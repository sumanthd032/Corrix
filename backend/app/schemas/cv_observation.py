from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CVObservationEvent(BaseModel):
    """Site-observation/CV detection event, per CORRIX_DATA_METHODOLOGY.md §9.

    `source` and `correlation_source` are kept as distinct, explicitly-typed
    fields rather than a single free-text label: the real/simulated split is
    encoded in the data structure itself, not just a UI label that could
    accidentally get lost or misrepresented as the system evolves.
    """

    event_id: str
    zone_id: str
    timestamp: datetime
    detection: str
    confidence: float
    source: Literal["real_inference"]
    correlation: str | None = None
    correlation_source: Literal["simulated"] | None = None
