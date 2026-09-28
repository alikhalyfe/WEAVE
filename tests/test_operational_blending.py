import numpy as np
import pandas as pd

from src.blending.operational import METHODS, MODELS, run_rolling_blend
from src.blending.weight_engine import optimal_weights


def _archive(days=90, seed=0):
    """One location, one variable, 6h lead. ai_model is accurate, model_b is
    noisy and model_a is biased by +3 -- so skill ordering is known."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-01", periods=days * 24, freq="h")
    actual = 20 + 5 * np.sin(np.arange(len(ts)) / 24 * 2 * np.pi)
    return pd.DataFrame({
        "timestamp": ts,
        "location": "Pune",
        "season": "Winter",
        "weather_regime": "Normal",
        "lead_time_hours": 6,
        "target_variable": "temperature_2m_c",
        "model_a_forecast": actual + 3 + rng.normal(0, 0.3, len(ts)),
        "model_b_forecast": actual + rng.normal(0, 2.0, len(ts)),
        "ai_model_forecast": actual + rng.normal(0, 0.3, len(ts)),
        "actual_value": actual,
    })


def test_optimal_weights_recovers_single_perfect_model():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    X = np.column_stack([y, y * 0 + 2.5])
    np.testing.assert_allclose(optimal_weights(X, y), [1.0, 0.0], atol=1e-9)


def test_first_period_has_no_history_and_uses_equal_weights():
    out = run_rolling_blend(_archive(), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31 23:00"))

    assert (out["fallback_level"] == "equal_weights").all()
    for m in MODELS:
        np.testing.assert_allclose(out[f"w_optimal_{m}"], 1 / 3)


def test_later_periods_favour_skilful_model_and_beat_members():
    out = run_rolling_blend(_archive(), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-30 23:00"))
    march = out[out["timestamp"] >= "2024-03-01"]

    assert (march["fallback_level"] == "location_season_regime").all()
    assert (march["w_inverse_mae_ai_model"] > march["w_inverse_mae_model_b"]).all()
    # bias correction removes model_a's +3 offset, so it becomes useful
    np.testing.assert_allclose(march["bias_model_a"], 3.0, atol=0.1)

    blend_mae = (march["blended_optimal"] - march["actual_value"]).abs().mean()
    for col in ["model_a_forecast", "model_b_forecast", "ai_model_forecast"]:
        assert blend_mae < (march[col] - march["actual_value"]).abs().mean()


def test_weights_never_use_observations_from_the_future():
    base = _archive()
    corrupted = base.copy()
    # Wreck ai_model only in March: February weights must not notice.
    march = corrupted["timestamp"] >= "2024-03-01"
    corrupted.loc[march, "ai_model_forecast"] += 50

    kwargs = dict(start=pd.Timestamp("2024-01-01"), end=pd.Timestamp("2024-02-28 23:00"))
    a = run_rolling_blend(base, **kwargs)
    b = run_rolling_blend(corrupted, **kwargs)

    pd.testing.assert_series_equal(a["blended_optimal"], b["blended_optimal"])


def test_target_time_must_precede_period_start():
    """A 6h forecast issued at 21:00 on the last day of January verifies in
    February, so it can't be part of February's weight history."""
    archive = _archive(days=40)
    out = run_rolling_blend(archive, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-05 23:00"))
    feb = out[out["timestamp"] >= "2024-02-01"]

    verified_before_feb = archive[archive["timestamp"] + pd.Timedelta(hours=6) < "2024-02-01"]
    assert (feb["n_history"] == len(verified_before_feb)).all()


def test_missing_member_is_excluded_and_weights_renormalised():
    archive = _archive()
    archive.loc[archive["timestamp"] >= "2024-03-01", "model_b_forecast"] = np.nan
    out = run_rolling_blend(archive, pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-02"))

    for method in METHODS:
        assert out[f"blended_{method}"].notna().all()
