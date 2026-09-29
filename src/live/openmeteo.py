"""Open-Meteo client for live mode (https://open-meteo.com, CC BY 4.0).

Every value WEAVE shows in live mode comes from one of these calls:

    search           geocoding API, restricted to India
    forecast         latest run of each member, hourly, 8 days (+ cloud cover)
    forecast_daily   daily member forecasts for many points (the India grid)
    ensemble_daily   all 51 ECMWF ensemble members, daily (event probabilities)
    previous_runs    archived forecasts at fixed lead days (skill history)
    era5 / era5_daily ERA5 reanalysis (ground truth, ~6-day latency)
    model_runs       initialisation time of each model's latest run

Member models (IDs verified against the live API):

    ecmwf_ifs  ECMWF IFS 0.25°              physical NWP (deterministic)
    gfs        NCEP GFS 0.11°               physical NWP (deterministic)
    icon       DWD ICON                     physical NWP (deterministic)
    ens        ECMWF IFS ENS mean (51 mem.) ensemble
    aifs       ECMWF AIFS 0.25°             AI / machine-learned

The ensemble mean is archived by the previous-runs API like the others, but
the forecast API returns it empty, so its live run comes from the ensemble
API instead (same model ID).
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
    "ens": {"id": "ecmwf_ifs025_ensemble_mean", "meta": "ecmwf_ifs025_ensemble", "label": "ECMWF ENS mean",
            "kind": "Ensemble", "provider": "ECMWF", "via": "ensemble"},
    "aifs": {"id": "ecmwf_aifs025_single", "label": "ECMWF AIFS", "kind": "AI", "provider": "ECMWF"},
}
# Tested and rejected (held-out, 4 cities x 3 variables x 8 lead days, same
# windows): adding UKMO global 10 km, JMA GSM and GEM global as members
# changed the blend's MAE by -0.6% (temperature), +0.4% (rain) and -0.2%
# (wind) at the median -- no gain, more selection noise -- so they are not used.
DETERMINISTIC = [k for k, m in LIVE_MODELS.items() if m.get("via") != "ensemble"]
ENSEMBLE_MEMBERS_MODEL = "ecmwf_ifs025"  # 51-member ECMWF ensemble on the ensemble API
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
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
META_URL = "https://api.open-meteo.com/data/{model}/static/meta.json"

TTL = {"geocode": 30 * 86400, "forecast": 3 * 3600, "previous_runs": 24 * 3600, "era5": 12 * 3600,
       "climatology": 30 * 86400, "meta": 1800, "ensemble": 6 * 3600, "grid": 6 * 3600}

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

# After Open-Meteo answers 429, every request pauses until the limit resets
# (retrying would only burn more allowance). Cached data keeps being served.
_blocked = {"until": 0.0, "reason": None}


def _block_after_429(reason: str) -> None:
    now = time.time()
    text = reason.lower()
    if "minut" in text:
        until = now + 65
    elif "hour" in text:
        until = (now // 3600 + 1) * 3600 + 60
    elif "day" in text or "daily" in text:
        until = (now // 86400 + 1) * 86400 + 60
    else:
        until = now + 300
    _blocked.update(until=until, reason=reason)


def paused() -> dict | None:
    """{'until': unix, 'reason': str} while paused after a 429, else None."""
    return dict(_blocked) if time.time() < _blocked["until"] else None


def can_spend(weight: float, window: int = 3600) -> bool:
    """True if `weight` more units fit this server's budget for `window`."""
    if paused():
        return False
    now = time.time()
    with budget.lock:
        used = sum(w for t, w in budget.spent if now - t < window)
    return used + weight <= BUDGET[window]
COMMON = {"timezone": "UTC", "wind_speed_unit": "ms", "precipitation_unit": "mm", "temperature_unit": "celsius"}


class OpenMeteoError(RuntimeError):
    """Upstream failure (network, HTTP error or API error payload)."""


# Generous connect timeout: TLS handshakes to Open-Meteo occasionally stall
# (seen from GitHub runners as "_ssl.c: The handshake operation timed out").
_client = httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0), headers={"User-Agent": "WEAVE/2 (non-commercial)"})
RETRY_WAITS = (0, 3, 10, 30)  # seconds before each attempt: transient network/5xx errors only


