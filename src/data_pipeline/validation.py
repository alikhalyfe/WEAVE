"""Extra dataset checks beyond what ai.data_loader.load_weather_data already
validates (required columns, timestamp parsing, missing values, duplicates,
numeric dtypes, precipitation sign, wind-speed/u10/v10 consistency)."""

import pandas as pd

from src.data_pipeline import config


def validate_time_range(
    df: pd.DataFrame,
    expected_start: pd.Timestamp = config.TRAIN_START,
    expected_end: pd.Timestamp = config.TEST_END,
) -> None:
    for location, group in df.groupby("location"):
        start, end = group["timestamp"].min(), group["timestamp"].max()
        if start != expected_start or end != expected_end:
            raise ValueError(
                f"Location '{location}' time range is {start} -> {end}, "
                f"expected {expected_start} -> {expected_end}."
            )


def validate_hourly_cadence(df: pd.DataFrame) -> None:
    for location, group in df.groupby("location"):
        diffs = group.sort_values("timestamp")["timestamp"].diff().dropna()
        bad = diffs[diffs != pd.Timedelta(hours=1)]
        if not bad.empty:
            raise ValueError(
                f"Location '{location}' has {len(bad)} non-hourly gap(s) "
                f"in its timestamp series."
            )


def validate_lat_lon_consistency(df: pd.DataFrame) -> None:
    for location, group in df.groupby("location"):
        if group["latitude"].nunique() != 1 or group["longitude"].nunique() != 1:
            raise ValueError(
                f"Location '{location}' has inconsistent latitude/longitude values."
            )


def validate_season_values(df: pd.DataFrame) -> None:
    invalid = ~df["season"].isin(config.VALID_SEASONS)
    if invalid.any():
        bad_values = sorted(df.loc[invalid, "season"].unique())
        raise ValueError(f"Dataset contains invalid season values: {bad_values}")

    expected_season = df["timestamp"].dt.month.map(config.MONTH_TO_SEASON)
    mismatched = df["season"] != expected_season
    if mismatched.any():
        raise ValueError(
            f"Dataset contains {mismatched.sum()} row(s) where 'season' does "
            f"not match the month it falls in."
        )


def validate_dataset(
    df: pd.DataFrame,
    expected_start: pd.Timestamp = config.TRAIN_START,
    expected_end: pd.Timestamp = config.TEST_END,
) -> None:
    validate_time_range(df, expected_start, expected_end)
    validate_hourly_cadence(df)
    validate_lat_lon_consistency(df)
    validate_season_values(df)
