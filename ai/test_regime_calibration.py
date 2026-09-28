import pandas as pd
import pytest

from ai.regime_calibration import (
    build_calibration_table,
    calculate_percentile_scores,
)


def make_test_data():
    return pd.DataFrame(
        {
            "location": ["Pune"] * 8,
            "season": ["Summer"] * 8,
            "temperature_2m_c": [
                20, 22, 24, 26, 28, 30, 32, 34
            ],
            "precipitation_mm": [
                0, 0, 0.1, 0.2, 0.5, 1, 2, 5
            ],
            "wind_speed_10m": [
                1, 1.5, 2, 2.5, 3, 3.5, 4, 5
            ],
        }
    )


def test_build_calibration_table():
    df = make_test_data()

    calibration = build_calibration_table(df)

    table = calibration.table

    assert len(table) == 1

    assert table.iloc[0]["location"] == "Pune"
    assert table.iloc[0]["season"] == "Summer"

    assert "temperature_2m_c_p50" in table.columns
    assert "temperature_2m_c_p95" in table.columns
    assert "precipitation_mm_p99" in table.columns
    assert "wind_speed_10m_p90" in table.columns


def test_calibration_preserves_location_season():
    df = pd.concat(
        [
            make_test_data(),
            make_test_data().assign(
                location="Mumbai"
            ),
        ],
        ignore_index=True,
    )

    calibration = build_calibration_table(df)

    table = calibration.table

    assert len(table) == 2

    assert set(table["location"]) == {
        "Pune",
        "Mumbai",
    }


def test_calculate_percentile_scores():
    df = make_test_data()

    calibration = build_calibration_table(df)

    scored = calculate_percentile_scores(
        df,
        calibration,
    )

    assert "temperature_2m_c_percentile" in scored.columns
    assert "precipitation_mm_percentile" in scored.columns
    assert "wind_speed_10m_percentile" in scored.columns

    assert scored["temperature_2m_c_percentile"].between(
        0.0,
        1.0,
    ).all()

    assert scored["precipitation_mm_percentile"].between(
        0.0,
        1.0,
    ).all()

    assert scored["wind_speed_10m_percentile"].between(
        0.0,
        1.0,
    ).all()


def test_missing_columns_are_rejected():
    df = pd.DataFrame(
        {
            "location": ["Pune"],
            "season": ["Summer"],
        }
    )

    with pytest.raises(ValueError):
        build_calibration_table(df)