def set_client(client: httpx.Client) -> None:
    """Swap the HTTP client (tests use httpx.MockTransport)."""
    global _client
    _client = client


def _get(url: str, params: dict, kind: str, weight_factor: float = 1.0) -> tuple[object, float]:
    """GET with TTL cache; network errors and 5xx are retried with backoff
    (RETRY_WAITS), other errors are not. Returns (json, fetched_at_unix).
    weight_factor scales the budget charge (ensemble members count as variables)."""
    key = str(httpx.URL(url, params=params))
    hit = cache.get(key, TTL[kind])
    if hit:
        return hit[1], hit[0]
    if url != GEOCODE_URL and "meta.json" not in url:
        p = paused()
        if p:
            resume = datetime.fromtimestamp(p["until"], timezone.utc).strftime("%H:%M UTC")
            raise OpenMeteoError(f"Open-Meteo limit reached ({p['reason']}); paused until {resume}, cached data still served.")
        budget.acquire(request_weight(params) * weight_factor)
    last_error = None
    for wait in RETRY_WAITS:
        if wait:
            time.sleep(wait)
        try:
            res = _client.get(url, params=params)
            body = res.json()
            if res.status_code != 200 or (isinstance(body, dict) and body.get("error")):
                reason = body.get("reason", res.text[:200]) if isinstance(body, dict) else res.text[:200]
                last_error = OpenMeteoError(f"Open-Meteo {res.status_code}: {reason}")
                if res.status_code == 429:
                    _block_after_429(reason)
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


def _coords(places: list[tuple[float, float]]) -> dict:
    return {"latitude": ",".join(f"{lat:.4f}" for lat, _ in places),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in places)}


def _suffix_single(block: dict, model_id: str) -> dict:
    """Single-model responses omit the model suffix; add it back."""
    return {k if k == "time" else f"{k}_{model_id}": v for k, v in block.items()}


def forecast(places: list[tuple[float, float]], days: int = 8) -> tuple[list[dict], float]:
    """Latest run of every member for each place. Per place: members (long
    rows timestamp, target_variable, <model>_forecast), cloud (mean cloud
    cover of the deterministic models, for plain-language wording only; it
    is not blended), and the grid-cell elevation."""
    det = [LIVE_MODELS[k]["id"] for k in DETERMINISTIC]
    params = {**COMMON, **_coords(places), "hourly": ",".join([*VARIABLES.values(), "cloud_cover"]),
              "models": ",".join(det), "forecast_days": days}
    body, fetched_at = _get(FORECAST_URL, params, "forecast")
    ens_id = LIVE_MODELS["ens"]["id"]
    ens_params = {**COMMON, **_coords(places), "hourly": ",".join(VARIABLES.values()), "models": ens_id, "forecast_days": days}
    try:
        ens_body, _ = _get(ENSEMBLE_URL, ens_params, "forecast")
        ens_bodies = ens_body if isinstance(ens_body, list) else [ens_body]
    except OpenMeteoError:
        ens_bodies = [None] * len(places)  # ensemble unavailable: blend the other members
    out = []
    for b, e in zip(body if isinstance(body, list) else [body], ens_bodies):
        wide = _hourly_frame(b["hourly"])
        if e is not None:
            ens = _hourly_frame(_suffix_single(e["hourly"], ens_id))
            wide = wide.merge(ens, on="timestamp", how="left")
        cloud_cols = [c for c in wide.columns if c.startswith("cloud_cover")]
        cloud = wide[["timestamp"]].assign(cloud_cover=wide[cloud_cols].mean(axis=1) if cloud_cols else float("nan"))
        out.append({"members": _members_long(wide, lead_day=None), "cloud": cloud, "elevation": b.get("elevation")})
    return out, fetched_at


DAILY_FORECAST = {
    "temperature_2m_c": "temperature_2m_max",
    "temperature_min": "temperature_2m_min",
    "precipitation_mm": "precipitation_sum",
    "wind_speed_10m": "wind_speed_10m_max",
}


