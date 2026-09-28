"""Adaptive blending: conditional model-skill weighting on top of the
existing inverse-MAE engine (weight_engine.calculate_weights /
blender.blend_forecasts, both reused unmodified).

Historical model skill (MAE) is looked up through a fallback hierarchy,
most specific to least specific:

    location + season + lead_time_hours + weather_regime
    location + season + lead_time_hours
    location + season
    location
    global (all historical data)
    equal weights (no usable historical data at any level)

A level is only accepted once it has enough historical (forecast, actual)
pairs for EVERY model being blended -- comparing one model's narrow-condition
skill against another model's only-ever-computed-globally skill would be an
apples-to-oranges weight comparison, so a level with partial coverage is
rejected and the ladder falls through to a broader one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.blending.blender import blend_forecasts
from src.blending.weight_engine import calculate_weights
from src.evaluation.metrics import mae

DEFAULT_MODEL_FORECAST_COLUMNS = {
    "model_a": "model_a_forecast",
    "model_b": "model_b_forecast",
    "ai_model": "ai_model_forecast",
}

FALLBACK_LEVELS = [
    ("location_season_lead_regime", ("location", "season", "lead_time_hours", "weather_regime")),
    ("location_season_lead", ("location", "season", "lead_time_hours")),
    ("location_season", ("location", "season")),
    ("location", ("location",)),
    ("global", ()),
]


def _jsonify(value):
    """Unwrap numpy scalars (np.float64/np.int64/...) to plain Python types
    so the result dict this module returns is safe to json.dumps() as-is."""
    return value.item() if isinstance(value, np.generic) else value


def attach_weather_regime(
    historical_data: pd.DataFrame,
    regime_data: pd.DataFrame,
    on: list[str] = ["timestamp", "location"],
) -> pd.DataFrame:
    """Left-join weather_regime onto historical_data on timestamp+location.

    Call this once when assembling historical_data, before select_adaptive_
    weights/adaptive_blend -- keeps those functions pandas-pure and testable
    without needing weather_regimes.csv. Rows with no regime match get NaN,
    which the fallback ladder already treats as unusable at that level.
    """
    return historical_data.merge(regime_data[[*on, "weather_regime"]], on=on, how="left")


def filter_historical_data(historical_data: pd.DataFrame, **conditions) -> pd.DataFrame:
    """Boolean-mask historical_data on each non-None condition whose key is
    an existing column. An unknown location/season/regime naturally yields
    an empty frame here -- no crash, just 0 rows for that level."""
    df = historical_data
    for key, value in conditions.items():
        if value is None or key not in df.columns:
            continue
        df = df[df[key] == value]
    return df


def calculate_historical_errors(
    historical_data: pd.DataFrame,
    models: list[str],
    actual_col: str = "actual_value",
    model_forecast_columns: dict[str, str] | None = None,
    cutoff_timestamp: str | pd.Timestamp | None = None,
    timestamp_col: str = "timestamp",
    min_samples: int = 10,
) -> dict[str, float]:
    """MAE per model on historical_data, reusing evaluation.metrics.mae.

    A model is included only if it has >= min_samples rows where both its
    forecast column and actual_col are non-null after the cutoff filter --
    this single check doubles as leakage guard (no rows at/after cutoff_
    timestamp are ever used) and sparse-data guard.
    """
    model_forecast_columns = model_forecast_columns or DEFAULT_MODEL_FORECAST_COLUMNS
    df = historical_data
    if cutoff_timestamp is not None:
        df = df[pd.to_datetime(df[timestamp_col]) < pd.to_datetime(cutoff_timestamp)]

    errors: dict[str, float] = {}
    for model in models:
        col = model_forecast_columns.get(model, f"{model}_forecast")
        if col not in df.columns or actual_col not in df.columns:
            continue
        pair = df[[col, actual_col]].dropna()
        if len(pair) < min_samples:
            continue
        errors[model] = float(mae(pair[actual_col], pair[col]))
    return errors


def select_adaptive_weights(
    historical_data: pd.DataFrame,
    models: list[str],
    location: str | None = None,
    season: str | None = None,
    lead_time_hours: float | None = None,
    weather_regime: str | None = None,
    model_forecast_columns: dict[str, str] | None = None,
    actual_col: str = "actual_value",
    cutoff_timestamp: str | pd.Timestamp | None = None,
    timestamp_col: str = "timestamp",
    min_samples: int = 10,
    epsilon: float = 1e-6,
) -> tuple[dict[str, float], dict[str, float], str]:
    """Walk FALLBACK_LEVELS most-to-least specific and return the first
    level with historical MAE for every model in `models`.

    Returns (weights, errors, fallback_level_name). If no level has usable
    history for all models (e.g. no forecasts have been produced yet),
    returns equal weights, empty errors, and level "equal_weights".
    """
    condition_values = {
        "location": location,
        "season": season,
        "lead_time_hours": lead_time_hours,
        "weather_regime": weather_regime,
    }

    for level_name, keys in FALLBACK_LEVELS:
        if "weather_regime" in keys and (
            weather_regime is None or "weather_regime" not in historical_data.columns
        ):
            continue

        subset = filter_historical_data(
            historical_data, **{k: condition_values[k] for k in keys}
        )
        errors = calculate_historical_errors(
            subset, models, actual_col, model_forecast_columns,
            cutoff_timestamp, timestamp_col, min_samples,
        )
        if set(errors) == set(models):
            return calculate_weights(errors, epsilon), errors, level_name

    equal = {m: 1.0 / len(models) for m in models}
    return equal, {}, "equal_weights"


def adaptive_blend(
    forecasts: dict[str, float],
    historical_data: pd.DataFrame,
    location: str | None = None,
    season: str | None = None,
    lead_time_hours: float | None = None,
    weather_regime: str | None = None,
    target_variable: str | None = None,
    model_forecast_columns: dict[str, str] | None = None,
    actual_col: str = "actual_value",
    timestamp_col: str = "timestamp",
    cutoff_timestamp: str | pd.Timestamp | None = None,
    min_samples: int = 10,
    epsilon: float = 1e-6,
) -> dict:
    """Pick adaptive weights, then blend_forecasts(). Returns a plain-
    JSON-safe dict: {blended_forecast, weights, errors, conditions,
    fallback_level}.
    """
    usable_forecasts = {
        m: v for m, v in forecasts.items() if v is not None and not pd.isna(v)
    }
    if not usable_forecasts:
        raise ValueError("adaptive_blend: no non-null forecast values were provided")
    models = list(usable_forecasts.keys())

    data = historical_data
    if target_variable is not None and "target_variable" in data.columns:
        data = data[data["target_variable"] == target_variable]

    weights, errors, fallback_level = select_adaptive_weights(
        data, models, location, season, lead_time_hours, weather_regime,
        model_forecast_columns, actual_col, cutoff_timestamp, timestamp_col,
        min_samples, epsilon,
    )
    blended = blend_forecasts(usable_forecasts, weights)

    return {
        "blended_forecast": _jsonify(blended),
        "weights": {m: _jsonify(w) for m, w in weights.items()},
        "errors": {m: _jsonify(e) for m, e in errors.items()},
        "conditions": {
            "location": location,
            "season": season,
            "lead_time_hours": _jsonify(lead_time_hours),
            "weather_regime": weather_regime,
            "target_variable": target_variable,
        },
        "fallback_level": fallback_level,
    }
