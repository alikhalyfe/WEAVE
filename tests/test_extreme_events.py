from src.evaluation.extreme_events import (
    classify_heavy_rain,
    classify_heat,
    classify_high_wind,
    event_metrics
)


def test_heavy_rain():
    assert list(classify_heavy_rain([10, 50, 80])) == [False, True, True]


def test_heat():
    assert list(classify_heat([30, 35, 40])) == [False, True, True]


def test_high_wind():
    assert list(classify_high_wind([5, 15, 20])) == [False, True, True]


def test_event_metrics():
    result = event_metrics(
        [1, 1, 0, 1],
        [1, 0, 0, 1]
    )

    assert result["precision"] == 1.0
    assert round(result["recall"], 2) == 0.67
    assert round(result["f1"], 2) == 0.80
    assert round(result["csi"], 2) == 0.67