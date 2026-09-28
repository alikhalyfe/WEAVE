"""Paths and constants for the data pipeline. No other module hardcodes these."""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"

# Same 5 filenames/order as ai/generate_regimes.py.
CITY_FILES = [
    "chhatrapati_sambhajinagar_era5_2021_2025_clean.csv",
    "mumbai_era5_2021_2025_clean.csv",
    "nagpur_era5_2021_2025_clean.csv",
    "nashik_era5_2021_2025_clean.csv",
    "pune_era5_2021_2025_clean_correct.csv",
]

MASTER_CSV_PATH = PROCESSED_DIR / "era5_master_5locations_2021_2025.csv"
LEAD_TIME_TARGETS_PATH = PROCESSED_DIR / "lead_time_targets.csv"
TRAIN_CSV_PATH = PROCESSED_DIR / "train.csv"
TEST_CSV_PATH = PROCESSED_DIR / "test.csv"

TARGET_VARIABLES = ["temperature_2m_c", "precipitation_mm", "wind_speed_10m"]
LEAD_TIMES_HOURS = [6, 12, 24]
LAG_HOURS = [1, 3, 6, 12, 24]
LAG_FEATURE_COLUMNS = TARGET_VARIABLES

TRAIN_START = pd.Timestamp("2021-01-01 00:00:00")
TRAIN_END = pd.Timestamp("2024-12-31 23:00:00")
TEST_START = pd.Timestamp("2025-01-01 00:00:00")
TEST_END = pd.Timestamp("2025-12-31 23:00:00")

VALID_SEASONS = {"Winter", "Summer", "Monsoon", "Post-Monsoon"}

MONTH_TO_SEASON = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Summer", 4: "Summer", 5: "Summer",
    6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
    10: "Post-Monsoon", 11: "Post-Monsoon",
}
