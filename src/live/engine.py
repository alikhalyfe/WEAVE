"""Live adaptive blending for any place in India.

For one place:

1. Truth: ERA5 for the last ~135 days (ERA5 lags real time by ~6 days).
2. Skill history: the members' archived forecasts at lead days 0-7 that
   verify in the last HISTORY_DAYS days of available truth.
3. For each (variable, lead day), using only members with >= 80% coverage,
   the history is split into three consecutive windows:

       fit | select (HOLDOUT_DAYS) | evaluate (HOLDOUT_DAYS)

   * every CONFIGS x METHODS candidate is fitted on `fit` and scored on
     `select`; the best one is chosen;
   * the chosen candidate is refitted on fit+select and scored on
     `evaluate` -- data never used for fitting or choosing, so that is the
     honest out-of-sample skill reported;
   * finally it is refitted on the full history for the live blend.
   Skill state is cached for SKILL_TTL; hourly refreshes only re-blend.
4. Blend the members' latest run with those weights. Lead day for a valid
   time = floor(hours ahead / 24), matching Open-Meteo's previous_dayN.
5. Extremes are judged per IST calendar day, like heat-wave and heavy-rain
   days: daily max temperature, daily rain total and daily max wind against
   the 95th percentile of the same +-15 days of year in the place's last 2
   years of ERA5 (rain: p95 of wet days >= 1 mm). Event probability is the
   skill-weighted share of (bias-corrected) members reaching it; the
   evaluate window gives POD/FAR/CSI for the same rule.

Nothing is fabricated: missing members are dropped and renormalised,
unpublished truth is simply absent, and every output carries timestamps.
"""

from __future__ import annotations

import threading
import time
from datetime import timedelta

import numpy as np
import pandas as pd

from src.blending.operational import CONFIGS, METHODS, blend_rows, forecast_columns, skill_table
from src.data_pipeline.config import MONTH_TO_SEASON
from src.evaluation.extreme_events import event_metrics
from src.live import openmeteo
from src.live.openmeteo import LIVE_MODELS, MODEL_KEYS, VARIABLES
from src.regime.classifier import classify, training_thresholds

HISTORY_DAYS = 120
HOLDOUT_DAYS = 21
TRUTH_LOOKBACK_DAYS = 135
SKILL_TTL = 24 * 3600
MIN_COVERAGE = 0.8
MIN_SAMPLES = 50
CLIMATE_DAYS = 730
WINDOW_DAYS = 15
WET_DAY_MM = 1.0
IST = pd.Timedelta(hours=5, minutes=30)
DAILY_AGG = {"temperature_2m_c": "max", "precipitation_mm": "sum", "wind_speed_10m": "max"}


def _utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h")