def forecast_daily(places: list[tuple[float, float]], days: int = 8) -> tuple[list[pd.DataFrame], float]:
    """Daily member forecasts (IST days) for many points at once: the India
    grid. One frame per point: date + '<variable>__<model key>' columns."""
    det = [LIVE_MODELS[k]["id"] for k in DETERMINISTIC]
    base = {**COMMON, "timezone": "Asia/Kolkata", **_coords(places), "daily": ",".join(DAILY_FORECAST.values()), "forecast_days": days}
    body, fetched_at = _get(FORECAST_URL, {**base, "models": ",".join(det)}, "grid")
    ens_id = LIVE_MODELS["ens"]["id"]
    try:
        ens_body, _ = _get(ENSEMBLE_URL, {**base, "models": ens_id}, "grid")
        ens_bodies = ens_body if isinstance(ens_body, list) else [ens_body]
    except OpenMeteoError:
        ens_bodies = [None] * len(places)
    frames = []
    for b, e in zip(body if isinstance(body, list) else [body], ens_bodies):
        daily = dict(b["daily"])
        if e is not None:
            daily.update({k: v for k, v in _suffix_single(e["daily"], ens_id).items() if k != "time"})
        df = pd.DataFrame({"date": pd.to_datetime(daily["time"])})
        for var, om in DAILY_FORECAST.items():
            for key, m in LIVE_MODELS.items():
                col = f"{om}_{m['id']}"
                df[f"{var}__{key}"] = pd.to_numeric(pd.Series(daily.get(col, [None] * len(df))), errors="coerce")
        frames.append(df)
    return frames, fetched_at


def ensemble_daily(lat: float, lon: float, days: int = 8) -> tuple[pd.DataFrame, float]:
    """All ECMWF ensemble members' daily max temperature, rain total and max
    wind on IST days. Long: date, variable, member, value."""
    params = {**COMMON, "timezone": "Asia/Kolkata", "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
              "daily": ",".join(DAILY_VARIABLES.values()), "models": ENSEMBLE_MEMBERS_MODEL, "forecast_days": days}
    body, fetched_at = _get(ENSEMBLE_URL, params, "ensemble", weight_factor=51)
    daily = body["daily"]
    dates = pd.to_datetime(daily["time"])
    rows = []
    for var, om in DAILY_VARIABLES.items():
        for col, values in daily.items():
            if col == om or col.startswith(om + "_member"):
                member = 0 if col == om else int(col.rsplit("member", 1)[1])
                rows.append(pd.DataFrame({"date": dates, "variable": var, "member": member,
                                          "value": pd.to_numeric(pd.Series(values), errors="coerce")}))
    return pd.concat(rows, ignore_index=True).dropna(subset=["value"]), fetched_at


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
    timestamp (valid time), target_variable, lead_time_hours (24 x day), members.

    One request per model: each is cached on its own, so adding a member
    never re-downloads the others, and one model's outage only drops that
    member (its column stays empty and the blend renormalises)."""
    hourly = [f"{v}_previous_day{d}" if d else v for v in VARIABLES.values() for d in LEAD_DAYS]
    wide, fetched = None, []
    for m in LIVE_MODELS.values():
        params = {**COMMON, "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": ",".join(hourly),
                  "models": m["id"], "start_date": start.isoformat(), "end_date": end.isoformat()}
        try:
            body, t = _get(PREVIOUS_RUNS_URL, params, "previous_runs")
        except OpenMeteoError:
            continue
        fetched.append(t)
        frame = _hourly_frame(_suffix_single(body["hourly"], m["id"]))
        wide = frame if wide is None else wide.merge(frame, on="timestamp", how="outer")
    if wide is None:
        raise OpenMeteoError("No archived forecasts available for this place.")
    frames = []
    for d in LEAD_DAYS:
        long = _members_long(wide, lead_day=d)
        long["lead_time_hours"] = 24 * d
        frames.append(long)
    return pd.concat(frames, ignore_index=True), min(fetched)


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
            meta, _ = _get(META_URL.format(model=m.get("meta", m["id"])), {}, "meta")
        except OpenMeteoError:
            out[key] = {"initialised": None, "available": None}
            continue

        def iso(t):
            return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="minutes") if t else None

        out[key] = {"initialised": iso(meta.get("last_run_initialisation_time")),
                    "available": iso(meta.get("last_run_availability_time"))}
    return out
