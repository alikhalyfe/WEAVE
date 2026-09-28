"""Chronological train/test split (Task 6). Never shuffles."""

import pandas as pd

from src.data_pipeline import config


def split_by_time(
    df: pd.DataFrame,
    train_end: pd.Timestamp = config.TRAIN_END,
    test_start: pd.Timestamp = config.TEST_START,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simple boundary split for the feature dataset (no future offset)."""
    train = df[df["timestamp"] <= train_end].copy()
    test = df[df["timestamp"] >= test_start].copy()
    return train, test


def split_lead_time_dataset(
    df: pd.DataFrame,
    train_end: pd.Timestamp = config.TRAIN_END,
    test_start: pd.Timestamp = config.TEST_START,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Leakage-safe split for the long-format lead-time dataset.

    A row's target comes from timestamp + lead_time_hours. A train-period
    row whose target falls after train_end is excluded from train -- its
    label would otherwise be test-period data.
    """
    target_time = df["timestamp"] + pd.to_timedelta(df["lead_time_hours"], unit="h")
    train = df[(df["timestamp"] <= train_end) & (target_time <= train_end)].copy()
    test = df[df["timestamp"] >= test_start].copy()
    return train, test
