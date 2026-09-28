"""Caching + background refresh around the live engine, for the API.

Results for a place are reused for RESULT_TTL (the member forecasts
themselves only change every ~6h). The overview map computes the tracked
cities in a small thread pool and reports honest per-city status
(ready / pending / error) instead of blocking or guessing.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.live import cities, engine, openmeteo

RESULT_TTL = 30 * 60
_results: dict[tuple, tuple[float, dict]] = {}
_errors: dict[str, tuple[float, str]] = {}
_pending: set[str] = set()
_resolved: dict[str, dict | None] = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="weave-live")


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
    rain, max wind; the dominant member per variable and lead day; and
    every alert in the next 72h. All read straight from the payload."""
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
        hits = [p for p in d["points"] if p["alert"] and p["hours_ahead"] < 72]
        if hits:
            peak = max(hits, key=lambda p: p["blended"])
            out["alerts"].append({
                "target_variable": var, "first_time": hits[0]["time"], "hours": len(hits), "peak_time": peak["time"],
                "peak_value": peak["blended"], "threshold": peak["event_threshold"],
                "max_probability": max(p["event_probability"] or 0 for p in hits),
            })
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
