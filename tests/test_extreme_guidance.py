import numpy as np
import pandas as pd

from src.evaluation.extreme_guidance import apply_guidance, attach_thresholds, tune_scales, verify_events
from src.evaluation.skill import add_skill_scores, skill_table

THRESHOLDS = pd.DataFrame({
    "location": ["Pune"], "season": ["Monsoon"],
    "precipitation_mm_p95": [4.5], "temperature_2m_c_p95": [35.0], "wind_speed_10m_p95": [8.0],
})


def _frame():
    # A smooth forecast that under-predicts every event by half.
    actual = np.array([0, 0, 5, 6, 0, 0, 8, 0, 0, 0], dtype=float)
    blended = actual * 0.5
    return pd.DataFrame({
        "location": "Pune", "season": "Monsoon", "target_variable": "precipitation_mm", "lead_time_hours": 6,
        "actual_value": actual, "blended": blended,
        "model_a_forecast": blended, "model_b_forecast": blended, "ai_model_forecast": np.zeros(10),
        "bias_model_a": 0.0, "bias_model_b": 0.0, "bias_ai_model": 0.0,
        "weight_model_a": 0.25, "weight_model_b": 0.25, "weight_ai_model": 0.5,
    })


def test_attach_thresholds_marks_observed_events_by_variable():
    out = attach_thresholds(_frame(), THRESHOLDS)
    assert (out["event_threshold"] == 4.5).all()
    assert out["observed_event"].tolist() == [False, False, True, True, False, False, True, False, False, False]


def test_tuned_scale_recovers_events_a_raw_threshold_misses():
    df = attach_thresholds(_frame(), THRESHOLDS)
    raw_hits = (df["blended"] >= df["event_threshold"]).sum()
    scales = tune_scales(df)
    guided = apply_guidance(df, scales)

    assert raw_hits == 0
    assert scales[("precipitation_mm", 6)] <= 0.6
    assert guided.loc[guided["observed_event"].astype(bool), "guidance_event"].all()
    # model_a + model_b (weight 0.5) exceed, ai_model (0.5) doesn't
    np.testing.assert_allclose(guided.loc[2, "event_probability"], 0.5)

    v = verify_events(guided, {"guidance": guided["guidance_event"]})
    assert v.loc[0, "csi"] == 1.0 and v.loc[0, "far"] == 0.0


def test_skill_table_scores_all_sources_on_identical_cases():
    df = pd.DataFrame({
        "g": ["a"] * 4, "actual_value": [1.0, 2.0, 3.0, np.nan],
        "good": [1.0, 2.0, 3.5, 9.0], "bad": [2.0, 3.0, 4.0, 9.0], "blend": [1.0, 2.0, 3.25, 9.0],
    })
    t = add_skill_scores(skill_table(df, {"good": "good", "bad": "bad", "blend": "blend"}, ["g"]), ["g"], ["good", "bad"])
    t = t.set_index("source")

    assert (t["n"] == 3).all()
    np.testing.assert_allclose(t.loc["good", "mae"], 0.5 / 3)
    np.testing.assert_allclose(t.loc["blend", "mae_skill_pct"], 50.0)
