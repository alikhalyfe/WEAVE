"""Compute the tracked cities and the India grid, and write one snapshot
file that the API can serve without calling Open-Meteo itself.

Why: Open-Meteo's free limits are per IP address, and hosting providers'
shared outbound IPs can exhaust them (Render's did: "Daily API request
limit exceeded" after WEAVE itself had used ~1,250 units). A scheduled
GitHub Actions run (.github/workflows/live-snapshot.yml) executes this on
GitHub's machines every 3 hours and publishes the file to the `live-data`
branch; the API loads it (service.load_snapshot).

    python -m src.live.publish [output path]
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

from src.data_pipeline import config
from src.live import cities, grid, openmeteo, service

DEFAULT_OUT = config.DATA_DIR / "snapshot" / "live.json.gz"


def build_snapshot() -> dict:
    t0 = time.time()
    entries, failures = [], []
    for name, state in cities.TRACKED_CITIES:
        label = f"{name}, {state}"
        place = service._resolved.get(label) or cities.resolve(name, state)
        if place is None:
            failures.append({"label": label, "error": "no geocoder match"})
            continue
        try:
            payload = service.forecast(place["name"], place["latitude"], place["longitude"])
            entries.append({"label": label, "place": place, "computed_at": time.time(), "payload": payload})
            print(f"[{time.strftime('%H:%M:%S')}] {label}: ok", flush=True)
        except Exception as exc:  # recorded, not fatal: the snapshot still ships the rest
            failures.append({"label": label, "error": str(exc)})
            print(f"[{time.strftime('%H:%M:%S')}] {label}: {exc}", flush=True)
    grid_payload = grid.build(service.weight_sources()) if entries else None
    return {
        "format": 1,
        "generated_at": time.time(),
        "compute_seconds": round(time.time() - t0, 1),
        "cities": entries,
        "failures": failures,
        "grid": grid_payload,
        "budget_used": round(sum(w for _, w in openmeteo.budget.spent), 1),
    }


def write(snapshot: dict, out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf8") as f:
        json.dump(snapshot, f, separators=(",", ":"), default=str)
    return out


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    snap = build_snapshot()
    path = write(snap, out)
    print(f"{len(snap['cities'])} cities, grid={'yes' if snap['grid'] else 'no'}, "
          f"{len(snap['failures'])} failures, {snap['budget_used']} units, {path.stat().st_size / 1e6:.1f} MB -> {path}")
    if not snap["cities"] or not snap["grid"]:
        sys.exit(1)  # fail the scheduled run loudly rather than publish an empty snapshot


if __name__ == "__main__":
    main()
