from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class BadgeEventType(str, Enum):
    ZONE_ENTRY = "zone_entry"
    ZONE_EXIT = "zone_exit"
    HEARTBEAT = "heartbeat"


class BadgePingEvent(BaseModel):
    """Worker-location/badge-ping event, per CORRIX_DATA_METHODOLOGY.md §8.2.
    Zone-level granularity, mirroring how real badge/turnstile RTLS systems
    actually report, not fabricated continuous GPS."""

    badge_id: str
    zone_id: str
    timestamp: datetime
    event_type: BadgeEventType
