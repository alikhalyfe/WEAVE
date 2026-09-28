"""Open-Meteo client for live mode (https://open-meteo.com, CC BY 4.0).

Every value WEAVE shows in live mode comes from one of these calls:

    search        geocoding API, restricted to India
    forecast      latest run of each member model, hourly, 7+ days
    previous_runs archived forecasts at fixed lead days (skill history)
    era5          ERA5 reanalysis (ground truth, ~5-6 day latency)
    model_runs    initialisation time of each model's latest run

Member models (IDs verified against the live API):

    ecmwf_ifs  ECMWF IFS 0.25°      physical NWP
    gfs        NCEP GFS 0.11°       physical NWP
    icon       DWD ICON             physical NWP
    aifs       ECMWF AIFS 0.25°     AI / machine-learned
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import date, datetime, timezone

import httpx
import pandas as pd

from src.live import cache

LIVE_MODELS = {
    "ecmwf_ifs": {"id": "ecmwf_ifs025", "label": "ECMWF IFS", "kind": "NWP", "provider": "ECMWF"},
    "gfs": {"id": "ncep_gfs013", "label": "NCEP GFS", "kind": "NWP", "provider": "NOAA NCEP"},
    "icon": {"id": "dwd_icon", "label": "DWD ICON", "kind": "NWP", "provider": "DWD"},
    "aifs": {"id": "ecmwf_aifs025_single", "label": "ECMWF AIFS", "kind": "AI", "provider": "ECMWF"},
}
MODEL_KEYS = list(LIVE_MODELS)
_ID_TO_KEY = {v["id"]: k for k, v in LIVE_MODELS.items()}

# WEAVE variable name -> Open-Meteo hourly variable
VARIABLES = {
    "temperature_2m_c": "temperature_2m",
    "precipitation_mm": "precipitation",
    "wind_speed_10m": "wind_speed_10m",
}
LEAD_DAYS = list(range(8))  # previous_day0..7

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
META_URL = "https://api.open-meteo.com/data/{model}/static/meta.json"

TTL = {"geocode": 30 * 86400, "forecast": 3600, "previous_runs": 24 * 3600, "era5": 12 * 3600,
       "climatology": 30 * 86400, "meta": 1800}

# Free-tier limits (https://open-meteo.com/en/pricing), with headroom.
BUDGET = {60: 540, 3600: 4500, 86400: 9000}


def request_weight(params: dict) -> float:
    """Open-Meteo's call accounting: max(1, variables/10) x max(1, days/14)
    per location. Variables are counted per model (conservative)."""
    fields = params.get("hourly") or params.get("daily") or ""
    n_vars = len(fields.split(",")) * max(1, len(params.get("models", "").split(",")))
    if "start_date" in params:
        days = (date.fromisoformat(params["end_date"]) - date.fromisoformat(params["start_date"])).days + 1
    else:
        days = int(params.get("forecast_days", 1))
    n_loc = len(str(params.get("latitude", "")).split(","))
    return max(1.0, n_vars / 10) * max(1.0, days / 14) * n_loc


class _Budget:
    """Sliding-window spend tracker. Waits out the minute window; refuses
    (rather than hammering the API) once the hourly/daily budget is spent."""

    def __init__(self):
        self.spent: deque[tuple[float, float]] = deque()
        self.lock = threading.Lock()

    def _used(self, window: float, now: float) -> float:
        return sum(w for t, w in self.spent if now - t < window)

    def acquire(self, weight: float, max_wait: float = 65.0) -> None:
        deadline = time.time() + max_wait
        while True:
            with self.lock:
                now = time.time()
                while self.spent and now - self.spent[0][0] > 86400:
                    self.spent.popleft()
                for window in (86400, 3600):
                    if self._used(window, now) + weight > BUDGET[window]:
                        raise OpenMeteoError(
                            f"WEAVE's Open-Meteo {'daily' if window == 86400 else 'hourly'} request budget is used up; "
                            "cached places still work, new ones will be available later.")
                if self._used(60, now) + weight <= BUDGET[60]:
                    self.spent.append((now, weight))
                    return
            if time.time() > deadline:
                raise OpenMeteoError("Open-Meteo per-minute limit reached; try again in a minute.")
            time.sleep(2)


budget = _Budget()
COMMON = {"timezone": "UTC", "wind_speed_unit": "ms", "precipitation_unit": "mm", "temperature_unit": "celsius"}


class OpenMeteoError(RuntimeError):
    """Upstream failure (network, HTTP error or API error payload)."""


_client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), headers={"User-Agent": "WEAVE/2 (non-commercial)"})


def set_client(client: httpx.Client) -> None:
    """Swap the HTTP client (tests use httpx.MockTransport)."""
    global _client
    _client = client


def _get(url: str, params: dict, kind: str) -> tuple[object, float]:
    """GET with TTL cache and one retry. Returns (json, fetched_at_unix)."""
    key = str(httpx.URL(url, params=params))
    hit = cache.get(key, TTL[kind])
    if hit:
        return hit[1], hit[0]
    if url != GEOCODE_URL and "meta.json" not in url:
        budget.acquire(request_weight(params))
    last_error = None
    for _ in range(2):
        try:
            res = _client.get(url, params=params)
            body = res.json()
            if res.status_code != 200 or (isinstance(body, dict) and body.get("error")):
                reason = body.get("reason", res.text[:200]) if isinstance(body, dict) else res.text[:200]
                last_error = OpenMeteoError(f"Open-Meteo {res.status_code}: {reason}")
                if res.status_code < 500:
                    break
                continue
            return body, cache.put(key, body)
        except (httpx.HTTPError, ValueError) as exc:
            last_error = OpenMeteoError(f"Open-Meteo request failed: {exc}")
    raise last_error


def search(query: str, count: int = 10) -> list[dict]:
    """Places in India matching query (name, state, coordinates, population)."""
    body, _ = _get(GEOCODE_URL, {"name": query, "count": count, "language": "en", "format": "json", "countryCode": "IN"}, "geocode")
    return [
        {"name": r["name"], "state": r.get("admin1"), "district": r.get("admin2"), "latitude": r["latitude"],
         "longitude": r["longitude"], "population": r.get("population"), "elevation": r.get("elevation")}
        for r in body.get("results", [])
        if r.get("country_code") == "IN"
    ]


def _hourly_frame(hourly: dict) -> pd.DataFrame:
    df = pd.DataFrame(hourly)
    df["timestamp"] = pd.to_datetime(df.pop("time"))
    return df


def forecast(places: list[tuple[float, float]], days: int = 8) -> tuple[list[pd.DataFrame], float]:
    """Latest run of every member for each place. One frame per place with
    columns timestamp, target_variable, <model>_forecast (valid-time rows)."""
    params = {
        **COMMON,
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in places),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in places),
        "hourly": ",".join(VARIABLES.values()),
        "models": ",".join(m["id"] for m in LIVE_MODELS.values()),
        "forecast_days": days,
    }
    body, fetched_at = _get(FORECAST_URL, params, "forecast")
    bodies = body if isinstance(body, list) else [body]
    return [_members_long(_hourly_frame(b["hourly"]), lead_day=None) for b in bodies], fetched_at


def _members_long(wide: pd.DataFrame, lead_day: int | None) -> pd.DataFrame:
    """Open-Meteo wide columns ('<var>[_previous_dayN]_<model id>') -> long
    rows per (timestamp, target_variable) with one column per member."""
    blocks = []
    for var, om_var in VARIABLES.items():
        prefix = om_var if lead_day in (None, 0) else f"{om_var}_previous_day{lead_day}"
        block = wide[["timestamp"]].copy()
        block["target_variable"] = var
        for model_id, key in _ID_TO_KEY.items():
            candidates = [f"{prefix}_{model_id}"]
            if lead_day == 0:
                candidates.append(f"{om_var}_previous_day0_{model_id}")
            col = next((c for c in candidates if c in wide.columns), None)
            block[f"{key}_forecast"] = pd.to_numeric(wide[col], errors="coerce") if col else float("nan")
        blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


def previous_runs(lat: float, lon: float, start: date, end: date) -> tuple[pd.DataFrame, float]:
    """Archived forecasts valid in [start, end] at lead days 0-7. Long rows:
    timestamp (valid time), target_variable, lead_time_hours (24 x day), members."""
    hourly = [f"{v}_previous_day{d}" if d else v for v in VARIABLES.values() for d in LEAD_DAYS]
    params = {
        **COMMON, "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": ",".join(hourly),
        "models": ",".join(m["id"] for m in LIVE_MODELS.values()),
        "start_date": start.isoformat(), "end_date": end.isoformat(),
    }
    body, fetched_at = _get(PREVIOUS_RUNS_URL, params, "previous_runs")
    wide = _hourly_frame(body["hourly"])
    frames = []
    for d in LEAD_DAYS:
        long = _members_long(wide, lead_day=d)
        long["lead_time_hours"] = 24 * d
        frames.append(long)
    return pd.concat(frames, ignore_index=True), fetched_at


def era5(lat: float, lon: float, start: date, end: date, kind: str = "era5") -> tuple[pd.DataFrame, float]:
    """ERA5 observations (timestamp, temperature_2m_c, precipitation_mm,
    wind_speed_10m); hours not yet published are dropped, never filled."""
    params = {
        **COMMON, "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": ",".join(VARIABLES.values()),
        "models": "era5", "start_date": start.isoformat(), "end_date": end.isoformat(),
    }
    body, fetched_at = _get(ARCHIVE_URL, params, kind)
    df = _hourly_frame(body["hourly"]).rename(columns={v: k for k, v in VARIABLES.items()})
    return df.dropna(subset=list(VARIABLES)).reset_index(drop=True), fetched_at


DAILY_VARIABLES = {
    "temperature_2m_c": "temperature_2m_max",
    "precipitation_mm": "precipitation_sum",
    "wind_speed_10m": "wind_speed_10m_max",
}


def era5_daily(lat: float, lon: float, start: date, end: date) -> tuple[pd.DataFrame, float]:
    """ERA5 daily max temperature, rain total and max wind on IST calendar
    days (date, temperature_2m_c, precipitation_mm, wind_speed_10m)."""
    params = {
        **COMMON, "timezone": "Asia/Kolkata", "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
        "daily": ",".join(DAILY_VARIABLES.values()), "models": "era5",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
    }
    body, fetched_at = _get(ARCHIVE_URL, params, "climatology")
    df = pd.DataFrame(body["daily"]).rename(columns={v: k for k, v in DAILY_VARIABLES.items()})
    df["date"] = pd.to_datetime(df.pop("time"))
    return df.dropna(subset=list(DAILY_VARIABLES)).reset_index(drop=True), fetched_at


def model_runs() -> dict[str, dict]:
    """Latest run initialisation / availability time per member (UTC ISO)."""
    out = {}
    for key, m in LIVE_MODELS.items():
        try:
            meta, _ = _get(META_URL.format(model=m["id"]), {}, "meta")
        except OpenMeteoError:
            out[key] = {"initialised": None, "available": None}
            continue

        def iso(t):
            return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="minutes") if t else None

        out[key] = {"initialised": iso(meta.get("last_run_initialisation_time")),
                    "available": iso(meta.get("last_run_availability_time"))}
    return out
