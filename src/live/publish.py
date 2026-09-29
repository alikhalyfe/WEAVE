"""Compute the tracked cities and the India grid, and write one snapshot
file that the API can serve without calling Open-Meteo itself.

Why: Open-Meteo's free limits are per IP address, and hosting providers'
shared outbound IPs can exhaust them (Render's did: "Daily API request
limit exceeded" after WEAVE itself had used ~1,250 units). A scheduled
GitHub Actions run (.github/workflows/live-snapshot.yml) executes this on
GitHub's machines every 3 hours and publishes the file to the `live-data`
branch; the API loads it (service.load_snapshot).

Robust to flaky networks: requests retry with backoff (openmeteo.RETRY_WAITS),
failed cities get a second pass, and any city that still fails keeps its
entry from the previous published snapshot (with its original timestamp,
so its real age stays visible) instead of disappearing from the site.

    python -m src.live.publish [output path]
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import httpx

from src.data_pipeline import config
from src.live import cities, grid, openmeteo, service

DEFAULT_OUT = config.DATA_DIR / "snapshot" / "live.json.gz"
SECOND_PASS_WAIT = 60


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _compute(label: str, name: str, state: str) -> dict:
    place = service._resolved.get(label) or cities.resolve(name, state)
    if place is None:
        raise openmeteo.OpenMeteoError("no geocoder match")
    payload = service.forecast(place["name"], place["latitude"], place["longitude"])
    return {"label": label, "place": place, "computed_at": time.time(), "payload": payload}


def previous_snapshot() -> dict:
    """The currently published snapshot, or {} if there is none."""
    if not service.SNAPSHOT_URL or service.SNAPSHOT_URL == "0":
        return {}
    try:
        res = httpx.get(service.SNAPSHOT_URL, timeout=60, follow_redirects=True)
        res.raise_for_status()
        return json.loads(gzip.decompress(res.content))
    except Exception as exc:
        _log(f"no previous snapshot to carry forward from: {exc}")
        return {}


def build_snapshot() -> dict:
    t0 = time.time()
    tracked = [(f"{n}, {s}", n, s) for n, s in cities.TRACKED_CITIES]
    done: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for attempt in (1, 2):
        todo = [t for t in tracked if t[0] not in done]
        if not todo:
            break
        if attempt == 2:
            _log(f"second pass for {len(todo)} cities in {SECOND_PASS_WAIT}s")
            time.sleep(SECOND_PASS_WAIT)
        for label, name, state in todo:
            try:
                done[label] = _compute(label, name, state)
                errors.pop(label, None)
                _log(f"{label}: ok")
            except Exception as exc:  # recorded, not fatal
                errors[label] = str(exc)
                _log(f"{label}: {exc}")

    carried = []
    if errors:
        prev = {e["label"]: e for e in previous_snapshot().get("cities", [])}
        for label in list(errors):
            if label in prev:
                done[label] = {**prev[label], "carried_over": True}
                carried.append(label)
        if carried:
            _log(f"carried forward from the previous snapshot: {', '.join(carried)}")

    entries = [done[label] for label, _, _ in tracked if label in done]
    grid_payload = None
    if entries:
        for e in entries:  # the grid borrows weights from every city we have, fresh or carried
            service._results.setdefault(service._key(e["place"]["latitude"], e["place"]["longitude"]), (e["computed_at"], e["payload"]))
        grid_payload = grid.build(service.weight_sources())
    return {
        "format": 1,
        "generated_at": time.time(),
        "compute_seconds": round(time.time() - t0, 1),
        "cities": entries,
        "carried_over": carried,
        "failures": [{"label": k, "error": v} for k, v in errors.items() if k not in carried],
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
    fresh = len(snap["cities"]) - len(snap["carried_over"])
    print(f"{fresh} cities fresh, {len(snap['carried_over'])} carried over, {len(snap['failures'])} missing, "
          f"grid={'yes' if snap['grid'] else 'no'}, {snap['budget_used']} units, {path.stat().st_size / 1e6:.1f} MB -> {path}")
    if fresh == 0 or not snap["grid"]:
        sys.exit(1)  # nothing new: fail loudly instead of republishing stale data as if it were new


if __name__ == "__main__":
    main()
