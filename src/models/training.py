"""Builds the features+targets modeling dataset by composing Member 1's
existing pipeline functions (no data loading/feature/target logic is
duplicated here) and applies a leakage-safe train/test split per lead time.
"""

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


def build_modeling_dataset() -> pd.DataFrame:
    """Master ERA5 data -> engineered features + lead-time target columns,
    one row per timestamp x location (wide format)."""
    master_df = build_master_dataset()
    features_df = engineer_all_features(master_df)
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
