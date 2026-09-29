"""Caching + the operational refresh loop around the live engine.

Results for a place are reused for RESULT_TTL (the member forecasts
themselves only change every ~6h). The tracked cities are computed in a
small thread pool with honest per-city status (ready / pending / error).
start_refresher() runs the routine workflow in the background: every
REFRESH_SECONDS it re-blends stale cities and rebuilds the India grid, so
the dashboard stays current without anyone running a script.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.live import alerts, cities, engine, grid, openmeteo

RESULT_TTL = 30 * 60
REFRESH_SECONDS = 20 * 60
GRID_TTL = 15 * 60
_results: dict[tuple, tuple[float, dict]] = {}
_errors: dict[str, tuple[float, str]] = {}
_pending: set[str] = set()
_resolved: dict[str, dict | None] = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="weave-live")
_grid: dict = {"at": 0.0, "payload": None, "error": None, "building": False}
_refresher = {"started": None, "runs": 0, "last_run": None, "last_error": None}


def _key(lat: float, lon: float) -> tuple:
    return round(lat, 3), round(lon, 3)


def forecast(name: str, lat: float, lon: float) -> dict:
    """Live blend for a place, recomputed at most every RESULT_TTL."""
    key = _key(lat, lon)
    hit = _results.get(key)
    if hit and time.time() - hit[0] < RESULT_TTL:
        return hit[1]
    payload = engine.live_forecast(name, lat, lon)
    _results[key] = (time.time(), payload)
    return payload


def summarise(payload: dict) -> dict:
    """Headline numbers for the map: next-24h blended max temperature, total
    rain, max wind; the dominant member per variable and lead day; skill;
    and daily extreme events for today and the next two IST days. All read
    straight from the payload."""
    out = {"place": payload["place"], "fetched_at": payload["fetched_at"], "next_24h": {}, "dominant": {}, "alerts": []}
    agg = {"temperature_2m_c": max, "precipitation_mm": sum, "wind_speed_10m": max}
    for var, d in payload["variables"].items():
        window = [p for p in d["points"] if p["hours_ahead"] < 24 and p["blended"] is not None]
        out["next_24h"][var] = round(agg[var](p["blended"] for p in window), 2) if window else None
        out["dominant"][var] = {}
        for day in sorted({p["lead_day"] for p in d["points"]}):
            ws = [p["weights"] for p in d["points"] if p["lead_day"] == day]
            mean = {m: round(sum(w.get(m) or 0 for w in ws) / len(ws), 3) for m in ws[0]}
            top = max(mean, key=mean.get)
            out["dominant"][var][str(day)] = {"model": top, "weight": mean[top], "weights": mean}
        by_day = {}
        for s in d["skill"]:
            by_day.setdefault(s["lead_day"], {})[s["source"]] = s["mae"]
        out.setdefault("skill", {})[var] = [
            {"lead_day": day, "blended": v["blended"],
             "best_member": min((x, k) for k, x in v.items() if k not in ("blended", "equal_mean"))[1],
             "best_member_mae": min(x for k, x in v.items() if k not in ("blended", "equal_mean")),
             "equal_mean": v.get("equal_mean")}
            for day, v in sorted(by_day.items()) if "blended" in v
        ]
        out.setdefault("verification", {})[var] = d["event_verification"]
    # Hazards for today and the next two IST days, from the plain-language outlook.
    for day in payload.get("outlook", [])[:3]:
        for h in day["hazards"]:
            out["alerts"].append({"type": h["type"], "level": h["level"], "label": h["label"], "date": day["date"],
                                  "day_label": day["label"], "probability": h["probability"], "sentence": h["sentence"]})
    out["outlook"] = [{k: d[k] for k in ("date", "label", "icon", "headline", "high", "low", "rain_mm", "rain_chance", "wind_kmh")}
                      for d in payload.get("outlook", [])[:3]]
    return out


def _compute_city(label: str, name: str, state: str) -> None:
    try:
        if label not in _resolved:
            _resolved[label] = cities.resolve(name, state)
        place = _resolved[label]
        if place is None:
            raise openmeteo.OpenMeteoError(f"Geocoder has no match for {name}, {state}")
        forecast(place["name"], place["latitude"], place["longitude"])
        _errors.pop(label, None)
    except Exception as exc:  # recorded and shown per city, never hidden
        _errors[label] = (time.time(), str(exc))
    finally:
        with _lock:
            _pending.discard(label)


def overview() -> dict:
    """Status + summary for every tracked city; schedules any that are
    missing or stale. Never blocks on network calls."""
    items = []
    for name, state in cities.TRACKED_CITIES:
        label = f"{name}, {state}"
        place = _resolved.get(label)
        hit = _results.get(_key(place["latitude"], place["longitude"])) if place else None
        fresh = hit and time.time() - hit[0] < RESULT_TTL
        err = _errors.get(label)
        retry_error = err and time.time() - err[0] > 300
        with _lock:
            if not fresh and label not in _pending and (not err or retry_error):
                _pending.add(label)
                _pool.submit(_compute_city, label, name, state)
            pending = label in _pending
        item = {"label": label, "name": name, "state": state,
                "status": "ready" if hit else "pending" if pending else "error" if err else "pending"}
        if place:
            item["place"] = {k: place[k] for k in ("name", "state", "latitude", "longitude")}
        if hit:
            item["summary"] = summarise(hit[1])
            item["stale"] = not fresh
        if err and not hit:
            item["error"] = err[1]
        items.append(item)
    ready = sum(i["status"] == "ready" for i in items)
    return {"cities": items, "ready": ready, "total": len(items)}


def weight_sources() -> list[dict]:
    """Verified cities and their mean weights per variable and lead day,
    for the grid's regional weighting."""
    out = []
    for (lat, lon), (_, payload) in list(_results.items()):
        weights = {}
        for var, d in payload["variables"].items():
            weights[var] = {}
            for day in sorted({p["lead_day"] for p in d["points"]}):
                ws = [p["weights"] for p in d["points"] if p["lead_day"] == day]
                weights[var][str(day)] = {m: sum(w.get(m) or 0 for w in ws) / len(ws) for m in ws[0]}
        out.append({"name": payload["place"]["name"], "latitude": lat, "longitude": lon, "weights": weights})
    return out


