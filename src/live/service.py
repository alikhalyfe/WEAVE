"""Caching + the operational refresh loop around the live engine.

Results for a place are reused for RESULT_TTL (the member forecasts
themselves only change every ~6h). The tracked cities are computed in a
small thread pool with honest per-city status (ready / pending / error).
start_refresher() runs the routine workflow in the background: every
REFRESH_SECONDS it re-blends stale cities and rebuilds the India grid, so
the dashboard stays current without anyone running a script.
"""

from __future__ import annotations

import gzip
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from src.live import alerts, cities, engine, grid, openmeteo, seed

RESULT_TTL = 30 * 60
REFRESH_SECONDS = 20 * 60
GRID_TTL = 15 * 60
GRID_REBUILD_MIN = 90       # seconds between rebuilds as new cities finish
GRID_RETRY = 60             # retry a failed first build after this long
CITY_COST = 190             # Open-Meteo units a cold city can cost (worst case)

# Published snapshot (src/live/publish.py, run every 3 h by GitHub Actions).
# Results loaded from it count as fresh for SNAPSHOT_FRESH, so the server
# does not spend its own (possibly exhausted) Open-Meteo allowance redoing them.
SNAPSHOT_URL = os.environ.get("SNAPSHOT_URL", "https://raw.githubusercontent.com/alikhalyfe/WEAVE/live-data/live.json.gz")
SNAPSHOT_FRESH = 4 * 3600
STALE_FALLBACK = 12 * 3600  # serve a result this old rather than an error when recomputing fails
_results: dict[tuple, tuple[float, dict]] = {}
_errors: dict[str, tuple[float, str]] = {}
_pending: set[str] = set()
_resolved: dict[str, dict | None] = dict(seed.cities())  # committed coordinates: no geocoding on a cold start
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="weave-live")
_grid: dict = {"at": 0.0, "payload": None, "error": None, "building": False, "sources": 0}
_grid_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="weave-grid")  # never queued behind cities
_from_snapshot: set[tuple] = set()
_snapshot = {"url": SNAPSHOT_URL, "generated_at": None, "loaded_at": None, "cities": 0, "error": None}
_refresher = {"started": None, "runs": 0, "last_run": None, "last_error": None}


def _key(lat: float, lon: float) -> tuple:
    return round(lat, 3), round(lon, 3)


def _fresh(key: tuple, hit) -> bool:
    ttl = SNAPSHOT_FRESH if key in _from_snapshot else RESULT_TTL
    return bool(hit) and time.time() - hit[0] < ttl


def forecast(name: str, lat: float, lon: float) -> dict:
    """Live blend for a place, recomputed at most every RESULT_TTL (or
    SNAPSHOT_FRESH for published results). If recomputing fails (e.g.
    Open-Meteo limits), a result up to STALE_FALLBACK old is served instead;
    its own timestamps show its age."""
    key = _key(lat, lon)
    hit = _results.get(key)
    if _fresh(key, hit):
        return hit[1]
    try:
        payload = engine.live_forecast(name, lat, lon)
    except openmeteo.OpenMeteoError:
        if hit and time.time() - hit[0] < STALE_FALLBACK:
            return hit[1]
        raise
    _results[key] = (time.time(), payload)
    _from_snapshot.discard(key)
    return payload


# ---- Browser relay: only for places this server just failed to fetch ----
RELAY_WINDOW = 30 * 60
_relay_allowed: dict[tuple, float] = {}
_relay_slot = threading.Semaphore(1)  # ponytail: one relay compute at a time, a queue if it gets popular


def allow_relay(lat: float, lon: float) -> None:
    _relay_allowed[_key(lat, lon)] = time.time()


def relay_allowed(lat: float, lon: float) -> bool:
    t = _relay_allowed.get(_key(lat, lon))
    return t is not None and time.time() - t < RELAY_WINDOW


def relay_forecast(name: str, lat: float, lon: float, responses: dict) -> dict:
    """Live blend from Open-Meteo responses the browser fetched. Returns
    {'needs': [urls]} until every request is answered. The result goes back
    to that browser only: nothing is stored (it is untrusted input)."""
    responses = {url: body for url, body in responses.items() if body is None or openmeteo.valid_relay_body(body)}
    if not _relay_slot.acquire(blocking=False):
        raise RelayBusy()
    try:
        with openmeteo.relayed(responses) as state:
            try:
                payload = engine.live_forecast(name, lat, lon)
            except openmeteo.OpenMeteoError:
                if not state["needs"]:
                    raise
                engine.relay_probe(name, lat, lon)
                payload = None
            needs = list(dict.fromkeys(state["needs"]))
    finally:
        _relay_slot.release()
    if needs:
        return {"needs": needs}
    return {**payload, "relayed": True}


class RelayBusy(RuntimeError):
    """Another relayed forecast is computing."""


def load_snapshot() -> bool:
    """Merge the published snapshot: any city or grid newer than what this
    server has. Returns True if something was loaded."""
    if not SNAPSHOT_URL or SNAPSHOT_URL == "0":
        return False
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            res = client.get(SNAPSHOT_URL)
            res.raise_for_status()
        snap = json.loads(gzip.decompress(res.content))
    except Exception as exc:  # no snapshot yet / network: carry on computing locally
        _snapshot["error"] = str(exc)
        return False
    return merge_snapshot(snap)


