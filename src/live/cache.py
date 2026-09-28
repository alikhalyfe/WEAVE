"""Tiny TTL cache for Open-Meteo responses: in-memory, mirrored to disk so a
restart doesn't re-download climatology. Keys are request URLs; values are
the raw JSON the API returned (never anything derived or invented)."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from src.data_pipeline import config

CACHE_DIR = Path(os.environ.get("WEAVE_LIVE_CACHE", config.DATA_DIR / "live_cache"))
_memory: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def _path(key: str) -> Path:
    return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def get(key: str, ttl: float) -> tuple[float, object] | None:
    """(stored_at, value) if younger than ttl seconds, else None."""
    now = time.time()
    with _lock:
        hit = _memory.get(key)
    if hit and now - hit[0] < ttl:
        return hit
    path = _path(key)
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if now - stored["stored_at"] >= ttl:
        return None
    hit = (stored["stored_at"], stored["value"])
    with _lock:
        _memory[key] = hit
    return hit


def put(key: str, value: object) -> float:
    stored_at = time.time()
    with _lock:
        _memory[key] = (stored_at, value)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _path(key).write_text(json.dumps({"stored_at": stored_at, "key": key, "value": value}))
    except OSError:
        pass  # disk is a best-effort mirror; memory still serves
    return stored_at


def clear() -> None:
    with _lock:
        _memory.clear()
