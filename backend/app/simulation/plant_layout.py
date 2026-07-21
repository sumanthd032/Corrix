"""Loads the eight-zone plant layout + adjacency graph, per
CORRIX_DATA_METHODOLOGY.md §7. Hand-authored static JSON, not generated;
the layout itself doesn't vary per scenario or seed.

`load_plant_layout` also accepts an optional `factory_id` (Bring Your
Own Factory, CORRIX_REAL_DATA_BUILD_PLAN.md Step 5) to load a real
user-onboarded layout from Neo4j instead. Every existing call site
calls it with zero arguments and is completely unaffected: that path
still resolves to `_load_static_demo_layout`, unchanged, byte-for-byte.
The factory path is deliberately not cached, since a factory's layout
can change after onboarding (the wizard can be re-run, zones added),
unlike the static demo layout, which never changes for the process's
lifetime."""

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import PlantLayout

REPO_ROOT = Path(__file__).resolve().parents[3]
LAYOUT_PATH = REPO_ROOT / "data" / "layout" / "plant_layout.json"


@lru_cache
def _load_static_demo_layout() -> PlantLayout:
    data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    return PlantLayout(**data)


def load_plant_layout(factory_id: str | None = None) -> PlantLayout:
    if factory_id is None:
        return _load_static_demo_layout()

    from app.storage.factory_store import load_factory

    profile = load_factory(factory_id)
    if profile is None:
        raise ValueError(f"unknown factory_id: {factory_id}")
    return profile.layout
