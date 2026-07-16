from datetime import datetime

from pydantic import BaseModel


class ShiftRecord(BaseModel):
    """Shift roster entry, per CORRIX_DATA_METHODOLOGY.md §6. Lists the zones
    it covers so the Shift Operations agent can answer "is a changeover
    imminent in this zone specifically" rather than a plant-wide constant."""

    shift_id: str
    start_time: datetime
    end_time: datetime
    changeover_window_minutes: int = 15
    zones: list[str]
