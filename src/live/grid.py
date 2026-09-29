"""Blended daily forecast field over India, for the maps.

Grid points every GRID_STEP degrees inside India's boundary (Survey of India
claim, data/geo/india.geojson). Each point gets the members' daily
forecasts (one batched Open-Meteo call per chunk of points) and is blended
with weights *borrowed from the nearest verified cities*: an
inverse-distance average of the per-lead-day weights those cities learned
from their own verified history. That regional weighting is what the
"most-trusted model" layer shows. Grid points do not get their own bias
correction (that needs local history); the tracked-city forecasts do.
"""

from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd

from src.data_pipeline import config
from src.live import openmeteo
from src.live.alerts import km_between

GRID_STEP = 1.5
CHUNK = 50
NEIGHBOURS = 3
BOUNDARY_PATH = config.DATA_DIR / "geo" / "india.geojson"
VARS = ["temperature_2m_c", "temperature_min", "precipitation_mm", "wind_speed_10m"]
WEIGHT_VAR = {"temperature_2m_c": "temperature_2m_c", "temperature_min": "temperature_2m_c",
              "precipitation_mm": "precipitation_mm", "wind_speed_10m": "wind_speed_10m"}

_points: list[tuple[float, float]] | None = None


def boundary() -> dict:
    return json.loads(BOUNDARY_PATH.read_text())


def _inside(lat: float, lon: float, polygons: list) -> bool:
    hit = False
    for poly in polygons:
        ring = poly[0]
        j = len(ring) - 1
        for i in range(len(ring)):
            (xi, yi), (xj, yj) = ring[i], ring[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
    return hit


def grid_points() -> list[tuple[float, float]]:
    global _points
    if _points is None:
        polys = boundary()["features"][0]["geometry"]["coordinates"]
        lats = np.arange(7.0, 36.5, GRID_STEP)
        lons = np.arange(68.5, 97.5, GRID_STEP)
        _points = [(round(float(a), 2), round(float(o), 2)) for a in lats for o in lons if _inside(a, o, polys)]
    return _points


def _idw(lat: float, lon: float, sources: list[dict]) -> tuple[dict, list[str]]:
    """Inverse-distance-squared average of the nearest cities' weights."""
    ranked = sorted(sources, key=lambda s: km_between(lat, lon, s["latitude"], s["longitude"]))[:NEIGHBOURS]
    if not ranked:
        return {}, []
    dist = [max(km_between(lat, lon, s["latitude"], s["longitude"]), 10.0) for s in ranked]
    inv = [1 / d ** 2 for d in dist]
    total = sum(inv)
    out = {}
    for var in ("temperature_2m_c", "precipitation_mm", "wind_speed_10m"):
        out[var] = {}
        for day in range(8):
            acc: dict[str, float] = {}
            for s, w in zip(ranked, inv):
                for m, v in s["weights"].get(var, {}).get(str(day), {}).items():
                    acc[m] = acc.get(m, 0.0) + w * v / total
            out[var][day] = acc
    return out, [s["name"] for s in ranked]


def build(sources: list[dict]) -> dict:
    """sources: verified cities, each {name, latitude, longitude,
    weights: {var: {lead_day: {model: weight}}}}."""
    t0 = time.time()
    pts = grid_points()
    frames, fetched = [], []
    for i in range(0, len(pts), CHUNK):
        f, t = openmeteo.forecast_daily(pts[i:i + CHUNK])
        frames += f
        fetched.append(t)
    today = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
    dates = [d.date().isoformat() for d in frames[0]["date"]] if frames else []
    cells = []
    for (lat, lon), df in zip(pts, frames):
        weights, neighbours = _idw(lat, lon, sources)
        cell = {"lat": lat, "lon": lon, "values": {}, "dominant": {}, "neighbours": neighbours}
        for var in VARS:
            wvar = WEIGHT_VAR[var]
            vals, doms = [], []
            for _, row in df.iterrows():
                day = int(min(max((row["date"] - today).days, 0), 7))
                w = weights.get(wvar, {}).get(day) or {m: 1.0 for m in openmeteo.MODEL_KEYS}
                members = {m: row.get(f"{var}__{m}") for m in openmeteo.MODEL_KEYS}
                usable = {m: v for m, v in members.items() if v is not None and not math.isnan(v) and w.get(m, 0) > 0}
                wsum = sum(w[m] for m in usable)
                vals.append(round(sum(w[m] * v for m, v in usable.items()) / wsum, 2) if wsum else None)
                if var != "temperature_min":
                    doms.append(max(w, key=w.get) if w else None)
            cell["values"][var] = vals
            if var != "temperature_min":
                cell["dominant"][var] = doms
        cell["weights"] = {v: {str(d): {m: round(x, 3) for m, x in ws.items()} for d, ws in days.items()}
                           for v, days in weights.items()}
        cells.append(cell)
    return {
        "dates": dates, "step_deg": GRID_STEP, "cells": cells,
        "weight_sources": [s["name"] for s in sources],
        "fetched_at": pd.Timestamp(min(fetched), unit="s").isoformat(timespec="seconds") if fetched else None,
        "compute_seconds": round(time.time() - t0, 2),
        "note": "Blend weights are borrowed from the nearest verified cities (inverse-distance); no local bias correction.",
    }