def _add_context(df: pd.DataFrame, name: str, regime_thresholds: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    """location / season / hour, and the regime the member-mean forecast
    implies (known at issue time, so usable for both history and live)."""
    df = df.copy()
    df["location"] = name
    df["season"] = df["timestamp"].dt.month.map(MONTH_TO_SEASON)
    df["hour"] = df["timestamp"].dt.hour
    mean = df[value_cols].mean(axis=1)
    keys = ["timestamp", "lead_time_hours"]
    wide = df.assign(member_mean=mean).pivot_table(
        index=[*keys, "location", "season"], columns="target_variable", values="member_mean").reset_index()
    for var in VARIABLES:
        if var not in wide:
            wide[var] = np.nan
    wide["weather_regime"] = classify(wide, regime_thresholds)
    return df.merge(wide[[*keys, "weather_regime"]], on=keys, how="left")


def daily_thresholds(clim: pd.DataFrame) -> pd.DataFrame:
    """p95 per day-of-year (1-366) from a +-WINDOW_DAYS circular window over
    every year in `clim` (daily ERA5). Rain uses wet days only, falling back
    to the whole record's wet days when the window has fewer than 10."""
    doy = clim["date"].dt.dayofyear.to_numpy()
    out = {"doy": np.arange(1, 367)}
    all_wet = clim.loc[clim["precipitation_mm"] >= WET_DAY_MM, "precipitation_mm"]
    for var in DAILY_AGG:
        values = clim[var].to_numpy()
        col = []
        for d in out["doy"]:
            dist = np.abs(doy - d)
            in_window = np.minimum(dist, 366 - dist) <= WINDOW_DAYS
            v = values[in_window]
            if var == "precipitation_mm":
                v = v[v >= WET_DAY_MM]
                if len(v) < 10:
                    v = all_wet.to_numpy()
            col.append(float(np.quantile(v, 0.95)) if len(v) else np.nan)
        out[var] = col
    return pd.DataFrame(out)


def climatology(lat: float, lon: float) -> pd.DataFrame:
    """Day-of-year event thresholds from the last 2 years of daily ERA5."""
    end = _utc_now().date() - timedelta(days=7)  # ERA5 publication lag
    end = end.replace(day=1) - timedelta(days=1)  # whole months: stable cache key for weeks
    clim, _ = openmeteo.era5_daily(lat, lon, end - timedelta(days=CLIMATE_DAYS - 1), end)
    if clim.empty:
        raise openmeteo.OpenMeteoError("ERA5 climatology unavailable for this place.")
    return daily_thresholds(clim)


def _history(name: str, lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.DataFrame]:
    """(history with context, hourly regime thresholds, last obs time, truth)."""
    today = _utc_now().date()
    truth, _ = openmeteo.era5(lat, lon, today - timedelta(days=TRUTH_LOOKBACK_DAYS), today)
    if truth.empty:
        raise openmeteo.OpenMeteoError("ERA5 returned no observations for this place.")
    last_obs = truth["timestamp"].max()
    # Regime thresholds (a conditioning key for the weights) come from the
    # truth already fetched: seasonal hourly p95 over the lookback window.
    regime_thr = training_thresholds(
        truth.assign(location=name, season=truth["timestamp"].dt.month.map(MONTH_TO_SEASON)),
        calibration_end=last_obs + pd.Timedelta(hours=1))
    start = (last_obs - pd.Timedelta(days=HISTORY_DAYS)).date()
    prev, _ = openmeteo.previous_runs(lat, lon, start, last_obs.date())
    truth_long = truth.melt(id_vars="timestamp", var_name="target_variable", value_name="actual_value")
    hist = prev.merge(truth_long, on=["timestamp", "target_variable"], how="inner")
    hist = hist[hist["timestamp"] >= last_obs - pd.Timedelta(days=HISTORY_DAYS)]
    return _add_context(hist, name, regime_thr, forecast_columns(MODEL_KEYS)), regime_thr, last_obs, truth


def _mae(pred, actual) -> float:
    return float(np.mean(np.abs(np.asarray(pred, dtype=float) - np.asarray(actual, dtype=float))))


def _group_models(hist: pd.DataFrame) -> list[str]:
    return [m for m in MODEL_KEYS if hist[f"{m}_forecast"].notna().mean() >= MIN_COVERAGE]


def _tables(frame: pd.DataFrame, cfg: str, models: list[str]) -> dict[str, pd.DataFrame]:
    spec = CONFIGS[cfg]
    return {n: skill_table(frame, keys, spec["bias_correct"], models) for n, keys in spec["levels"]}


def _blend(rows: pd.DataFrame, tables: dict, cfg: str, method: str, models: list[str]) -> pd.DataFrame:
    b = blend_rows(rows.reset_index(drop=True), tables, MIN_SAMPLES, CONFIGS[cfg]["levels"], models)
    b["blended"] = b[f"blended_{method}"]
    return b


def _fit_group(hist: pd.DataFrame, models: list[str], select_start: pd.Timestamp, eval_start: pd.Timestamp) -> dict:
    """Choose a candidate on the select window, report skill on the evaluate
    window, and return skill tables refitted on the whole history."""
    cols = forecast_columns(models)
    hist = hist.dropna(subset=[*cols, "actual_value"])
    fit = hist[hist["timestamp"] < select_start]
    select = hist[(hist["timestamp"] >= select_start) & (hist["timestamp"] < eval_start)]
    evaluate = hist[hist["timestamp"] >= eval_start]
    if len(fit) < MIN_SAMPLES or select.empty:
        return {"config": "regime", "method": "equal", "skill": [], "evaluation": None,
                "tables": _tables(hist, "regime", models) if len(hist) else {}}

    best = None
    for cfg in CONFIGS:
        b = _blend(select, _tables(fit, cfg, models), cfg, "equal", models)
        for method in METHODS:
            score = _mae(b[f"blended_{method}"], b["actual_value"])
            if best is None or score < best[0]:
                best = (score, cfg, method)
    _, cfg, method = best

    evaluation, skill = None, []
    if not evaluate.empty:
        evaluation = _blend(evaluate, _tables(hist[hist["timestamp"] < eval_start], cfg, models), cfg, method, models)
        skill = [{"source": m, "mae": _mae(evaluate[f"{m}_forecast"], evaluate["actual_value"])} for m in models]
        skill.append({"source": "equal_mean", "mae": _mae(evaluate[cols].mean(axis=1), evaluate["actual_value"])})
        skill.append({"source": "blended", "mae": _mae(evaluation["blended"], evaluation["actual_value"])})
        for s in skill:
            s["n"] = len(evaluate)
    return {"config": cfg, "method": method, "skill": skill, "evaluation": evaluation, "tables": _tables(hist, cfg, models)}


def _ist_date(ts: pd.Series) -> pd.Series:
    return (ts + IST).dt.normalize()


def _threshold_for(dates: pd.Series, thresholds: pd.DataFrame, var: str) -> np.ndarray:
    return thresholds.set_index("doy")[var].reindex(dates.dt.dayofyear).to_numpy()


def _event_verification(evaluation: pd.DataFrame | None, thresholds: pd.DataFrame, var: str) -> dict | None:
    """Daily rule (blend daily aggregate >= day-of-year p95) scored against
    ERA5 daily aggregates on complete IST days of the evaluate window."""
    if evaluation is None or evaluation.empty:
        return None
    e = evaluation.assign(date=_ist_date(evaluation["timestamp"]))
    daily = e.groupby("date").agg(hours=("actual_value", "size"), blended=("blended", DAILY_AGG[var]),
                                  actual=("actual_value", DAILY_AGG[var])).reset_index()
    daily = daily[daily["hours"] == 24]
    if daily.empty:
        return None
    thr = _threshold_for(daily["date"], thresholds, var)
    observed = daily["actual"].to_numpy() >= thr
    forecast = daily["blended"].to_numpy() >= thr
    m = event_metrics(observed, forecast)
    return {"days": len(daily), "observed_events": int(observed.sum()), "forecast_events": int(forecast.sum()),
            "pod": float(m["recall"]) if observed.any() else None,
            "far": float(1 - m["precision"]) if forecast.any() else None,
            "csi": float(m["csi"]) if (observed.any() or forecast.any()) else None}


_skill_cache: dict[tuple, tuple[float, dict]] = {}
_skill_locks: dict[tuple, threading.Lock] = {}
_locks_guard = threading.Lock()


def skill_state(name: str, lat: float, lon: float) -> dict:
    """Thresholds + per (variable, lead day) chosen candidate, skill tables
    and out-of-sample verification. Cached for SKILL_TTL per place."""
    key = (round(lat, 3), round(lon, 3))
    with _locks_guard:
        lock = _skill_locks.setdefault(key, threading.Lock())
    with lock:  # concurrent requests for one place compute it once
        hit = _skill_cache.get(key)
        if hit and time.time() - hit[0] < SKILL_TTL:
            return hit[1]

        thresholds = climatology(lat, lon)
        hist, regime_thr, last_obs, _ = _history(name, lat, lon)
        eval_start = last_obs - pd.Timedelta(days=HOLDOUT_DAYS)
        select_start = eval_start - pd.Timedelta(days=HOLDOUT_DAYS)

        groups = {}
        for (var, lead), h in hist.groupby(["target_variable", "lead_time_hours"]):
            models = _group_models(h)
            if models:
                g = _fit_group(h, models, select_start, eval_start)
                g["models"] = models
                g["event_verification"] = _event_verification(g["evaluation"], thresholds, var)
                groups[(var, int(lead))] = g
        state = {"thresholds": thresholds, "regime_thresholds": regime_thr, "groups": groups,
                 "last_obs": last_obs, "computed_at": time.time()}
        _skill_cache[key] = (time.time(), state)
        return state


def live_forecast(name: str, lat: float, lon: float) -> dict:
    t0 = time.time()
    now = _utc_now()
    state = skill_state(name, lat, lon)
    thresholds, groups = state["thresholds"], state["groups"]

    (fc,), fetched_at = openmeteo.forecast([(lat, lon)])
    fc = fc[fc["timestamp"] >= now].copy()
    hours = (fc["timestamp"] - now) / pd.Timedelta(hours=1)
    fc["lead_time_hours"] = 24 * np.minimum(hours // 24, 7).astype(int)
    fc["hours_ahead"] = hours.astype(int)
    fc = _add_context(fc, name, state["regime_thresholds"], forecast_columns(MODEL_KEYS))

    variables = {}
    for var in VARIABLES:
        rows, chosen, skill, verification, recent = [], [], [], [], None
        for lead in sorted(fc["lead_time_hours"].unique()):
            live = fc[(fc["target_variable"] == var) & (fc["lead_time_hours"] == lead)]
            day = int(lead // 24)
            g = groups.get((var, int(lead)))
            if g is None:  # no verified history for this lead: equal weights over the members present
                models = [m for m in MODEL_KEYS if live[f"{m}_forecast"].notna().any()]
                g = {"config": "regime", "method": "equal", "tables": {}, "models": models, "skill": [],
                     "event_verification": None, "evaluation": None}
            b = _blend(live, g["tables"], g["config"], g["method"], g["models"])
            for m in MODEL_KEYS:
                b[f"weight_{m}"] = b[f"w_{g['method']}_{m}"] if m in g["models"] else 0.0
                if m not in g["models"]:
                    b[f"bias_{m}"] = 0.0
            b["models"] = [g["models"]] * len(b)
            rows.append(b)
            chosen.append({"lead_day": day, "config": g["config"], "method": g["method"], "models": g["models"]})
            skill += [{**s, "lead_day": day} for s in g["skill"]]
            if g["event_verification"]:
                verification.append({**g["event_verification"], "lead_day": day})
            if day == 1 and g["evaluation"] is not None:
                recent = g["evaluation"].sort_values("timestamp")
        blended = pd.concat(rows, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
        variables[var] = {
            "points": _points(blended),
            "days": _days(blended, thresholds, var),
            "chosen": chosen,
            "skill": skill,
            "event_verification": verification,
            "recent_verification": _recent(recent),
        }

    last_obs = state["last_obs"]
    return {
        "place": {"name": name, "latitude": lat, "longitude": lon},
        "issued_at": now.isoformat(),
        "fetched_at": pd.Timestamp(fetched_at, unit="s").isoformat(timespec="seconds"),
        "skill_computed_at": pd.Timestamp(state["computed_at"], unit="s").isoformat(timespec="seconds"),
        "model_runs": openmeteo.model_runs(),
        "models": LIVE_MODELS,
        "truth_available_until": last_obs.isoformat(),
        "history_window_days": HISTORY_DAYS,
        "evaluation_window": [(last_obs - pd.Timedelta(days=HOLDOUT_DAYS)).isoformat(), last_obs.isoformat()],
        "event_definition": {"window_days": WINDOW_DAYS, "climate_days": CLIMATE_DAYS, "percentile": 95,
                             "wet_day_mm": WET_DAY_MM, "daily_aggregate": DAILY_AGG, "day_boundary": "IST"},
        "variables": variables,
        "compute_seconds": round(time.time() - t0, 2),
    }


def _points(b: pd.DataFrame) -> list[dict]:
    out = []
    for r in b.itertuples(index=False):
        r = r._asdict()
        models = r["models"]
        out.append({
            "time": r["timestamp"].isoformat(), "hours_ahead": int(r["hours_ahead"]), "lead_day": int(r["lead_time_hours"] // 24),
            "members": {m: _num(r[f"{m}_forecast"]) for m in MODEL_KEYS}, "blended": _num(r["blended"]),
            "weights": {m: _num(r[f"weight_{m}"]) for m in models},
            "bias_correction": {m: _num(-r[f"bias_{m}"]) for m in models},
            "fallback_level": r["fallback_level"], "n_history": int(r["n_history"]), "regime": r["weather_regime"],
        })
    return out


def _days(b: pd.DataFrame, thresholds: pd.DataFrame, var: str) -> list[dict]:
    """Per IST day: blended and member daily aggregates, the day-of-year
    threshold, event flag and skill-weighted member agreement."""
    agg = DAILY_AGG[var]
    b = b.assign(date=_ist_date(b["timestamp"]))
    for m in MODEL_KEYS:
        b[f"corr_{m}"] = b[f"{m}_forecast"] - b[f"bias_{m}"]
    out = []
    for date, g in b.groupby("date", sort=True):
        thr = float(_threshold_for(pd.Series([date]), thresholds, var)[0])
        blended = float(getattr(g["blended"], agg)())
        members, weights = {}, {}
        for m in MODEL_KEYS:
            col = g[f"corr_{m}"]
            members[m] = float(getattr(col, agg)()) if col.notna().all() else None
            weights[m] = float(g[f"weight_{m}"].mean())
        agree = [m for m, v in members.items() if v is not None and weights[m] > 0]
        wsum = sum(weights[m] for m in agree)
        prob = sum(weights[m] for m in agree if members[m] >= thr) / wsum if wsum else None
        out.append({
            "date": date.date().isoformat(), "hours": len(g), "complete": len(g) == 24,
            "first_hour_ist": (g["timestamp"].min() + IST).strftime("%H:%M"),
            "blended": _num(blended), "members": {m: _num(v) for m, v in members.items()},
            "threshold": _num(thr), "event": bool(np.isfinite(thr) and blended >= thr), "probability": _num(prob),
        })
    return out


def _recent(evaluation: pd.DataFrame | None) -> list[dict]:
    if evaluation is None or len(evaluation) == 0:
        return []
    return [{"time": r.timestamp.isoformat(), "blended": _num(r.blended), "actual": _num(r.actual_value),
             **{m: _num(getattr(r, f"{m}_forecast")) for m in MODEL_KEYS}} for r in evaluation.itertuples()]


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None
