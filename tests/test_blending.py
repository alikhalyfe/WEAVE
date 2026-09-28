import pandas as pd
import pytest

from src.blending.blender import blend_forecasts
from src.blending.weight_engine import calculate_weights
from src.blending.adaptive_blender import adaptive_blend


# ---------------------------------------------------------------------------
# Existing primitives (weight_engine.calculate_weights / blender.blend_forecasts)
# ---------------------------------------------------------------------------

def test_calculate_weights_and_blend_parity_with_original_demo():
    model_errors = {"model_a": 10, "model_b": 20, "ai_model": 5}
    forecasts = {"model_a": 80, "model_b": 70, "ai_model": 90}

    weights = calculate_weights(model_errors)
    blended = blend_forecasts(forecasts, weights)

    assert weights["model_a"] == pytest.approx(0.286, abs=0.001)
    assert weights["model_b"] == pytest.approx(0.143, abs=0.001)
    assert weights["ai_model"] == pytest.approx(0.571, abs=0.001)
    assert blended == pytest.approx(84.29, abs=0.01)


def test_calculate_weights_is_inverse_mae():
    equal = calculate_weights({"a": 10, "b": 10})
    assert equal["a"] == pytest.approx(equal["b"])

    asymmetric = calculate_weights({"a": 5, "b": 20})
    assert asymmetric["a"] == pytest.approx((1 / 5) / (1 / 5 + 1 / 20))


def test_weights_sum_to_one():
    weights = calculate_weights({"a": 3, "b": 7, "c": 1, "d": 15})
    assert sum(weights.values()) == pytest.approx(1.0)


def test_lower_error_gets_higher_weight():
    weights = calculate_weights({"a": 5, "b": 20})
    assert weights["a"] > weights["b"]


def test_blend_forecasts_matches_manual_weighted_sum():
    forecasts = {"a": 10, "b": 20}
    weights = {"a": 0.25, "b": 0.75}
    assert blend_forecasts(forecasts, weights) == pytest.approx(10 * 0.25 + 20 * 0.75)


# ---------------------------------------------------------------------------
# adaptive_blend -- synthetic test-only fixtures, small and deterministic
# ---------------------------------------------------------------------------

def _row(timestamp, location, season, lead_time_hours, model_a, model_b, actual, weather_regime=None):
    row = {
        "timestamp": timestamp,
        "location": location,
        "season": season,
        "lead_time_hours": lead_time_hours,
        "model_a_forecast": model_a,
        "model_b_forecast": model_b,
        "actual_value": actual,
    }
    if weather_regime is not None:
        row["weather_regime"] = weather_regime
    return row


def test_adaptive_blend_selects_by_location():
    rows = []
    for i in range(5):
        # Pune: model_a is accurate, model_b is way off.
        rows.append(_row(f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 50 + i, 90, 50 + i))
        # Mumbai: model_b is accurate, model_a is way off.
        rows.append(_row(f"2021-01-0{i+1} 00:00:00", "Mumbai", "Monsoon", 6, 90, 50 + i, 50 + i))
    historical = pd.DataFrame(rows)

    pune_result = adaptive_blend(
        {"model_a": 50, "model_b": 90}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6, min_samples=3,
    )
    mumbai_result = adaptive_blend(
        {"model_a": 90, "model_b": 50}, historical,
        location="Mumbai", season="Monsoon", lead_time_hours=6, min_samples=3,
    )

    assert pune_result["weights"]["model_a"] > pune_result["weights"]["model_b"]
    assert mumbai_result["weights"]["model_b"] > mumbai_result["weights"]["model_a"]


