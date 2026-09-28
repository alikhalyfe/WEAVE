import numpy as np
import pandas as pd

from ai.data_loader import REQUIRED_COLUMNS, load_weather_data
from src.data_pipeline import config
from src.data_pipeline.features import engineer_all_features
from src.data_pipeline.master import build_master_dataset
from src.data_pipeline.split import split_by_time, split_lead_time_dataset
from src.data_pipeline.targets import add_lead_time_targets


def test_master_dataset_loadable_by_ai_data_loader(tmp_path):
    df = build_master_dataset()
    out_path = tmp_path / "era5_master_5locations_2021_2025.csv"
    df.to_csv(out_path, index=False)

    reloaded = load_weather_data(out_path)

    assert set(reloaded.columns) == REQUIRED_COLUMNS
    assert len(reloaded) == len(df)


def test_split_by_time_boundaries():
    timestamps = pd.date_range("2024-12-30", periods=48, freq="h")
    df = pd.DataFrame({"timestamp": timestamps, "value": range(48)})

    train, test = split_by_time(df)

    assert (train["timestamp"] <= config.TRAIN_END).all()
    assert (test["timestamp"] >= config.TEST_START).all()
    assert set(train.index).isdisjoint(set(test.index))


def test_split_lead_time_dataset_no_leakage():
    df = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2024-12-31 16:00:00"),  # target 22:00, ok
                pd.Timestamp("2024-12-31 20:00:00"),  # target 2025-01-01 02:00, must be excluded
                pd.Timestamp("2025-01-01 00:00:00"),  # test period
            ],
            "lead_time_hours": [6, 6, 6],
        }
    )

    train, test = split_lead_time_dataset(df)

    target_time = train["timestamp"] + pd.to_timedelta(train["lead_time_hours"], unit="h")
    assert (target_time <= config.TRAIN_END).all()
    assert len(train) == 1
    assert len(test) == 1


def test_run_pipeline_smoke():
    master_df = build_master_dataset()
    assert len(master_df) == 219_120

    features_df = engineer_all_features(master_df)
    assert "temperature_2m_c_lag_24h" in features_df.columns
    assert "day_of_year" in features_df.columns

    targets_df = add_lead_time_targets(master_df)
    assert "temperature_2m_c_target_6h" in targets_df.columns
