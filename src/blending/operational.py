"""Operational (rolling-origin) adaptive blending over the forecast archive.

adaptive_blender.adaptive_blend answers "blend these forecasts for one
issue time". This module answers the operational question at scale: blend
every archived forecast exactly as a live system would have, with weights
re-estimated at the start of each update period (monthly by default) from
forecasts whose verifying observation was already available -- i.e. whose
target time (timestamp + lead) is strictly before the period starts.

Weights are conditioned on target variable and lead time at every level,
then on a fallback ladder of increasingly broad conditions:

    [location + season + hour of day]     (diurnal configurations only)
    [location + hour of day]
    location + season + weather regime
    location + season
    location
    global (variable + lead only)
    equal weights (no verified history yet)

A level is used only if it has >= min_samples verified cases.

Weighting methods, all computed per condition group:

    equal        1/N each
    inverse_mae  weight_engine.calculate_weights on MAE (the original engine)
    inverse_mse  same engine on MSE -- penalises large misses more
    optimal      weight_engine.optimal_weights (NNLS stacking, sum to 1)

With bias_correct=True each model's mean error in the group is subtracted
before weighting and blending (standard statistical post-processing).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.blending.adaptive_blender import DEFAULT_MODEL_FORECAST_COLUMNS
from src.blending.weight_engine import calculate_weights, optimal_weights

MODELS = list(DEFAULT_MODEL_FORECAST_COLUMNS)
FORECAST_COLUMNS = list(DEFAULT_MODEL_FORECAST_COLUMNS.values())
BASE_KEYS = ["target_variable", "lead_time_hours"]
LEVELS = [
    ("location_season_regime", ["location", "season", "weather_regime"]),
    ("location_season", ["location", "season"]),
    ("location", ["location"]),
    ("global", []),
]
DIURNAL_LEVELS = [
    ("location_season_hour", ["location", "season", "hour"]),
    ("location_hour", ["location", "hour"]),
]
# Candidate configurations; the workflow picks one per (variable, lead) on
# the hindcast. Mean-bias correction suits near-Gaussian errors (temperature,
# wind) but not zero-heavy rainfall, where MAE is minimised by the median.
CONFIGS = {
    "regime": {"levels": LEVELS, "bias_correct": False},
    "regime_bias": {"levels": LEVELS, "bias_correct": True},
    "diurnal_bias": {"levels": DIURNAL_LEVELS + LEVELS, "bias_correct": True},
}
METHODS = ("equal", "inverse_mae", "inverse_mse", "optimal", "best_member")
NONNEGATIVE_VARIABLES = {"precipitation_mm", "wind_speed_10m"}


def forecast_columns(models: list[str]) -> list[str]:
    return [f"{m}_forecast" for m in models]


def group_weights(forecasts: np.ndarray, actual: np.ndarray, bias_correct: bool = True, models: list[str] = MODELS) -> dict:
    """Bias and per-method weights for one condition group (columns of
    `forecasts` follow `models`)."""
    bias = (forecasts - actual[:, None]).mean(axis=0) if bias_correct else np.zeros(forecasts.shape[1])
    corrected = forecasts - bias
    err = corrected - actual[:, None]
    mae = np.abs(err).mean(axis=0)
    mse = (err ** 2).mean(axis=0)

    per_method = {
        "equal": np.full(len(models), 1.0 / len(models)),
        "inverse_mae": np.array(list(calculate_weights(dict(zip(models, mae))).values())),
        "inverse_mse": np.array(list(calculate_weights(dict(zip(models, mse))).values())),
        "optimal": optimal_weights(corrected, actual),
        # Degenerate "blend": all weight on the historically best member. Lets
        # selection fall back to one model when combining doesn't help.
        "best_member": np.eye(len(models))[int(np.argmin(mae))],
    }
    out = {"n": len(actual)}
    out.update({f"bias_{m}": b for m, b in zip(models, bias)})
    out.update({f"mae_{m}": e for m, e in zip(models, mae)})
    for method, w in per_method.items():
        out.update({f"w_{method}_{m}": v for m, v in zip(models, w)})
    return out


def skill_table(history: pd.DataFrame, keys: list[str], bias_correct: bool = True, models: list[str] = MODELS) -> pd.DataFrame:
    """group_weights for every (target_variable, lead_time_hours, *keys) group."""
    group_keys = BASE_KEYS + keys
    forecasts = history[forecast_columns(models)].to_numpy(float)
    actual = history["actual_value"].to_numpy(float)
    rows = []
    # Slice numpy arrays by group positions: far cheaper than a DataFrame per group.
    for key, idx in history.groupby(group_keys, sort=False).indices.items():
        stats = group_weights(forecasts[idx], actual[idx], bias_correct, models)
        rows.append({**dict(zip(group_keys, key if isinstance(key, tuple) else (key,))), **stats})
    return pd.DataFrame(rows)


def _param_columns(models: list[str]) -> list[str]:
    cols = ["n", *(f"bias_{m}" for m in models), *(f"mae_{m}" for m in models)]
    return cols + [f"w_{method}_{m}" for method in METHODS for m in models]


def blend_rows(
    rows: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    min_samples: int = 50,
    levels: list[tuple[str, list[str]]] = LEVELS,
    models: list[str] = MODELS,
) -> pd.DataFrame:
    """Attach the most specific usable weights to each row and blend."""
    n = len(rows)
    params = {c: np.zeros(n) for c in _param_columns(models)}
    for method in METHODS:
        for m in models:
            params[f"w_{method}_{m}"][:] = 1.0 / len(models)
    for m in models:
        params[f"mae_{m}"][:] = np.nan
    level = np.full(n, "equal_weights", dtype=object)
    assigned = np.zeros(n, dtype=bool)

    for level_name, keys in levels:
        table = tables.get(level_name)
        if table is None or table.empty:
            continue
        on = BASE_KEYS + keys
        merged = rows[on].merge(table, on=on, how="left")
        ok = ~assigned & (merged["n"].to_numpy() >= min_samples)
        if not ok.any():
            continue
        names = list(params)
        values = merged[names].to_numpy(float)[ok]
        for j, c in enumerate(names):
            params[c][ok] = values[:, j]
        level[ok] = level_name
        assigned |= ok

    out = rows.copy()
    forecasts = out[forecast_columns(models)].to_numpy(float) - np.column_stack([params[f"bias_{m}"] for m in models])
    available = ~np.isnan(forecasts)
    filled = np.where(available, forecasts, 0.0)
    nonneg = out["target_variable"].isin(NONNEGATIVE_VARIABLES).to_numpy()

    for method in METHODS:
        w = np.column_stack([params[f"w_{method}_{m}"] for m in models]) * available
        total = w.sum(axis=1)
        blended = np.where(total > 0, (w * filled).sum(axis=1) / np.where(total > 0, total, 1), np.nan)
        out[f"blended_{method}"] = np.where(nonneg, np.clip(blended, 0, None), blended)

    for c, v in params.items():
        out[c] = v
    out["n_history"] = out.pop("n").astype(int)
    out["fallback_level"] = level
    return out


def run_rolling_blend(
    archive: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    freq: str = "MS",
    min_samples: int = 50,
    bias_correct: bool = True,
    history_days: int | None = None,
    levels: list[tuple[str, list[str]]] = LEVELS,
    models: list[str] = MODELS,
) -> pd.DataFrame:
    """Blend every archived forecast issued in [start, end].

    archive: long-format lead-time dataset (lead_time_targets.csv schema)
    with a weather_regime column. Weights for issue times in each period
    come only from rows whose target time is before the period start
    (optionally limited to the trailing history_days).
    """
    archive = archive.copy()
    archive["timestamp"] = pd.to_datetime(archive["timestamp"])
    archive["hour"] = archive["timestamp"].dt.hour
    cols = forecast_columns(models)
    has_forecast = archive[cols].notna().any(axis=1)
    verified = archive[archive[cols + ["actual_value"]].notna().all(axis=1)]
    target_time = verified["timestamp"] + pd.to_timedelta(verified["lead_time_hours"], unit="h")

    edges = list(pd.date_range(pd.Timestamp(start).to_period("M").start_time, end, freq=freq))
    edges = [max(edges[0], pd.Timestamp(start))] + edges[1:] if edges else [pd.Timestamp(start)]
    edges.append(pd.Timestamp(end) + pd.Timedelta(hours=1))

    blocks = []
    for p_start, p_end in zip(edges[:-1], edges[1:]):
        rows = archive[has_forecast & (archive["timestamp"] >= p_start) & (archive["timestamp"] < p_end)]
        if rows.empty:
            continue
        history = verified[target_time < p_start]
        if history_days is not None:
            history = history[history["timestamp"] >= p_start - pd.Timedelta(days=history_days)]
        tables = {name: skill_table(history, keys, bias_correct, models) for name, keys in levels} if len(history) else {}
        block = blend_rows(rows.reset_index(drop=True), tables, min_samples, levels, models)
        block["weights_updated_at"] = p_start
        blocks.append(block)

    return pd.concat(blocks, ignore_index=True)