def test_adaptive_blend_selects_by_season():
    rows = []
    for i in range(5):
        rows.append(_row(f"2021-0{1}-0{i+1} 00:00:00", "Pune", "Winter", 6, 50 + i, 90, 50 + i))
        rows.append(_row(f"2021-0{6}-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 90, 50 + i, 50 + i))
    historical = pd.DataFrame(rows)

    winter_result = adaptive_blend(
        {"model_a": 50, "model_b": 90}, historical,
        location="Pune", season="Winter", lead_time_hours=6, min_samples=3,
    )
    monsoon_result = adaptive_blend(
        {"model_a": 90, "model_b": 50}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6, min_samples=3,
    )

    assert winter_result["weights"]["model_a"] > winter_result["weights"]["model_b"]
    assert monsoon_result["weights"]["model_b"] > monsoon_result["weights"]["model_a"]


def test_adaptive_blend_selects_by_lead_time():
    rows = []
    for i in range(5):
        rows.append(_row(f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 50 + i, 90, 50 + i))
        # A non-6/12/24 lead time, proving arbitrary numeric lead times work.
        rows.append(_row(f"2021-01-0{i+1} 06:00:00", "Pune", "Monsoon", 18, 90, 50 + i, 50 + i))
    historical = pd.DataFrame(rows)

    lead6_result = adaptive_blend(
        {"model_a": 50, "model_b": 90}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6, min_samples=3,
    )
    lead18_result = adaptive_blend(
        {"model_a": 90, "model_b": 50}, historical,
        location="Pune", season="Monsoon", lead_time_hours=18, min_samples=3,
    )

    assert lead6_result["weights"]["model_a"] > lead6_result["weights"]["model_b"]
    assert lead18_result["weights"]["model_b"] > lead18_result["weights"]["model_a"]


def test_adaptive_blend_selects_by_weather_regime():
    rows = []
    for i in range(3):
        rows.append(_row(
            f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6,
            50 + i, 90, 50 + i, weather_regime="Heavy Rain",
        ))
        rows.append(_row(
            f"2021-01-0{i+1} 12:00:00", "Pune", "Monsoon", 6,
            90, 50 + i, 50 + i, weather_regime="Normal",
        ))
    historical = pd.DataFrame(rows)

    rain_result = adaptive_blend(
        {"model_a": 50, "model_b": 90}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6,
        weather_regime="Heavy Rain", min_samples=3,
    )
    normal_result = adaptive_blend(
        {"model_a": 90, "model_b": 50}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6,
        weather_regime="Normal", min_samples=3,
    )

    assert rain_result["fallback_level"] == "location_season_lead_regime"
    assert normal_result["fallback_level"] == "location_season_lead_regime"
    assert rain_result["weights"]["model_a"] > rain_result["weights"]["model_b"]
    assert normal_result["weights"]["model_b"] > normal_result["weights"]["model_a"]


def test_adaptive_blend_falls_back_when_specific_level_too_sparse():
    rows = [
        # Only 2 rows for Pune+Monsoon+6h -- below min_samples=3.
        _row("2021-01-01 00:00:00", "Pune", "Monsoon", 6, 50, 50, 50),
        _row("2021-01-02 00:00:00", "Pune", "Monsoon", 6, 50, 50, 50),
        # 2 more Pune rows under a different season/lead -- bring the
        # location-only pool to 4, enough to satisfy min_samples.
        _row("2021-02-01 00:00:00", "Pune", "Summer", 12, 50, 50, 50),
        _row("2021-02-02 00:00:00", "Pune", "Summer", 12, 50, 50, 50),
    ]
    historical = pd.DataFrame(rows)

    result = adaptive_blend(
        {"model_a": 50, "model_b": 50}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6, min_samples=3,
    )

    assert result["fallback_level"] == "location"


def test_adaptive_blend_equal_weights_when_no_history_available():
    # Mirrors the real current state of data/processed/lead_time_targets.csv:
    # forecast columns exist but are entirely empty.
    rows = [
        _row("2021-01-01 00:00:00", "Pune", "Monsoon", 6, None, None, 50),
        _row("2021-01-02 00:00:00", "Pune", "Monsoon", 6, None, None, 51),
    ]
    historical = pd.DataFrame(rows)

    result = adaptive_blend(
        {"model_a": 40, "model_b": 60}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6,
    )

    assert result["fallback_level"] == "equal_weights"
    assert result["weights"] == {"model_a": 0.5, "model_b": 0.5}
    assert result["blended_forecast"] == pytest.approx(50.0)


def test_adaptive_blend_ignores_missing_forecast_value():
    rows = [_row(f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 50 + i, 50 + i, 50 + i) for i in range(4)]
    historical = pd.DataFrame(rows)

    result = adaptive_blend(
        {"model_a": 80, "model_b": None}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6, min_samples=3,
    )

    assert "model_b" not in result["weights"]
    assert result["weights"]["model_a"] == pytest.approx(1.0)
    assert result["blended_forecast"] == pytest.approx(80.0)


def test_adaptive_blend_unknown_regime_falls_through_gracefully():
    rows = [
        _row(f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 50 + i, 50 + i, 50 + i, weather_regime="Normal")
        for i in range(4)
    ]
    historical = pd.DataFrame(rows)

    result = adaptive_blend(
        {"model_a": 50, "model_b": 50}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6,
        weather_regime="Tornado", min_samples=3,
    )

    assert result["fallback_level"] != "location_season_lead_regime"
    assert "model_a" in result["weights"]


def test_adaptive_blend_zero_error_model_dominates():
    rows = [
        _row(f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 50 + i, 90, 50 + i)
        for i in range(4)
    ]
    historical = pd.DataFrame(rows)

    result = adaptive_blend(
        {"model_a": 50, "model_b": 90}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6, min_samples=3,
    )

    assert result["weights"]["model_a"] > 0.999
    assert result["blended_forecast"] == pytest.approx(50.0, abs=0.1)


def test_adaptive_blend_cutoff_excludes_future_rows():
    early_rows = [
        _row(f"2021-01-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 50 + i, 90, 50 + i)
        for i in range(3)
    ]
    late_rows = [
        _row(f"2021-02-0{i+1} 00:00:00", "Pune", "Monsoon", 6, 90, 50 + i, 50 + i)
        for i in range(5)
    ]
    historical = pd.DataFrame(early_rows + late_rows)

    result = adaptive_blend(
        {"model_a": 50, "model_b": 90}, historical,
        location="Pune", season="Monsoon", lead_time_hours=6,
        cutoff_timestamp="2021-02-01 00:00:00", min_samples=3,
    )

    assert result["weights"]["model_a"] > result["weights"]["model_b"]
