"""Committed warm-start data for the tracked cities.

A fresh deploy (Render's free tier keeps no files) would otherwise
re-download two things that barely change: the tracked cities' geocoded
coordinates and their day-of-year climate thresholds (2 years of daily
ERA5, ~52 Open-Meteo call units per city). Both are stored in
data/live_seed.json and used when recent enough; everything that changes
daily (forecasts, skill history, ERA5 truth) is still fetched live.

    python -m src.live.seed      # regenerate (reuses the local cache)
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

import pandas as pd

from src.data_pipeline import config

SEED_PATH = config.DATA_DIR / "live_seed.json"
MAX_AGE_DAYS = 92  # thresholds are 2-year statistics; a quarter-old snapshot is still representative


def key(lat: float, lon: float) -> str:
    return f"{lat:.3f},{lon:.3f}"


@lru_cache
def load() -> dict:
    try:
        return json.loads(SEED_PATH.read_text())
    except (OSError, ValueError):
        return {}


def cities() -> dict[str, dict]:
    return load().get("cities", {})


def climatology(lat: float, lon: float, end: date) -> pd.DataFrame | None:
    """Stored thresholds for this place if computed within MAX_AGE_DAYS of `end`."""
    entry = load().get("climatology", {}).get(key(lat, lon))
    if not entry or (end - date.fromisoformat(entry["through"])).days > MAX_AGE_DAYS:
        return None
    return pd.DataFrame(entry["thresholds"])


def build() -> dict:
    from src.live import cities as tracked, engine

    out = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "cities": {}, "climatology": {}}
    end = engine.climatology_end()
    for name, state in tracked.TRACKED_CITIES:
        place = tracked.resolve(name, state)
        if place is None:
            print(f"skip {name}, {state}: no geocoder match")
            continue
        out["cities"][f"{name}, {state}"] = place
        thr = engine.climatology(place["latitude"], place["longitude"], use_seed=False)
        out["climatology"][key(place["latitude"], place["longitude"])] = {
            "through": end.isoformat(), "thresholds": thr.round(3).to_dict("records")}
        print(f"seeded {name}")
    SEED_PATH.write_text(json.dumps(out, separators=(",", ":")))
    load.cache_clear()
    return out


if __name__ == "__main__":
    build()
