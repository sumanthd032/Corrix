from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["SAFE", "CAUTION", "HIGH", "CRITICAL"]
TriggerReason = Literal["rule_threshold", "novelty", "memory_retrieval"]


class TimeToCriticalForecast(BaseModel):
    """Monte Carlo rollout output, per CORRIX_DATA_METHODOLOGY.md §3.6.

    Deliberately a distribution, not a scalar: a bare point estimate ("18
    min") is falsely precise. `median_minutes` plus the IQR band is what
    the live forecaster (CORRIX_PROJECT.md §6.4) actually renders. At Step 4
    this is populated with a placeholder; the real Monte Carlo rollout over
    the simulator's step() function lands in Step 8.
    """

    median_minutes: float
    iqr_low_minutes: float
    iqr_high_minutes: float
    escalation_probability: float = Field(ge=0.0, le=1.0)
    horizon_minutes: int = 60


class CouncilEvidence(BaseModel):
    """The four evidence agents' structured outputs, as received only by the
    Chair (CORRIX_PROJECT.md §6.1); no agent sees another agent's evidence."""

    process_safety_engineer: str
    permit_control_officer: str
    shift_operations: str
    site_safety_observer: str


class RegulatoryCitation(BaseModel):
    """A clause from the Regulatory Intelligence substrate (OISD, Factories
    Act, DGMS) surfaced as the regulatory basis for a verdict: the specific
    provision most relevant to the situation the Council just judged. DGMS
    material is flagged supplementary, never presented as a primary
    citation (CORRIX_PROJECT.md §7.3)."""

    framework: str
    source_document: str
    section_number: str
    section_title: str
    is_supplementary: bool


class CouncilVerdict(BaseModel):
    """The Safety Council's Chair-synthesized verdict, per
    CORRIX_PROJECT.md §6.2."""

    zone_id: str
    scenario_id: str | None = None
    trigger_reason: TriggerReason
    timestamp: datetime
    council: CouncilEvidence
    risk_level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    compound_flag: bool
    time_to_critical: TimeToCriticalForecast
    explanation: str
    recommended_action: str
    evacuation_route: list[str] | None = None
    regulatory_citations: list[RegulatoryCitation] | None = None
