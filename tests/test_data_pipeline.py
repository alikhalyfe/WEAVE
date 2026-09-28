import numpy as np
import pandas as pd
import pytest

from src.data_pipeline.preprocessing import (
    compute_wind_speed,
    kelvin_to_celsius,
    meters_to_mm,
    season_from_month,
)
from src.data_pipeline.validation import (
    validate_hourly_cadence,
    validate_lat_lon_consistency,
    validate_season_values,
    validate_time_range,
)
from src.data_pipeline.features import add_lag_features
from src.data_pipeline.targets import add_lead_time_targets, build_lead_time_forecast_dataset


def _hourly_series(n_hours, location="Pune", start="2021-01-01 00:00:00"):
    timestamps = pd.date_range(start, periods=n_hours, freq="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "location": location,
            "latitude": 18.5,
            "longitude": 73.75,
            "temperature_2m_c": np.arange(n_hours, dtype=float),
            "precipitation_mm": np.arange(n_hours, dtype=float) * 0.1,
            "wind_speed_10m": np.arange(n_hours, dtype=float) * 0.5,
            "season": "Winter",
        }
    )


def test_kelvin_to_celsius():
    assert kelvin_to_celsius(273.15) == pytest.approx(0.0)


def test_meters_to_mm():
    assert meters_to_mm(0.001) == pytest.approx(1.0)


def test_compute_wind_speed_matches_components():
    assert compute_wind_speed(3.0, 4.0) == pytest.approx(5.0)


def test_season_from_month_matches_known_mapping():
    assert season_from_month(1) == "Winter"
    assert season_from_month(7) == "Monsoon"
    assert season_from_month(10) == "Post-Monsoon"
    assert season_from_month(4) == "Summer"


def test_validate_season_values_rejects_invalid_season():
    df = _hourly_series(2)
    df.loc[0, "season"] = "NotASeason"
    with pytest.raises(ValueError):
        validate_season_values(df)


def test_validate_season_values_rejects_month_season_mismatch():
    df = _hourly_series(2)  # January rows
    df["season"] = "Monsoon"
    with pytest.raises(ValueError):
        validate_season_values(df)


def test_validate_hourly_cadence_detects_gap():
    df = _hourly_series(5)
    df = df.drop(index=2).reset_index(drop=True)
    with pytest.raises(ValueError):
        validate_hourly_cadence(df)


def test_validate_lat_lon_consistency_detects_mismatch():
    df = _hourly_series(2)
    df.loc[1, "latitude"] = 99.0
    with pytest.raises(ValueError):
        validate_lat_lon_consistency(df)


def test_validate_time_range_detects_missing_coverage():
    df = _hourly_series(5)
    with pytest.raises(ValueError):
        validate_time_range(
            df,
            expected_start=pd.Timestamp("2021-01-01 00:00:00"),
            expected_end=pd.Timestamp("2025-12-31 23:00:00"),
        )


def test_add_lag_features_looks_backward_only():
    df = _hourly_series(5)
    result = add_lag_features(df, columns=["temperature_2m_c"], lags=[1])
    assert pd.isna(result.loc[0, "temperature_2m_c_lag_1h"])
    for i in range(1, 5):
        assert result.loc[i, "temperature_2m_c_lag_1h"] == df.loc[i - 1, "temperature_2m_c"]


def test_add_lead_time_targets_matches_future_row():
    df = _hourly_series(30)
    result = add_lead_time_targets(df)
    for h in (6, 12, 24):
        for var in ("temperature_2m_c", "precipitation_mm", "wind_speed_10m"):
            col = f"{var}_target_{h}h"
            for t in range(0, 30 - h):
                assert result.loc[t, col] == pytest.approx(df.loc[t + h, var])


def test_build_lead_time_forecast_dataset_schema():
    df = _hourly_series(30)
    result = build_lead_time_forecast_dataset(df)
    expected_columns = {
        "timestamp", "location", "latitude", "longitude", "lead_time_hours",
        "target_variable", "model_a_forecast", "model_b_forecast",
        "ai_model_forecast", "actual_value", "season",
    }
    assert set(result.columns) == expected_columns
    assert result["model_a_forecast"].isna().all()
    assert result["model_b_forecast"].isna().all()
    assert result["ai_model_forecast"].isna().all()