def _build_grid() -> None:
    try:
        payload = grid.build(weight_sources())
        _grid.update(at=time.time(), payload=payload, error=None)
    except Exception as exc:  # shown on the map, never hidden
        _grid.update(error=str(exc), at=time.time())
    finally:
        _grid["building"] = False


def grid_field() -> dict:
    """Latest India grid. Rebuilt in the background when older than
    GRID_TTL; returns status 'building' until the first one exists."""
    with _lock:
        stale = time.time() - _grid["at"] > GRID_TTL
        if stale and not _grid["building"] and _results:
            _grid["building"] = True
            _pool.submit(_build_grid)
    if _grid["payload"] is None:
        return {"status": "building" if _grid["building"] or not _results else "error", "error": _grid["error"],
                "note": "The grid appears once at least one city's model skill has been learned."}
    return {"status": "ready", **_grid["payload"], "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_grid["at"]))}


def _refresh_loop() -> None:
    while True:
        try:
            overview()
            grid_field()
            _refresher.update(runs=_refresher["runs"] + 1, last_run=time.time(), last_error=None)
        except Exception as exc:
            _refresher["last_error"] = str(exc)
        time.sleep(REFRESH_SECONDS)


def start_refresher() -> None:
    """Idempotent: starts the routine refresh thread once per process."""
    with _lock:
        if _refresher["started"]:
            return
        _refresher["started"] = time.time()
    threading.Thread(target=_refresh_loop, name="weave-refresher", daemon=True).start()


def status() -> dict:
    """Operational status for the Operations page."""
    now = time.time()
    b = openmeteo.budget
    with b.lock:
        used = {label: round(sum(w for t, w in b.spent if now - t < win), 1) for label, win in (("minute", 60), ("hour", 3600), ("day", 86400))}
    ov = overview()
    ages = [now - t for t, _ in _results.values()]
    try:
        sachet = alerts.fetch()
        sachet_info = {"active": len(sachet["alerts"]), "fetched_at": sachet["fetched_at"], "age_seconds": sachet["age_seconds"]}
    except Exception as exc:
        sachet_info = {"error": str(exc)}
    return {
        "refresher": {**_refresher, "interval_seconds": REFRESH_SECONDS,
                      "next_run_in_seconds": max(0, round(REFRESH_SECONDS - (now - _refresher["last_run"]))) if _refresher["last_run"] else None},
        "budget": {"used": used, "limits": {"minute": openmeteo.BUDGET[60], "hour": openmeteo.BUDGET[3600], "day": openmeteo.BUDGET[86400]},
                   "note": "Counted by this server since it started, using Open-Meteo's own call weighting."},
        "cities": {"ready": ov["ready"], "total": ov["total"], "errors": sum(c["status"] == "error" for c in ov["cities"])},
        "places_cached": len(_results),
        "oldest_result_minutes": round(max(ages) / 60, 1) if ages else None,
        "skill_cache": len(engine._skill_cache),
        "grid": {"status": "ready" if _grid["payload"] else "building" if _grid["building"] else "not built",
                 "cells": len(_grid["payload"]["cells"]) if _grid["payload"] else 0,
                 "built_minutes_ago": round((now - _grid["at"]) / 60, 1) if _grid["payload"] else None},
        "official_alerts": sachet_info,
        "ttl_seconds": openmeteo.TTL,
    }
