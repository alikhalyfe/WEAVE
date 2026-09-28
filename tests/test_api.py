import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.api.main as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    ts = pd.date_range("2025-07-01", periods=200, freq="h")
    rng = np.random.default_rng(0)
    actual = 25 + rng.normal(0, 1, len(ts))
    df = pd.DataFrame({
        "timestamp": ts, "location": "Pune", "latitude": 18.5, "longitude": 73.75, "season": "Monsoon",
        "weather_regime": "Normal", "target_variable": "temperature_2m_c", "lead_time_hours": 12,
        "model_a_forecast": actual + 2, "model_b_forecast": actual + rng.normal(0, 1, len(ts)),
        "ai_model_forecast": actual + rng.normal(0, 0.2, len(ts)), "blended": actual, "actual_value": actual,
        "event_probability": 0.0, "guidance_threshold": 35.0, "event_threshold": 35.0, "guidance_event": False,
        "observed_event": False, "weight_model_a": 0.1, "weight_model_b": 0.2, "weight_ai_model": 0.7,
    })
    df.to_csv(tmp_path / "forecasts.csv", index=False)
    manifest = {
        "generated_at": "2026-01-01T00:00:00+00:00", "default_issue_time": "2025-07-03 06:00:00",
        "selected_methods": [{"target_variable": "temperature_2m_c", "lead_time_hours": 12, "config": "regime_bias", "method": "optimal"}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "skill.json").write_text(json.dumps({"by_variable_lead": [
        {"target_variable": "temperature_2m_c", "lead_time_hours": 12, "source": "blended", "mae": 0.5, "mae_skill_pct": float("nan")},
        {"target_variable": "precipitation_mm", "lead_time_hours": 12, "source": "blended", "mae": 0.1},
    ]}))

    monkeypatch.setattr(api, "ARTIFACTS_DIR", tmp_path)
    for fn in (api._json, api._forecasts, api._live_tables):
        fn.cache_clear()
    yield TestClient(api.app)
    for fn in (api._json, api._forecasts, api._live_tables):
        fn.cache_clear()


def test_health_and_meta(client):
    assert client.get("/api/health").json()["artifacts_ready"] is True
    assert client.get("/api/meta").json()["default_issue_time"] == "2025-07-03 06:00:00"


def test_snapshot_defaults_to_manifest_issue_time(client):
    body = client.get("/api/snapshot", params={"lead": 12}).json()
    assert body["issue_time"] == "2025-07-03T06:00:00"
    assert body["valid_time"] == "2025-07-03T18:00:00"
    assert len(body["rows"]) == 1


def test_series_window_and_validation(client):
    body = client.get("/api/series", params={"location": "Pune", "variable": "temperature_2m_c", "lead": 12,
                                             "time": "2025-07-03T06:00", "hours_before": 6, "hours_after": 6}).json()
    assert len(body["points"]) == 13
    assert client.get("/api/series", params={"location": "Pune", "variable": "snow"}).status_code == 422


def test_skill_filter_and_nan_become_null(client):
    rows = client.get("/api/skill", params={"variable": "temperature_2m_c"}).json()["by_variable_lead"]
    assert len(rows) == 1 and rows[0]["mae_skill_pct"] is None


def test_blend_learns_from_archive_and_corrects_bias(client):
    res = client.post("/api/blend", json={
        "location": "Pune", "season": "Monsoon", "weather_regime": "Normal", "target_variable": "temperature_2m_c",
        "lead_time_hours": 12, "forecasts": {"model_a": 32.0, "model_b": 30.0, "ai_model": 30.0},
    }).json()
    assert res["config"] == "regime_bias" and res["method"] == "optimal"
    assert res["fallback_level"] == "location_season_regime"
    assert res["weights"]["ai_model"] > res["weights"]["model_b"]
    assert res["bias_correction"]["model_a"] == pytest.approx(2.0, abs=1e-6)
    assert res["blended_forecast"] == pytest.approx(30.0, abs=0.05)


def test_blend_rejects_unknown_models(client):
    res = client.post("/api/blend", json={
        "location": "Pune", "season": "Monsoon", "target_variable": "temperature_2m_c",
        "lead_time_hours": 12, "forecasts": {"gfs": 1.0},
    })
    assert res.status_code == 422


def test_missing_artifacts_return_503(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ARTIFACTS_DIR", tmp_path)
    api._json.cache_clear()
    c = TestClient(api.app)
    assert c.get("/api/health").json()["artifacts_ready"] is False
    assert c.get("/api/meta").status_code == 503