def merge_snapshot(snap: dict) -> bool:
    loaded = 0
    for entry in snap.get("cities", []):
        place = entry["place"]
        key = _key(place["latitude"], place["longitude"])
        _resolved.setdefault(entry["label"], place)
        current = _results.get(key)
        if not current or current[0] < entry["computed_at"]:
            _results[key] = (entry["computed_at"], entry["payload"])
            _from_snapshot.add(key)
            _errors.pop(entry["label"], None)
            loaded += 1
    if snap.get("grid") and snap["generated_at"] > _grid["at"]:
        _grid.update(at=snap["generated_at"], payload=snap["grid"], error=None, sources=len(snap.get("cities", [])), from_snapshot=True)
        loaded += 1
    _snapshot.update(generated_at=snap.get("generated_at"), loaded_at=time.time(), cities=len(snap.get("cities", [])), error=None)
    return loaded > 0


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
        fresh = place is not None and _fresh(_key(place["latitude"], place["longitude"]), hit)
        err = _errors.get(label)
        retry_error = err and time.time() - err[0] > 300
        with _lock:
            wants = not fresh and label not in _pending and (not err or retry_error)
            # Warm up only what this hour's data allowance can pay for; the
            # rest waits for the next refresh cycle instead of hitting a 429.
            if wants and (hit or openmeteo.can_spend(CITY_COST * (len(_pending) + 1))):
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
        sources = weight_sources()
        payload = grid.build(sources)
        _grid.update(at=time.time(), payload=payload, error=None, sources=len(sources), from_snapshot=False)
    except Exception as exc:  # shown on the map, never hidden
        _grid.update(error=str(exc), at=time.time())
    finally:
        _grid["building"] = False


def grid_field() -> dict:
    """Latest India grid. Built straight away (equal weights until cities
    are learned), rebuilt as more cities finish and when older than GRID_TTL."""
    with _lock:
        age = time.time() - _grid["at"]
        published = _grid.get("from_snapshot", False)
        stale = (
            (_grid["payload"] is None and (age > GRID_RETRY or _grid["at"] == 0))
            or age > (SNAPSHOT_FRESH if published else GRID_TTL)
            or (not published and len(_results) > _grid["sources"] and age > GRID_REBUILD_MIN)
        )
        if stale and not _grid["building"]:
            _grid["building"] = True
            _grid_pool.submit(_build_grid)
    if _grid["payload"] is None:
        return {"status": "building" if _grid["building"] else "error", "error": _grid["error"],
                "note": "Fetching the five models for 124 grid points across India."}
    return {"status": "ready", **_grid["payload"], "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_grid["at"]))}


def _refresh_loop() -> None:
    while True:
        try:
            load_snapshot()  # published results first: no Open-Meteo calls from this server
            grid_field()     # then the map: it needs no learned skill to appear
            overview()
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


# ---- Keep-alive (Render free tier) ----
# Render's free web services sleep after ~15 min with no *incoming* HTTP
# traffic, and waking means re-learning every city and rebuilding the map.
# Pinging our own public URL goes out and back in through Render's proxy,
# which counts as incoming traffic. Render sets RENDER_EXTERNAL_URL itself;
# elsewhere (local dev, tests) there is no URL, so nothing is pinged.
KEEPALIVE_SECONDS = 10 * 60
_keepalive = {"url": None, "started": None, "pings": 0, "last_ping": None, "last_status": None, "last_error": None}


def keepalive_url() -> str | None:
    if os.environ.get("WEAVE_KEEPALIVE", "1") == "0":
        return None
    base = os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    return base.rstrip("/") + "/api/health" if base else None


def _keepalive_loop(url: str) -> None:
    with httpx.Client(timeout=30) as client:
        while True:
            time.sleep(KEEPALIVE_SECONDS)
            try:
                res = client.get(url)
                _keepalive.update(pings=_keepalive["pings"] + 1, last_ping=time.time(), last_status=res.status_code, last_error=None)
            except httpx.HTTPError as exc:  # a failed ping is retried next cycle
                _keepalive.update(last_ping=time.time(), last_error=str(exc))


def start_keepalive() -> bool:
    """Idempotent: starts the self-ping thread once, if a public URL is known."""
    url = keepalive_url()
    with _lock:
        if not url or _keepalive["started"]:
            return False
        _keepalive.update(url=url, started=time.time())
    threading.Thread(target=_keepalive_loop, args=(url,), name="weave-keepalive", daemon=True).start()
    return True


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
        "keepalive": {**_keepalive, "interval_seconds": KEEPALIVE_SECONDS},
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
        "open_meteo_paused": openmeteo.paused(),
        "snapshot": {**_snapshot, "age_minutes": round((now - _snapshot["generated_at"]) / 60, 1) if _snapshot["generated_at"] else None},
        "ttl_seconds": openmeteo.TTL,
    }
