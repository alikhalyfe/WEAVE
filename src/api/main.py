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
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.blending.operational import CONFIGS, METHODS, MODELS, blend_rows, skill_table
from src.data_pipeline import config

ARTIFACTS_DIR = Path(os.environ.get("WEAVE_ARTIFACTS_DIR", config.PROCESSED_DIR / "artifacts"))
FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"

Variable = Literal["temperature_2m_c", "precipitation_mm", "wind_speed_10m"]
MEMBER_COLS = [f"{m}_forecast" for m in MODELS]

app = FastAPI(title="WEAVE adaptive forecast blending API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    df = pd.read_csv(_require("forecasts.csv"), parse_dates=["timestamp"])
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
        return pd.Timestamp(_json("manifest").get("default_issue_time") or df["timestamp"].max()).floor("h")
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


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
