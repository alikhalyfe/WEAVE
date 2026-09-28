"""Lead-time ACTUAL future targets (Task 4) and the long-format forecast
dataset interface Member 2 will later fill with model predictions (Task 5).

No forecast values are fabricated here -- model_a_forecast, model_b_forecast
and ai_model_forecast are always NaN placeholders.
"""

import numpy as np
import pandas as pd

from src.data_pipeline import config


def add_lead_time_targets(
    df: pd.DataFrame,
    variables: list[str] = config.TARGET_VARIABLES,
    lead_hours: list[int] = config.LEAD_TIMES_HOURS,
) -> pd.DataFrame:
    """Adds {var}_target_{h}h = actual value h hours ahead, per location.

    Requires df sorted by [location, timestamp] and strictly hourly per
    location (guaranteed once validation.validate_hourly_cadence passes).
    Rows within the last `h` hours of a location's series get NaN -- the
    future observation doesn't exist yet, which is real information, not
    a value to fabricate or drop.
    """
    df = df.copy()
    grouped = df.groupby("location", sort=False)
    for var in variables:
        for h in lead_hours:
            df[f"{var}_target_{h}h"] = grouped[var].shift(-h)
    return df


def build_lead_time_forecast_dataset(
    df: pd.DataFrame,
    variables: list[str] = config.TARGET_VARIABLES,
    lead_hours: list[int] = config.LEAD_TIMES_HOURS,
) -> pd.DataFrame:
    """Melts add_lead_time_targets()'s wide target columns into the shared
    long-format schema Member 2 (and others) will append forecasts to."""
    df = add_lead_time_targets(df, variables, lead_hours)

    rows = []
    for var in variables:
        for h in lead_hours:
            chunk = df[["timestamp", "location", "latitude", "longitude", "season"]].copy()
            chunk["lead_time_hours"] = h
            chunk["target_variable"] = var
            chunk["actual_value"] = df[f"{var}_target_{h}h"]
            rows.append(chunk)

    result = pd.concat(rows, ignore_index=True)
    result["model_a_forecast"] = np.nan
    result["model_b_forecast"] = np.nan
    result["ai_model_forecast"] = np.nan

    return result[
        [
            "timestamp",
            "location",
            "latitude",
            "longitude",
            "lead_time_hours",
            "target_variable",
            "model_a_forecast",
            "model_b_forecast",
            "ai_model_forecast",
            "actual_value",
            "season",
        ]
    ]
