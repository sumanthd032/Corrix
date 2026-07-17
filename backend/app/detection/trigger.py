"""The event-trigger condition, per CORRIX_BUILD_PLAN.md Step 3: anomaly
score or permit-conflict crossing a configured threshold. This is what
will later convene the Safety Council (Step 4), defined here as a plain
function, not one of the Council's siloed agents, since the fast-path
trigger is explicitly allowed to look at both sensor and permit data at
once (it's the deterministic baseline, not a Council member bound by the
agent-silo constraint in CORRIX_PROJECT.md §6.1).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.detection.anomaly_scorer import AnomalyPoint, score_series
from app.detection.permit_conflict import (
    PermitConflictResult,
    active_permits_at,
    check_permit_conflict,
)
from app.schemas import PermitRecord, TriggerReason, Zone

TICK_SECONDS = 5.0


@dataclass
class TriggerEvaluation:
    zone_id: str
    index: int
    timestamp: datetime
    anomaly_point: AnomalyPoint
    permit_conflict: PermitConflictResult
    should_trigger: bool
    trigger_reason: TriggerReason | None


def evaluate_at_index(
    zone: Zone,
    points: list[AnomalyPoint],
    index: int,
    permits: list[PermitRecord],
    start_time: datetime,
) -> TriggerEvaluation:
    point = points[index]
    timestamp = start_time + timedelta(seconds=TICK_SECONDS * index)
    active = active_permits_at(permits, zone.zone_id, timestamp)
    conflict = check_permit_conflict(zone, active, point.risk_level)

    should_trigger = point.risk_level in ("HIGH", "CRITICAL") or conflict.conflict
    return TriggerEvaluation(
        zone_id=zone.zone_id,
        index=index,
        timestamp=timestamp,
        anomaly_point=point,
        permit_conflict=conflict,
        should_trigger=should_trigger,
        trigger_reason="rule_threshold" if should_trigger else None,
    )


def find_first_trigger(
    zone: Zone,
    values: list[float],
    permits: list[PermitRecord],
    start_time: datetime,
) -> TriggerEvaluation | None:
    """Scan the full run and return the first tick where the trigger
    condition fires, or None if it never does: the earliest point a
    correct system could reasonably convene the Council."""
    points = score_series(values)
    for i in range(len(points)):
        evaluation = evaluate_at_index(zone, points, i, permits, start_time)
        if evaluation.should_trigger:
            return evaluation
    return None
