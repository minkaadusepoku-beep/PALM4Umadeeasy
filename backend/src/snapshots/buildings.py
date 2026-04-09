"""
Base building snapshot loader (ADR-004 §1, §5).

A snapshot is a frozen, named set of base buildings (typically OSM at a
fixed date). Storing the snapshot id inside the scenario JSON makes
re-runs deterministic regardless of when the source service is queried.

For v1 the loader is filesystem-backed: a snapshot lives at
`<PROJECT_ROOT>/data/base_snapshots/<snapshot_id>.json` and contains a
JSON array of building dicts shaped like:

    [
      {"id": "osm:way/123", "geometry": {...}, "height_m": 12.0},
      ...
    ]

Tests can register snapshots in-memory via `register_snapshot`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..config import PROJECT_ROOT

_SNAPSHOT_DIR = Path(PROJECT_ROOT) / "data" / "base_snapshots"
_in_memory: dict[str, list[dict]] = {}


def register_snapshot(snapshot_id: str, buildings: list[dict]) -> None:
    """Register a snapshot in memory (used by tests and seeding)."""
    _in_memory[snapshot_id] = buildings


def clear_in_memory_snapshots() -> None:
    _in_memory.clear()


def load_snapshot(snapshot_id: str) -> list[dict]:
    """
    Return the building list for a snapshot id.

    Resolution order: in-memory registry first, then the filesystem
    fallback. An unknown id resolves to an empty list — this is
    deliberate so a freshly created scenario without any base data
    behaves identically to one whose base snapshot has zero buildings.
    """
    if snapshot_id in _in_memory:
        return _in_memory[snapshot_id]
    path = _SNAPSHOT_DIR / f"{snapshot_id}.json"
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
    return []
