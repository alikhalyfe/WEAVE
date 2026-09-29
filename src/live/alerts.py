"""Official warnings from NDMA SACHET, India's national CAP alert portal
(https://sachet.ndma.gov.in). It aggregates warnings issued by IMD, CWC and
state disaster management authorities; the feed is published as public
domain. WEAVE only relays these -- it never edits or re-grades them.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone

import httpx

from src.live import cache

SACHET_URL = "https://sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails"
TTL_SECONDS = 600
IST = timezone(timedelta(hours=5, minutes=30))
SEVERITY_RANK = {"red": 4, "warning": 4, "orange": 3, "alert": 3, "yellow": 2, "watch": 2, "green": 1, "advisory": 1}
WEATHER_TYPES = ("rain", "thunder", "lightning", "storm", "wind", "heat", "cold", "cyclone", "flood", "fog", "hail", "snow")

_client = httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0), headers={"User-Agent": "WEAVE/2 (non-commercial)"})


def set_client(client: httpx.Client) -> None:
    global _client
    _client = client


def _parse_time(text: str | None) -> datetime | None:
    """'Tue Sep 29 08:00:00 IST 2026' -> aware datetime."""
    if not text:
        return None
    try:
        return datetime.strptime(text.replace(" IST ", " "), "%a %b %d %H:%M:%S %Y").replace(tzinfo=IST)
    except ValueError:
        return None


def _normalise(a: dict) -> dict | None:
    try:
        lon, lat = (float(x) for x in a["centroid"].split(","))
    except (KeyError, ValueError, AttributeError):
        lat = lon = None
    start, end = _parse_time(a.get("effective_start_time")), _parse_time(a.get("effective_end_time"))
    severity = (a.get("severity") or "").strip()
    return {
        "id": str(a.get("identifier")),
        "type": a.get("disaster_type"),
        "severity": severity,
        "severity_color": (a.get("severity_color") or "").lower() or None,
        "rank": SEVERITY_RANK.get(severity.lower(), SEVERITY_RANK.get((a.get("severity_color") or "").lower(), 1)),
        "area": a.get("area_description"),
        "message": a.get("warning_message"),
        "source": a.get("alert_source"),
        "language": (a.get("actual_lang") or "en").lower(),
        "starts": start.isoformat() if start else None,
        "ends": end.isoformat() if end else None,
        "latitude": lat,
        "longitude": lon,
        "weather_related": any(w in (a.get("disaster_type") or "").lower() for w in WEATHER_TYPES),
    }


def fetch() -> dict:
    """Current alerts (cached TTL_SECONDS). Expired alerts are dropped."""
    hit = cache.get(SACHET_URL, TTL_SECONDS)
    if hit:
        stored_at, raw = hit
    else:
        res = _client.get(SACHET_URL)
        res.raise_for_status()
        raw = res.json()
        stored_at = cache.put(SACHET_URL, raw)
    now = datetime.now(IST)
    alerts = [n for n in (_normalise(a) for a in raw if isinstance(a, dict)) if n]
    active = [a for a in alerts if not a["ends"] or datetime.fromisoformat(a["ends"]) >= now]
    active.sort(key=lambda a: (-a["rank"], a["starts"] or ""))
    return {"alerts": active, "fetched_at": datetime.fromtimestamp(stored_at, timezone.utc).isoformat(timespec="seconds"),
            "source": "NDMA SACHET (IMD, CWC and state disaster management authorities)", "age_seconds": round(time.time() - stored_at)}


def km_between(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def near(lat: float, lon: float, state: str | None = None, radius_km: float = 150) -> list[dict]:
    """Alerts whose area centre is within radius_km, or whose area text
    names the place's state. Adds distance_km for display."""
    out = []
    for a in fetch()["alerts"]:
        d = km_between(lat, lon, a["latitude"], a["longitude"]) if a["latitude"] is not None else None
        named = bool(state and a["area"] and state.lower() in a["area"].lower())
        if (d is not None and d <= radius_km) or named:
            out.append({**a, "distance_km": round(d) if d is not None else None, "matched_by": "distance" if d is not None and d <= radius_km else "state"})
    return out
