from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PermitType(str, Enum):
    HOT_WORK = "hot_work"
    COLD_WORK = "cold_work"
    CONFINED_SPACE_ENTRY = "confined_space_entry"
    LIFTING_OPERATION = "lifting_operation"
    ELECTRICAL_ISOLATION = "electrical_isolation"


class PermitStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class PermitRecord(BaseModel):
    """Permit-to-work record, per CORRIX_DATA_METHODOLOGY.md §5."""

    permit_id: str
    type: PermitType
    zone_id: str
    issued_by: str
    start_time: datetime
    end_time: datetime
    status: PermitStatus
    linked_checklist_id: str | None = None
