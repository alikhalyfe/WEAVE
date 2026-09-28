"""Live mode against a mock Open-Meteo (httpx.MockTransport): no network.

The mock serves a known synthetic truth and member forecasts with known
error profiles, so assertions can check the engine learns the right thing:
ecmwf_ifs is accurate, gfs is biased (+2) and noisy, icon has no lead-day-7
forecasts, aifs is fairly accurate.
"""

from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.live import cache, engine, openmeteo, service

ERRORS = {"ecmwf_ifs025": (0.0, 0.2), "ncep_gfs013": (2.0, 1.5), "dwd_icon": (0.0, 0.8), "ecmwf_aifs025_single": (0.0, 0.4)}
ERA5_LAG_DAYS = 6


def _truth(var: str, times: np.ndarray) -> np.ndarray:
    h = times.astype("datetime64[h]").astype(np.int64)
    if var == "temperature_2m":
        return 25 + 5 * np.sin(2 * np.pi * h / 24)
    if var == "precipitation":
        return np.clip(3 * np.sin(2 * np.pi * h / 50), 0, None)
    return 3 + np.sin(2 * np.pi * h / 30)


def _times(start: str, end: str) -> np.ndarray:
    return np.arange(np.datetime64(start + "T00"), np.datetime64(end + "T23") + np.timedelta64(1, "h"), np.timedelta64(1, "h"))


def _member(var, model, times, day):
    bias, noise = ERRORS[model]
    rng = np.random.default_rng(abs(hash((var, model, day))) % 2**32)
    values = _truth(var, times) + bias + rng.normal(0, noise, len(times))
    if var != "temperature_2m":
        values = np.clip(values, 0, None)
    out = [round(float(v), 2) for v in values]
    if model == "dwd_icon" and day == 7:
        out = [None] * len(out)
    return out


def _fmt(times):
    return [str(t)[:16] for t in times]


def handler(request: httpx.Request) -> httpx.Response:
    q = dict(request.url.params)
    host = request.url.host
    handler.calls.append(host)
    if host.startswith("geocoding"):
        return httpx.Response(200, json={"results": [
            {"name": "Pune", "admin1": "Maharashtra", "admin2": "Pune", "country_code": "IN", "latitude": 18.52,
             "longitude": 73.86, "population": 3124458, "elevation": 560},
            {"name": "Pune", "admin1": "Somewhere", "country_code": "XX", "latitude": 1.0, "longitude": 1.0},
        ]})
    if request.url.path.endswith("meta.json"):
        return httpx.Response(200, json={"last_run_initialisation_time": 1790000000, "last_run_availability_time": 1790010000})
    hourly_vars = q["hourly"].split(",")
    if host.startswith("archive"):
        times = _times(q["start_date"], q["end_date"])
        cutoff = np.datetime64(datetime.now(timezone.utc).date() - timedelta(days=ERA5_LAG_DAYS))
        hourly = {"time": _fmt(times)}
        for v in hourly_vars:
            vals = [round(float(x), 2) for x in _truth(v, times)]
            hourly[v] = [None if t >= cutoff else x for t, x in zip(times, vals)]
        return httpx.Response(200, json={"hourly": hourly})
    models = q["models"].split(",")
    if host.startswith("previous-runs"):
        times = _times(q["start_date"], q["end_date"])
    else:
        today = datetime.now(timezone.utc).date()
        times = _times(today.isoformat(), (today + timedelta(days=int(q["forecast_days"]) - 1)).isoformat())
    hourly = {"time": _fmt(times)}
    for v in hourly_vars:
        base, _, day = v.partition("_previous_day")
        for m in models:
            hourly[f"{v}_{m}"] = _member(base, m, times, int(day or 0) if host.startswith("previous-runs") else 0)
    return httpx.Response(200, json={"hourly": hourly})


@pytest.fixture(autouse=True)
def mock_openmeteo(tmp_path, monkeypatch):
    handler.calls = []
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    cache.clear()
    engine._skill_cache.clear()
    service._results.clear()
    openmeteo.set_client(httpx.Client(transport=httpx.MockTransport(handler)))
    yield
    openmeteo.set_client(httpx.Client())


def test_search_keeps_only_indian_places():
    results = openmeteo.search("Pune")
    assert [r["state"] for r in results] == ["Maharashtra"]


def test_previous_runs_parses_every_lead_day_including_unsuffixed_day0():
    df, _ = openmeteo.previous_runs(18.5, 73.9, date(2026, 1, 1), date(2026, 1, 2))
    assert sorted(df["lead_time_hours"].unique()) == [24 * d for d in range(8)]
    day0 = df[(df["lead_time_hours"] == 0) & (df["target_variable"] == "temperature_2m_c")]
    assert day0["ecmwf_ifs_forecast"].notna().all()
    day7 = df[df["lead_time_hours"] == 168]
    assert day7["icon_forecast"].isna().all()


def test_era5_drops_unpublished_hours_instead_of_filling_them():
    today = datetime.now(timezone.utc).date()
    df, _ = openmeteo.era5(18.5, 73.9, today - timedelta(days=10), today)
    assert df["timestamp"].max() < np.datetime64(today - timedelta(days=ERA5_LAG_DAYS))
    assert df.notna().all().all()


def test_responses_are_cached():
    openmeteo.search("Pune")
    openmeteo.search("Pune")
    assert handler.calls.count("geocoding-api.open-meteo.com") == 1


def test_live_forecast_learns_member_skill_and_verifies_out_of_sample():
    r = engine.live_forecast("Pune", 18.52, 73.86)
    temp = r["variables"]["temperature_2m_c"]

    day1 = [p for p in temp["points"] if p["lead_day"] == 1]
    assert day1 and all(p["weights"]["ecmwf_ifs"] > p["weights"]["gfs"] for p in day1)

    # ICON has no day-7 history, so it is excluded there rather than guessed.
    day7 = next(c for c in temp["chosen"] if c["lead_day"] == 7)
    assert "icon" not in day7["models"]

    skill = {(s["lead_day"], s["source"]): s["mae"] for s in temp["skill"]}
    assert skill[(1, "blended")] < skill[(1, "gfs")]
    assert skill[(1, "blended")] <= skill[(1, "ecmwf_ifs")] * 1.05
    assert all(s["n"] > 0 for s in temp["skill"])

    for p in temp["points"]:
        assert p["event_probability"] is None or 0 <= p["event_probability"] <= 1
    assert r["truth_available_until"] < r["issued_at"]


def test_api_live_endpoints():
    from src.api.main import app

    client = TestClient(app)
    assert client.get("/api/live/search", params={"q": "Pune"}).json()["results"][0]["state"] == "Maharashtra"
    assert client.get("/api/live/forecast", params={"lat": 51.5, "lon": -0.1}).status_code == 422

    body = client.get("/api/live/forecast", params={"lat": 18.52, "lon": 73.86, "name": "Pune"}).json()
    assert set(body["variables"]) == {"temperature_2m_c", "precipitation_mm", "wind_speed_10m"}
    assert "Open-Meteo" in body["attribution"]

    summary = service.summarise(body)
    assert summary["next_24h"]["temperature_2m_c"] is not None
    assert summary["dominant"]["temperature_2m_c"]["model"] in {"ecmwf_ifs", "aifs"}
