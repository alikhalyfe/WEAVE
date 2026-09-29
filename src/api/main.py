"""WEAVE API: serves the operational workflow's artifacts and blends new
forecasts on demand.

    uvicorn src.api.main:app --reload          (from the repo root)

Artifacts come from `python -m src.workflow` (data/processed/artifacts, or
$WEAVE_ARTIFACTS_DIR). If frontend/dist exists it is served at / so one
process hosts the whole product.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.blending.operational import CONFIGS, METHODS, MODELS, blend_rows, skill_table
from src.data_pipeline import config
from src.live import alerts, grid, openmeteo, service


def _default_artifacts_dir() -> Path:
    """Freshly generated artifacts if present, else the committed export."""
    local = config.PROCESSED_DIR / "artifacts"
    return local if (local / "manifest.json").exists() else config.DATA_DIR / "artifacts"


ARTIFACTS_DIR = Path(os.environ.get("WEAVE_ARTIFACTS_DIR", _default_artifacts_dir()))
FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"
# The deployed dashboard and local dev are always allowed; ALLOWED_ORIGINS
# (comma-separated) adds more. Trailing slashes are ignored, since browsers
# send origins without one.
DEFAULT_ORIGINS = ["https://weave-eosin-three.vercel.app", "http://localhost:5173", "http://127.0.0.1:5173"]
ALLOWED_ORIGINS = DEFAULT_ORIGINS + [
    o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
# Vercel preview deployments of this project (weave-<hash>-<team>.vercel.app).
VERCEL_PREVIEW_ORIGINS = r"https://weave-[a-z0-9-]+\.vercel\.app"
INDIA_BOUNDS = {"lat": (6.0, 37.5), "lon": (68.0, 97.5)}
ATTRIBUTION = ("Weather data by Open-Meteo.com (CC BY 4.0): ECMWF IFS, ENS & AIFS, NOAA NCEP GFS, DWD ICON; "
               "ERA5 reanalysis, Copernicus Climate Change Service. Official warnings: NDMA SACHET.")

Variable = Literal["temperature_2m_c", "precipitation_mm", "wind_speed_10m"]
MEMBER_COLS = [f"{m}_forecast" for m in MODELS]

@asynccontextmanager
async def lifespan(_app):
    # The operational workflow: keep tracked cities and the India grid fresh.
    if os.environ.get("WEAVE_BACKGROUND", "1") != "0":
        service.start_refresher()
    yield


app = FastAPI(title="WEAVE adaptive forecast blending API", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_origin_regex=VERCEL_PREVIEW_ORIGINS,
                   allow_methods=["GET", "POST"], allow_headers=["*"])


def _require(name: str) -> Path:
    path = ARTIFACTS_DIR / name
    if not path.exists():
        raise HTTPException(503, f"Artifact {name} missing -- run `python -m src.workflow` first.")
    return path


@lru_cache
def _json(name: str) -> dict:
    return json.loads(_require(f"{name}.json").read_text())


@lru_cache
def _forecasts() -> pd.DataFrame:
    name = "forecasts.csv" if (ARTIFACTS_DIR / "forecasts.csv").exists() else "forecasts.csv.gz"
    df = pd.read_csv(_require(name), parse_dates=["timestamp"])
    df["valid_time"] = df["timestamp"] + pd.to_timedelta(df["lead_time_hours"], unit="h")
    return df.sort_values(["location", "target_variable", "lead_time_hours", "timestamp"]).reset_index(drop=True)


@lru_cache
def _live_tables(cfg: str, target_variable: str, lead: int) -> dict[str, pd.DataFrame]:
    """Skill tables from every verified case in the archive -- what the
    blender would use for a forecast issued right after the archive ends."""
    df = _forecasts()
    verified = df[(df["target_variable"] == target_variable) & (df["lead_time_hours"] == lead)]
    verified = verified.dropna(subset=[*MEMBER_COLS, "actual_value"]).assign(hour=lambda d: d["timestamp"].dt.hour)
    spec = CONFIGS[cfg]
    return {name: skill_table(verified, keys, spec["bias_correct"]) for name, keys in spec["levels"]}


def _clean(value):
    """NaN/inf -> None (recursively) so responses are valid JSON."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _frame(df: pd.DataFrame) -> list[dict]:
    return _clean(json.loads(df.to_json(orient="records", date_format="iso")))


def _filter(records: list[dict], **conds) -> list[dict]:
    return [r for r in records if all(v is None or r.get(k) == v for k, v in conds.items())]


def _time(value: str | None) -> pd.Timestamp:
    df = _forecasts()
    if value is None:
        default = (_json("manifest").get("default_view") or {}).get("issue_time")
        return pd.Timestamp(default or df["timestamp"].max()).floor("h")
    try:
        ts = pd.Timestamp(value).tz_localize(None).floor("h")
    except (ValueError, TypeError):
        raise HTTPException(422, f"Invalid timestamp: {value}")
    return min(max(ts, df["timestamp"].min()), df["timestamp"].max())


