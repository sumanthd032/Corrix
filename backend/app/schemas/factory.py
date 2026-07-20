from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.shift import ShiftRecord
from app.schemas.zone import PlantLayout


class FactoryProfile(BaseModel):
    """A user-onboarded "Bring Your Own Factory" profile, per
    CORRIX_REAL_DATA.md §4 Phase A. Reuses `PlantLayout`/`Zone`/
    `ZoneAdjacencyEdge` and `ShiftRecord` as-is rather than duplicating
    their shape, so the same evacuation routing, risk propagation, and
    shift-changeover logic the synthetic demo already uses runs
    unmodified against a real user's factory."""

    factory_id: str
    name: str
    industry: str
    location: str | None = None
    layout: PlantLayout
    permit_types_in_use: list[str]
    shift_pattern: list[ShiftRecord]
    data_source: Literal["csv", "mqtt", "opcua"] = "csv"
    created_at: datetime
