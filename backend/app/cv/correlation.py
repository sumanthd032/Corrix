"""Scripted correlation layer, per CORRIX_DATA_METHODOLOGY.md §9: a CV
detection's plant-context correlation is checked against the Step 2
worker-location/badge-ping stream — not an implied badge system, and
not a hardcoded guess. `source` and `correlation_source` are kept as
distinct, explicitly-typed fields on the resulting event (Step 1's
CVObservationEvent schema), so the real/simulated split can't
accidentally get lost as the system evolves.
"""

from datetime import datetime, timedelta

from app.cv.inference import Detection
from app.schemas import BadgePingEvent, CVObservationEvent

PERSON_CLASSES = {"Person", "person"}
_TOLERANCE = timedelta(minutes=2)


def _latest_ping_before(
    pings: list[BadgePingEvent], zone_id: str, at_time: datetime
) -> BadgePingEvent | None:
    candidates = [
        p for p in pings if p.zone_id == zone_id and p.timestamp <= at_time
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.timestamp)


def correlate_detection(
    detection: Detection,
    zone_id: str,
    detection_time: datetime,
    worker_pings: list[BadgePingEvent],
    event_id: str,
) -> CVObservationEvent:
    """Builds a CVObservationEvent for one real detection, correlating it
    against the worker-location stream: a person-class detection with no
    matching badge-ping in the zone within the tolerance window is
    flagged as unconfirmed presence."""
    correlation: str | None = None
    if detection.class_name in PERSON_CLASSES:
        latest = _latest_ping_before(worker_pings, zone_id, detection_time)
        if latest is None or (detection_time - latest.timestamp) > _TOLERANCE:
            correlation = f"no matching badge-ping in {zone_id}"
        else:
            correlation = f"matches badge-ping {latest.badge_id} in {zone_id}"

    return CVObservationEvent(
        event_id=event_id,
        zone_id=zone_id,
        timestamp=detection_time,
        detection=detection.class_name,
        confidence=detection.confidence,
        source="real_inference",
        correlation=correlation,
        correlation_source="simulated" if correlation is not None else None,
    )
