"""Builds the canonical 5-location master dataset (Task 9), reusing
ai.data_loader for loading/combining/base validation and adding the extra
checks from validation.py."""

from pathlib import Path

import pandas as pd

from ai.data_loader import load_multiple_city_data
from src.data_pipeline import config, validation


def build_master_dataset() -> pd.DataFrame:
    """Loads and validates the 5 city CSVs. Returns exactly
    ai.data_loader.REQUIRED_COLUMNS -- nothing extra -- so the written CSV
    round-trips through ai.data_loader.load_weather_data with zero adapter
    code (Task 8)."""
    df = load_multiple_city_data(config.DATA_DIR, config.CITY_FILES)
    validation.validate_dataset(df)
    return df


def write_master_dataset(
    df: pd.DataFrame, path: Path = config.MASTER_CSV_PATH
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
