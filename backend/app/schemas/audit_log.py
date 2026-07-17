from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class RegulatoryFramework(str, Enum):
    OISD = "OISD"
    FACTORIES_ACT = "Factories_Act_1948"
    DGMS = "DGMS"


class AuditLogEntry(BaseModel):
    """Historical near-miss / inspection-log corpus entry, per
    CORRIX_DATA_METHODOLOGY.md §10. Hand-authored and illustrative, but each
    entry must reference a real, checkable clause: the mocked incident
    record is not real, the regulatory citation it points to is."""

    entry_id: str
    zone_id: str | None = None
    timestamp: datetime
    deviation_type: str
    description: str
    source_framework: RegulatoryFramework
    required_checklist_ref: str
