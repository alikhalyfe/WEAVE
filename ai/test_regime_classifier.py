import pandas as pd
import pytest
from ai.regime_calibration import CalibrationTable

from ai.regime_classifier import (
    REGIMES,
    RegimeThresholds,
    classify_regimes,
    classify_weather_regime,
)


# Temporary thresholds used ONLY to test the classifier logic.
# These are not scientific WEAVE thresholds.
THRESHOLDS = RegimeThresholds(
    heavy_rain_mm=5.0,
    heat_temperature_c=35.0,
    high_wind_speed_ms=10.0,
)


def test_regime_names():
    assert REGIMES == (
        "Normal",
        "Heavy Rain",
        "Heat",
        "High Wind",
    )


@pytest.mark.parametrize(
    ("temperature", "precipitation", "wind", "expected"),
    [
        (25.0, 0.0, 2.0, "Normal"),
        (25.0, 10.0, 2.0, "Heavy Rain"),
        (40.0, 0.0, 2.0, "Heat"),
        (25.0, 0.0, 15.0, "High Wind"),
    ],
)
def test_classify_weather_regime(
    temperature,
    precipitation,
    wind,
    expected,
):
    row = pd.Series(
        {
            "temperature_2m_c": temperature,
            "precipitation_mm": precipitation,
            "wind_speed_10m": wind,
        }
    )

    result = classify_weather_regime(
        row,
        THRESHOLDS,
    )

    assert result == expected


def test_heavy_rain_has_priority():
    row = pd.Series(
        {
            "temperature_2m_c": 40.0,
            "precipitation_mm": 10.0,
            "wind_speed_10m": 15.0,
        }
    )

    result = classify_weather_regime(
        row,
        THRESHOLDS,
    )

    assert result == "Heavy Rain"


def test_classify_regimes_adds_column():
    df = pd.DataFrame(
        [
            {
                "location": "Pune",
                "season": "Summer",
                "temperature_2m_c": 25.0,
                "precipitation_mm": 0.0,
                "wind_speed_10m": 2.0,
            },
            {
                "location": "Pune",
                "season": "Summer",
                "temperature_2m_c": 40.0,
                "precipitation_mm": 0.0,
                "wind_speed_10m": 2.0,
            },
        ]
    )

    calibration = CalibrationTable(
        table=pd.DataFrame(
            [
                {
                    "location": "Pune",
                    "season": "Summer",
                    "precipitation_mm_p95": 5.0,
                    "temperature_2m_c_p95": 35.0,
                    "wind_speed_10m_p95": 10.0,
                }
            ]
        )
    )

    result = classify_regimes(
        df,
        calibration,
    )

    assert "weather_regime" in result.columns
    assert result["weather_regime"].tolist() == [
        "Normal",
        "Heat",
    ]