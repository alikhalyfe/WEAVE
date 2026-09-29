"""Builds the features+targets modeling dataset by composing Member 1's
existing pipeline functions (no data loading/feature/target logic is
duplicated here) and applies a leakage-safe train/test split per lead time.
"""

import numpy as np
import pandas as pd

from src.data_pipeline import config
from src.data_pipeline.features import engineer_all_features
from src.data_pipeline.master import build_master_dataset
from src.data_pipeline.targets import add_lead_time_targets

# Numeric feature columns produced by engineer_all_features(), excluding
# identifiers (timestamp, location) and the categorical `season` column.
FEATURE_COLUMNS = [
    "temperature_2m_c", "precipitation_mm", "u10", "v10", "wind_speed_10m",
    "hour", "day_of_week", "month", "day_of_year",
    "precipitation_3h", "temperature_3h_mean", "wind_speed_3h_mean",
    "temperature_change_1h", "precipitation_change_1h", "wind_change_1h",
] + [
    f"{col}_lag_{n}h"
    for col in config.LAG_FEATURE_COLUMNS
    for n in config.LAG_HOURS
]

# Extra predictors (all backward-looking, computed per location):
# * lag 18 h -- for a 6 h lead this is "same hour yesterday" relative to the
#   target time, the strongest diurnal analogue a forecaster has;
# * 24 h rolling mean / max / sum -- the day so far;
# * cyclic hour and day-of-year encodings, so 23:00 sits next to 00:00;
# * a location code, letting trees learn site-specific behaviour.
EXTRA_FEATURE_COLUMNS = [
    *(f"{col}_lag_18h" for col in config.LAG_FEATURE_COLUMNS),
    "temperature_24h_mean", "temperature_24h_max", "precipitation_24h_sum", "wind_speed_24h_mean",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos", "location_code",
]
FEATURE_COLUMNS = FEATURE_COLUMNS + EXTRA_FEATURE_COLUMNS


def add_extra_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["location", "timestamp"]).copy()
    g = df.groupby("location", sort=False)
    for col in config.LAG_FEATURE_COLUMNS:
        df[f"{col}_lag_18h"] = g[col].shift(18)
    roll = lambda col, fn: g[col].transform(lambda x: getattr(x.rolling(24, min_periods=1), fn)())  # noqa: E731
    df["temperature_24h_mean"] = roll("temperature_2m_c", "mean")
    df["temperature_24h_max"] = roll("temperature_2m_c", "max")
    df["precipitation_24h_sum"] = roll("precipitation_mm", "sum")
    df["wind_speed_24h_mean"] = roll("wind_speed_10m", "mean")
    df["hour_sin"], df["hour_cos"] = np.sin(2 * np.pi * df["hour"] / 24), np.cos(2 * np.pi * df["hour"] / 24)
    df["doy_sin"], df["doy_cos"] = np.sin(2 * np.pi * df["day_of_year"] / 366), np.cos(2 * np.pi * df["day_of_year"] / 366)
    df["location_code"] = df["location"].astype("category").cat.codes
    return df


def build_modeling_dataset() -> pd.DataFrame:
    """Master ERA5 data -> engineered features + lead-time target columns,
    one row per timestamp x location (wide format)."""
    master_df = build_master_dataset()
    features_df = add_extra_features(engineer_all_features(master_df))
    targets_df = add_lead_time_targets(master_df)

    target_columns = [
        f"{var}_target_{h}h"
        for var in config.TARGET_VARIABLES
        for h in config.LEAD_TIMES_HOURS
    ]
    return features_df.merge(
        targets_df[["location", "timestamp", *target_columns]],
        on=["location", "timestamp"],
        how="left",
    )


def get_leakage_safe_train_test(
    modeling_df: pd.DataFrame,
    lead_time_hours: int,
    train_end: pd.Timestamp = config.TRAIN_END,
    test_start: pd.Timestamp = config.TEST_START,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train rows must have their target (timestamp + lead_time_hours)
    landing at or before train_end -- otherwise the label would be a
    test-period observation. Test rows just need timestamp >= test_start;
    predictions there don't require the label to exist."""
    target_time = modeling_df["timestamp"] + pd.to_timedelta(lead_time_hours, unit="h")
    train_df = modeling_df[(modeling_df["timestamp"] <= train_end) & (target_time <= train_end)]
    test_df = modeling_df[modeling_df["timestamp"] >= test_start]
    return train_df, test_df
