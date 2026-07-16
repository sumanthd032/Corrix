from datetime import datetime

from pydantic import BaseModel, Field


class ComplianceSignalReading(BaseModel):
    """S1's procedural-compliance degradation signal, Q(t), per
    CORRIX_DATA_METHODOLOGY.md §4. Deliberately not a GasSensorReading — this
    represents a checklist-quality score, not an atmospheric concentration,
    matching the real anchor incident's mechanism rather than forcing a
    rising-gas-ppm shape onto a procedural-lapse failure mode."""

    zone_id: str
    linked_checklist_id: str
    compliance_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
