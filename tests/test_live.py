"""Live mode against a mock Open-Meteo (httpx.MockTransport): no network.

The mock serves a known synthetic truth and member forecasts with known
error profiles, so assertions can check the engine learns the right thing:
ecmwf_ifs is accurate, gfs is biased (+2) and noisy, icon has no lead-day-7
forecasts, the ensemble mean and aifs are fairly accurate. Like the real API,
single-model responses carry no model suffix and multi-location requests
return a list.
"""

from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.live import alerts, cache, engine, grid, openmeteo, outlook, service

ERRORS = {"ecmwf_ifs025": (0.0, 0.2), "ncep_gfs013": (2.0, 1.5), "dwd_icon": (0.0, 0.8),
          "ecmwf_ifs025_ensemble_mean": (0.0, 0.5), "ecmwf_aifs025_single": (0.0, 0.4)}
DAILY_BASE = {"temperature_2m_max": "temperature_2m", "temperature_2m_min": "temperature_2m",
              "precipitation_sum": "precipitation", "wind_speed_10m_max": "wind_speed_10m"}
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


def _daily_body(q, models):
    today = datetime.now(timezone.utc).date()
    days = np.arange(np.datetime64(today), np.datetime64(today + timedelta(days=int(q.get("forecast_days", 8)))))
    noon = days.astype("datetime64[h]") + np.timedelta64(12, "h")
    daily = {"time": [str(d) for d in days]}
    for v in q["daily"].split(","):
        base = _truth(DAILY_BASE[v], noon) * (24 if "precipitation" in v else 1)
        if models == [openmeteo.ENSEMBLE_MEMBERS_MODEL]:  # 51 members: control + 50 perturbed
            rng = np.random.default_rng(0)
            daily[v] = [round(float(x), 2) for x in base]
            for k in range(1, 51):
                daily[f"{v}_member{k:02d}"] = [round(float(x), 2) for x in np.clip(base + rng.normal(0, 1, len(base)), 0, None)]
            continue
        for m in models:
            key = v if len(models) == 1 else f"{v}_{m}"
            daily[key] = [round(float(x), 2) for x in base + ERRORS.get(m, (0, 0))[0]]
    return {"daily": daily, "elevation": 560.0}


def _hourly_body(q, host, models):
    if host.startswith("previous-runs"):
        times = _times(q["start_date"], q["end_date"])
    else:
        today = datetime.now(timezone.utc).date()
        times = _times(today.isoformat(), (today + timedelta(days=int(q["forecast_days"]) - 1)).isoformat())
    hourly = {"time": _fmt(times)}
    for v in q["hourly"].split(","):
        base, _, day = v.partition("_previous_day")
        for m in models:
            key = v if len(models) == 1 else f"{v}_{m}"
            hourly[key] = _member(base, m, times, int(day or 0) if host.startswith("previous-runs") else 0)
    return {"hourly": hourly, "elevation": 560.0}


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
    if host.startswith("archive") and "daily" in q:
        days = np.arange(np.datetime64(q["start_date"]), np.datetime64(q["end_date"]) + np.timedelta64(1, "D"))
        daily = {"time": [str(d) for d in days]}
        noon = days.astype("datetime64[h]") + np.timedelta64(12, "h")
        for v in q["daily"].split(","):
            daily[v] = [round(float(x), 2) for x in _truth(DAILY_BASE[v], noon) * (24 if "precipitation" in v else 1)]
        return httpx.Response(200, json={"daily": daily})
    if host.startswith("archive"):
        times = _times(q["start_date"], q["end_date"])
        cutoff = np.datetime64(datetime.now(timezone.utc).date() - timedelta(days=ERA5_LAG_DAYS))
        hourly = {"time": _fmt(times)}
        for v in q["hourly"].split(","):
            vals = [round(float(x), 2) for x in _truth(v, times)]
            hourly[v] = [None if t >= cutoff else x for t, x in zip(times, vals)]
        return httpx.Response(200, json={"hourly": hourly})
    models = q["models"].split(",")
    n_loc = len(q["latitude"].split(","))
    bodies = [_daily_body(q, models) if "daily" in q else _hourly_body(q, host, models) for _ in range(n_loc)]
    return httpx.Response(200, json=bodies if n_loc > 1 else bodies[0])


SACHET_SAMPLE = [
    {"identifier": 1, "severity": "Orange", "severity_color": "orange", "disaster_type": "Heavy Rain",
     "area_description": "Pune, Satara, Maharashtra", "warning_message": "Heavy rainfall likely at isolated places.",
     "alert_source": "IMD", "effective_start_time": "Tue Sep 29 08:00:00 IST 2026",
     "effective_end_time": "Sat Oct 31 08:00:00 IST 2099", "centroid": "73.9,18.4"},
    {"identifier": 2, "severity": "Yellow", "severity_color": "yellow", "disaster_type": "Flood",
     "area_description": "Kosi, Khagaria, Bihar", "warning_message": "River above danger level.",
     "alert_source": "CWC", "effective_start_time": "Mon Sep 28 08:00:00 IST 2026",
     "effective_end_time": "Mon Sep 28 09:00:00 IST 2026", "centroid": "86.7,25.5"},
]


@pytest.fixture(autouse=True)
def mock_openmeteo(tmp_path, monkeypatch):
    handler.calls = []
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    cache.clear()
    engine._skill_cache.clear()
    service._results.clear()
    openmeteo.set_client(httpx.Client(transport=httpx.MockTransport(handler)))
    alerts.set_client(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=SACHET_SAMPLE))))
    openmeteo.budget.spent.clear()
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


