"""Deterministic permit-conflict rule table, per CORRIX_BUILD_PLAN.md
Step 3: "hot work + high-hazard zone + elevated anomaly = conflict, etc."
Not LLM-generated — a fully auditable, inspectable rule table, consistent
with CORRIX_DATA_METHODOLOGY.md §5's principle that core safety logic
should be rule-based and auditable.

The gating rule is permit-type-agnostic (keyed only on the zone's hazard
class and the current anomaly risk level): this generalizes the doc's
named example (hot work) to the pattern the brief itself names verbatim
for S3 — a *maintenance* (cold_work) permit co-occurring with rising gas
is exactly as much a compound risk as a hot-work permit is, and gating
only on permit type would miss it. The permit type is still recorded in
the conflict's reason string for explainability, just not used to decide
whether the rule fires.
"""

from datetime import datetime

from app.schemas import HazardClass, PermitRecord, RiskLevel, Zone

_HAZARD_ORDER = {HazardClass.LOW: 0, HazardClass.MEDIUM: 1, HazardClass.HIGH: 2}
_RISK_ORDER = {"SAFE": 0, "CAUTION": 1, "HIGH": 2, "CRITICAL": 3}

# Minimum anomaly risk level required, per zone hazard class, before an
# active permit in that zone counts as a conflict. LOW-hazard zones never
# conflict — no rule table entry needed, no permit there is dangerous
# enough to flag regardless of anomaly score.
CONFLICT_RULE_TABLE: dict[HazardClass, RiskLevel] = {
    HazardClass.HIGH: "CAUTION",
    HazardClass.MEDIUM: "HIGH",
}


class PermitConflictResult:
    def __init__(
        self,
        zone_id: str,
        conflict: bool,
        reason: str | None,
        conflicting_permits: list[str],
    ):
        self.zone_id = zone_id
        self.conflict = conflict
        self.reason = reason
        self.conflicting_permits = conflicting_permits

    def __repr__(self) -> str:
        return (
            f"PermitConflictResult(zone_id={self.zone_id!r}, conflict={self.conflict}, "
            f"reason={self.reason!r}, conflicting_permits={self.conflicting_permits})"
        )


def active_permits_at(
    permits: list[PermitRecord], zone_id: str, at_time: datetime
) -> list[PermitRecord]:
    return [
        p
        for p in permits
        if p.zone_id == zone_id and p.start_time <= at_time <= p.end_time
    ]


def check_permit_conflict(
    zone: Zone,
    active_permits: list[PermitRecord],
    risk_level: RiskLevel,
) -> PermitConflictResult:
    """Deterministic rule check: does the combination of an active permit in
    this zone plus the zone's current anomaly risk level constitute a
    scripted conflict, per CONFLICT_RULE_TABLE."""
    if not active_permits:
        return PermitConflictResult(zone.zone_id, False, None, [])

    min_required = CONFLICT_RULE_TABLE.get(zone.hazard_class)
    if min_required is None:
        return PermitConflictResult(zone.zone_id, False, None, [])

    if _RISK_ORDER[risk_level] < _RISK_ORDER[min_required]:
        return PermitConflictResult(zone.zone_id, False, None, [])

    permit_ids = [p.permit_id for p in active_permits]
    permit_types = sorted({p.type.value for p in active_permits})
    reason = (
        f"{len(active_permits)} active permit(s) ({', '.join(permit_types)}) in "
        f"{zone.zone_id} ({zone.hazard_class.value}-hazard), anomaly risk_level="
        f"{risk_level} >= required {min_required}"
    )
    return PermitConflictResult(zone.zone_id, True, reason, permit_ids)
