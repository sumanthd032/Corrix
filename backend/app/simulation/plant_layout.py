"""Loads the eight-zone plant layout + adjacency graph, per
CORRIX_DATA_METHODOLOGY.md §7. Hand-authored static JSON, not generated —
the layout itself doesn't vary per scenario or seed."""

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import PlantLayout

REPO_ROOT = Path(__file__).resolve().parents[3]
LAYOUT_PATH = REPO_ROOT / "data" / "layout" / "plant_layout.json"


@lru_cache
def load_plant_layout() -> PlantLayout:
    data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    return PlantLayout(**data)