@app.get("/api/health")
def health():
    ready = (ARTIFACTS_DIR / "manifest.json").exists()
    return {"status": "ok", "artifacts_ready": ready,
            "generated_at": _json("manifest")["generated_at"] if ready else None}


@app.get("/api/meta")
def meta():
    return _json("manifest")


@app.get("/api/snapshot")
def snapshot(time: str | None = None, lead: int = Query(12, ge=1)):
    """Every location x variable at one issue time: blended value, members,
    weights, regime and extreme guidance. Powers cards, map and alerts."""
    ts = _time(time)
    df = _forecasts()
    rows = df[(df["timestamp"] == ts) & (df["lead_time_hours"] == lead)]
    if rows.empty:
        raise HTTPException(404, f"No forecasts for issue time {ts} and lead {lead}h.")
    return {
        "issue_time": ts.isoformat(),
        "valid_time": (ts + pd.Timedelta(hours=lead)).isoformat(),
        "lead_time_hours": lead,
        "rows": _frame(rows.drop(columns=["valid_time"])),
    }


@app.get("/api/series")
def series(location: str, variable: Variable, lead: int = 12, time: str | None = None,
           hours_before: int = Query(96, ge=0, le=24 * 60), hours_after: int = Query(48, ge=0, le=24 * 60)):
    """Members, blend and observation around an issue time, keyed by valid time."""
    ts = _time(time)
    df = _forecasts()
    rows = df[(df["location"] == location) & (df["target_variable"] == variable) & (df["lead_time_hours"] == lead)
              & (df["timestamp"] >= ts - pd.Timedelta(hours=hours_before))
              & (df["timestamp"] <= ts + pd.Timedelta(hours=hours_after))]
    if rows.empty:
        raise HTTPException(404, "No forecasts for that location/variable/lead.")
    cols = ["timestamp", "valid_time", *MEMBER_COLS, "blended", "actual_value", "event_probability",
            "guidance_threshold", "weather_regime", *(f"weight_{m}" for m in MODELS)]
    return {"issue_time": ts.isoformat(), "points": _frame(rows[cols])}


@app.get("/api/daily")
def daily(location: str, variable: Variable, lead: int = 12):
    """Whole-year daily summary (for the timeline / date picker)."""
    df = _forecasts()
    rows = df[(df["location"] == location) & (df["target_variable"] == variable) & (df["lead_time_hours"] == lead)]
    agg = "sum" if variable == "precipitation_mm" else "max"
    daily_df = rows.groupby(rows["timestamp"].dt.floor("D")).agg(
        blended=("blended", agg), actual=("actual_value", agg),
        max_event_probability=("event_probability", "max"),
        guidance_events=("guidance_event", "sum"), observed_events=("observed_event", "sum"),
    ).reset_index().rename(columns={"timestamp": "date"})
    return {"aggregation": agg, "days": _frame(daily_df)}


@app.get("/api/weights")
def weights(variable: Variable | None = None, lead: int | None = None):
    w = _json("weights")
    return {k: _filter(v, target_variable=variable, lead_time_hours=lead) for k, v in w.items()}


@app.get("/api/skill")
def skill(variable: Variable | None = None, lead: int | None = None):
    s = _json("skill")
    return {k: _clean(_filter(v, target_variable=variable, lead_time_hours=lead)) for k, v in s.items()}


@app.get("/api/extremes")
def extremes(variable: Variable | None = None, lead: int | None = None):
    e = _json("extremes")
    return {
        "event_names": e["event_names"],
        "scales": _filter(e["scales"], target_variable=variable, lead_time_hours=lead),
        "verification": _clean(_filter(e["verification"], target_variable=variable, lead_time_hours=lead)),
        "notable_events": _clean(_filter(e["notable_events"], target_variable=variable, lead_time_hours=lead)),
    }


class BlendRequest(BaseModel):
    location: str
    target_variable: Variable
    lead_time_hours: int = Field(ge=1)
    season: Literal["Winter", "Summer", "Monsoon", "Post-Monsoon"]
    weather_regime: Literal["Normal", "Heavy Rain", "Heat", "High Wind"] | None = None
    issue_hour: int | None = Field(None, ge=0, le=23, description="UTC hour of issue (enables diurnal weights)")
    forecasts: dict[str, float | None] = Field(description="model_a / model_b / ai_model forecast values")


