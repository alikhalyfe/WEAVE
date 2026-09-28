"""Vectorized, leakage-safe weather regime classification.

Same rules and priority as ai.regime_classifier.classify_weather_regime
(Heavy Rain > Heat > High Wind > Normal, thresholds = location x season p95
from ai.regime_calibration), but:

* calibration is built from the training period only, so 2025 regimes never
  depend on 2025 percentiles;
* thresholds are merged on and applied with np.select instead of a per-row
  apply (~200x faster on the 219k-row master dataset).
"""

import numpy as np
import pandas as pd

from ai.regime_calibration import build_calibration_table
from src.data_pipeline import config

THRESHOLD_COLUMNS = {
    "precipitation_mm": "precipitation_mm_p95",
    "temperature_2m_c": "temperature_2m_c_p95",
    "wind_speed_10m": "wind_speed_10m_p95",
}


def training_thresholds(df: pd.DataFrame, calibration_end: pd.Timestamp = config.TRAIN_END) -> pd.DataFrame:
    """location x season p95 thresholds from rows at/before calibration_end."""
    table = build_calibration_table(df[df["timestamp"] <= calibration_end]).table
    return table[["location", "season", *THRESHOLD_COLUMNS.values()]]


def classify(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.Series:
    """Weather regime per row of df (needs location, season and the three
    weather variables). Returned Series is aligned to df.index."""
    t = df[["location", "season"]].merge(thresholds, on=["location", "season"], how="left")
    t.index = df.index
    rain = (df["precipitation_mm"] > 0) & (df["precipitation_mm"] >= t["precipitation_mm_p95"])
    heat = df["temperature_2m_c"] >= t["temperature_2m_c_p95"]
    wind = df["wind_speed_10m"] >= t["wind_speed_10m_p95"]
    return pd.Series(
        np.select([rain, heat, wind], ["Heavy Rain", "Heat", "High Wind"], default="Normal"),
        index=df.index,
        name="weather_regime",
    )


def build_regimes(master_df: pd.DataFrame, calibration_end: pd.Timestamp = config.TRAIN_END) -> pd.DataFrame:
    """timestamp, location, weather_regime for every master row."""
    out = master_df[["timestamp", "location"]].copy()
    out["weather_regime"] = classify(master_df, training_thresholds(master_df, calibration_end))
    return out
