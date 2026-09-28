"""Feature engineering: wraps ai.feature_engineering.engineer_features and
adds day_of_year plus backward-looking lag features (Task 3)."""

import pandas as pd

from ai.feature_engineering import engineer_features
from src.data_pipeline import config


def add_day_of_year(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    return df


def add_lag_features(
    df: pd.DataFrame,
    columns: list[str] = config.LAG_FEATURE_COLUMNS,
    lags: list[int] = config.LAG_HOURS,
) -> pd.DataFrame:
    """Adds {col}_lag_{n}h = value from n hours ago, per location.

    Uses a positive shift only -- a lag must never look into the future.
    Rows within the first `n` hours of a location's series get NaN rather
    than a fabricated fill value.
    """
    df = df.copy()
    grouped = df.groupby("location", sort=False)
    for col in columns:
        for n in lags:
            df[f"{col}_lag_{n}h"] = grouped[col].shift(n)
    return df


def engineer_all_features(df: pd.DataFrame) -> pd.DataFrame:
    df = engineer_features(df)
    df = add_day_of_year(df)
    df = add_lag_features(df)
    return df