@app.post("/api/blend")
def blend(req: BlendRequest):
    """Blend a new set of model forecasts with weights learned from the
    verified archive (same fallback ladder as the operational workflow)."""
    unknown = set(req.forecasts) - set(MODELS)
    if unknown:
        raise HTTPException(422, f"Unknown models {sorted(unknown)}; expected {MODELS}.")
    if all(v is None for v in req.forecasts.values()):
        raise HTTPException(422, "At least one forecast value is required.")
    cfg, method = next(
        ((s["config"], s["method"]) for s in _json("manifest")["selected_methods"]
         if s["target_variable"] == req.target_variable and s["lead_time_hours"] == req.lead_time_hours),
        ("regime", "optimal"),
    )
    row = pd.DataFrame([{
        "location": req.location, "season": req.season, "weather_regime": req.weather_regime, "hour": req.issue_hour,
        "target_variable": req.target_variable, "lead_time_hours": req.lead_time_hours,
        **{f"{m}_forecast": req.forecasts.get(m) for m in MODELS},
    }]).astype({f"{m}_forecast": float for m in MODELS})
    tables = _live_tables(cfg, req.target_variable, req.lead_time_hours)
    out = blend_rows(row, tables, levels=CONFIGS[cfg]["levels"]).iloc[0]
    return _clean({
        "blended_forecast": float(out[f"blended_{method}"]),
        "config": cfg,
        "method": method,
        "weights": {m: float(out[f"w_{method}_{m}"]) for m in MODELS},
        "bias_correction": {m: float(out[f"bias_{m}"]) for m in MODELS},
        "historical_mae": {m: float(out[f"mae_{m}"]) for m in MODELS},
        "fallback_level": out["fallback_level"],
        "n_history": int(out["n_history"]),
        "all_methods": {k: float(out[f"blended_{k}"]) for k in METHODS},
    })


# ---- Live mode (Open-Meteo) ----

def _live_call(fn, *args):
    try:
        return fn(*args)
    except openmeteo.OpenMeteoError as exc:
        raise HTTPException(502, f"Upstream weather data unavailable: {exc}")


@app.get("/api/live/search")
def live_search(q: str = Query(min_length=2, max_length=80)):
    """Places in India matching q (Open-Meteo geocoding)."""
    return {"results": _live_call(openmeteo.search, q), "attribution": ATTRIBUTION}


@app.get("/api/live/forecast")
def live_forecast(lat: float, lon: float, name: str = Query("Selected place", max_length=120),
                  state: str | None = Query(None, max_length=80)):
    """Adaptive blend of ECMWF IFS, NCEP GFS, DWD ICON, the ECMWF ensemble
    mean and ECMWF AIFS for the next ~7 days, with weights learned from this
    place's verified history; plus official warnings near the place."""
    if not (INDIA_BOUNDS["lat"][0] <= lat <= INDIA_BOUNDS["lat"][1] and INDIA_BOUNDS["lon"][0] <= lon <= INDIA_BOUNDS["lon"][1]):
        raise HTTPException(422, "Live mode covers India only.")
    payload = _live_call(service.forecast, name, lat, lon)
    try:
        official = {"alerts": alerts.near(lat, lon, state), "error": None}
    except Exception as exc:  # official feed down: say so, forecast still served
        official = {"alerts": [], "error": f"Official alert feed unavailable: {exc}"}
    return _clean({**payload, "official_alerts": official, "attribution": ATTRIBUTION})


@app.get("/api/live/cities")
def live_cities():
    """Tracked cities with headline blended values and alerts. Cities still
    computing are reported as pending, never filled in."""
    return _clean({**service.overview(), "attribution": ATTRIBUTION})


@app.get("/api/live/models")
def live_models():
    return {"models": openmeteo.LIVE_MODELS, "runs": _live_call(openmeteo.model_runs), "attribution": ATTRIBUTION}


@app.get("/api/live/grid")
def live_grid():
    """Blended daily field over India (1.5° grid) with regional weights."""
    return _clean({**service.grid_field(), "attribution": ATTRIBUTION})


@app.get("/api/live/boundary")
def live_boundary():
    """India boundary (Survey of India claim; datameet, CC-0), simplified."""
    return grid.boundary()


@app.get("/api/live/official-alerts")
def official_alerts(lat: float | None = None, lon: float | None = None, state: str | None = None,
                    radius_km: float = Query(150, ge=10, le=1000)):
    """Active official warnings from NDMA SACHET (IMD, CWC, SDMAs). With
    lat/lon, only those near the place."""
    try:
        feed = alerts.fetch()
        items = alerts.near(lat, lon, state, radius_km) if lat is not None and lon is not None else feed["alerts"]
    except Exception as exc:
        raise HTTPException(502, f"Official alert feed unavailable: {exc}")
    return {"alerts": items, "fetched_at": feed["fetched_at"], "source": feed["source"]}


@app.get("/api/live/status")
def live_status():
    """Operational status: refresh loop, API budget, caches, feeds."""
    return _clean(service.status())


# ---- Frontend (single-page app) ----

if FRONTEND_DIST.exists():
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and FRONTEND_DIST.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
