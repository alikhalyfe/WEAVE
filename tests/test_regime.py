import pandas as pd

from ai.regime_calibration import CalibrationTable
from ai.regime_classifier import classify_regimes
from src.regime.classifier import classify, training_thresholds


def _df():
    ts = pd.date_range("2024-06-01", periods=6, freq="h")
    return pd.DataFrame({
        "timestamp": ts,
        "location": ["Pune"] * 3 + ["Mumbai"] * 3,
        "season": "Monsoon",
        "precipitation_mm": [0.0, 12.0, 0.0, 0.0, 0.5, 9.0],
        "temperature_2m_c": [25.0, 25.0, 38.0, 25.0, 36.0, 40.0],
        "wind_speed_10m": [2.0, 20.0, 2.0, 11.0, 2.0, 2.0],
    })


THRESHOLDS = pd.DataFrame({
    "location": ["Pune", "Mumbai"],
    "season": ["Monsoon", "Monsoon"],
    "precipitation_mm_p95": [5.0, 5.0],
    "temperature_2m_c_p95": [35.0, 35.0],
    "wind_speed_10m_p95": [10.0, 10.0],
})


def test_vectorized_classifier_matches_reference_row_classifier():
    df = _df()
    reference = classify_regimes(df, CalibrationTable(THRESHOLDS))["weather_regime"]

    result = classify(df, THRESHOLDS)

    assert result.tolist() == reference.tolist()
    assert result.tolist() == ["Normal", "Heavy Rain", "Heat", "High Wind", "Heat", "Heavy Rain"]


def test_training_thresholds_ignore_rows_after_calibration_end():
    df = _df()
    late = df.copy()
    late["timestamp"] = late["timestamp"] + pd.Timedelta(days=400)
    late["temperature_2m_c"] = 99.0

    before = training_thresholds(df, calibration_end=pd.Timestamp("2024-12-31"))
    with_late = training_thresholds(pd.concat([df, late]), calibration_end=pd.Timestamp("2024-12-31"))

    pd.testing.assert_frame_equal(before, with_late)