def test_daily_thresholds_use_a_day_of_year_window():
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    clim = pd.DataFrame({"date": dates, "temperature_2m_c": dates.dayofyear.astype(float),
                         "precipitation_mm": 5.0, "wind_speed_10m": 3.0})
    thr = engine.daily_thresholds(clim).set_index("doy")
    # temperature equals day-of-year, so the p95 of a +-15-day window sits near doy + 13
    assert 160 < thr.loc[150, "temperature_2m_c"] < 166
    assert thr.loc[150, "precipitation_mm"] == 5.0


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

    assert temp["days"] and all(d["probability"] is None or 0 <= d["probability"] <= 1 for d in temp["days"])
    assert all(d["threshold"] is not None for d in temp["days"])
    assert sum(d["hours"] for d in temp["days"]) == len(temp["points"])
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
    assert summary["dominant"]["temperature_2m_c"]["1"]["model"] in {"ecmwf_ifs", "aifs"}


def test_request_weight_follows_open_meteo_accounting():
    # 2 weeks x 15 variables = 1.5 calls (Open-Meteo's own example)
    assert openmeteo.request_weight({"hourly": ",".join(["v"] * 15), "models": "era5",
                                     "start_date": "2026-01-01", "end_date": "2026-01-14", "latitude": "1"}) == 1.5
    assert openmeteo.request_weight({"hourly": "a", "forecast_days": 7, "latitude": "1,2"}) == 2


def test_budget_refuses_instead_of_exceeding_hourly_limit(monkeypatch):
    b = openmeteo._Budget()
    monkeypatch.setitem(openmeteo.BUDGET, 3600, 10)
    b.acquire(8)
    with pytest.raises(openmeteo.OpenMeteoError, match="hourly"):
        b.acquire(5)


def test_ensemble_daily_has_51_members():
    ens, _ = openmeteo.ensemble_daily(18.5, 73.9)
    assert ens.groupby("variable")["member"].nunique().eq(51).all()


def test_forecast_includes_ensemble_mean_member_and_cloud():
    (res,), _ = openmeteo.forecast([(18.5, 73.9)])
    assert res["members"]["ens_forecast"].notna().all()
    assert res["cloud"]["cloud_cover"].notna().all() and res["elevation"] == 560.0


def test_imd_heat_wave_rules():
    assert outlook.heat_wave(41.0, 36.0, hills=False) == "heat wave"          # departure 5.0
    assert outlook.heat_wave(41.0, 34.0, hills=False) == "severe heat wave"   # departure 7.0
    assert outlook.heat_wave(39.0, 30.0, hills=False) is None                 # below 40 °C in the plains
    assert outlook.heat_wave(31.0, 26.0, hills=True) == "heat wave"           # hills threshold 30 °C
    assert outlook.heat_wave(45.5, 44.0, hills=False) == "heat wave"          # absolute 45 °C


def test_imd_rain_categories_and_words():
    assert outlook.rain_category(0.05) is None
    assert outlook.rain_category(70) == "heavy rain"
    assert outlook.rain_category(210) == "extremely heavy rain"
    d = outlook.describe_day({"high": 29, "low": 24, "rain_mm": 80, "rain_chance": 0.9, "wind_kmh": 20, "cloud": 90, "hazards": []})
    assert d["headline"] == "Heavy rain" and "around 80 mm" in d["text"] and "Chance of rain 90%" in d["text"]


def test_outlook_is_built_from_computed_numbers():
    r = engine.live_forecast("Pune", 18.52, 73.86)
    assert r["ensemble_members"] == 51
    assert r["outlook"] and all(o["headline"] and o["text"] for o in r["outlook"])
    first = r["outlook"][0]
    assert first["high"] == r["variables"]["temperature_2m_c"]["days"][0]["blended"]
    assert all(o["rain_chance"] is None or 0 <= o["rain_chance"] <= 1 for o in r["outlook"])


def test_official_alerts_parse_filter_and_match_by_distance_or_state():
    feed = alerts.fetch()
    assert [a["id"] for a in feed["alerts"]] == ["1"]  # the expired flood alert is dropped
    assert alerts.near(18.52, 73.86)[0]["distance_km"] < 50
    assert alerts.near(21.1, 79.1, state="Maharashtra")[0]["matched_by"] == "state"
    assert alerts.near(28.6, 77.2) == []


def test_grid_points_are_inside_india_and_blend_with_borrowed_weights():
    pts = grid.grid_points()
    assert 80 < len(pts) < 200 and all(6 <= la <= 37 and 68 <= lo <= 98 for la, lo in pts)
    grid._points = pts[:3]
    try:
        src = [{"name": "Pune", "latitude": 18.52, "longitude": 73.86,
                "weights": {v: {str(d): {"ecmwf_ifs": 1.0} for d in range(8)} for v in ("temperature_2m_c", "precipitation_mm", "wind_speed_10m")}}]
        g = grid.build(src)
    finally:
        grid._points = None
    cell = g["cells"][0]
    assert cell["neighbours"] == ["Pune"] and cell["dominant"]["temperature_2m_c"][0] == "ecmwf_ifs"
    assert cell["values"]["temperature_2m_c"][0] is not None


def test_city_resolution_never_crosses_states():
    from src.live import cities
    assert cities.resolve("Pune", "Maharashtra")["state"] == "Maharashtra"
    assert cities.resolve("Pune", "Goa") is None  # only a Maharashtra match exists: refuse, don't guess


def test_keepalive_targets_render_url_and_stays_off_locally(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KEEPALIVE_URL", raising=False)
    assert service.keepalive_url() is None  # local dev / tests: never ping

    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://weave-api.onrender.com/")
    assert service.keepalive_url() == "https://weave-api.onrender.com/api/health"

    monkeypatch.setenv("WEAVE_KEEPALIVE", "0")
    assert service.keepalive_url() is None
