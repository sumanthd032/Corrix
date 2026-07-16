"""The joint-evidence vector, per CORRIX_DATA_METHODOLOGY.md §13.2: the
"whole picture together" representation the novelty detector needs, as
opposed to the single-signal z-score the fast-path scorer (§3) uses.

Assembled per zone per timestep from data every scenario run already
produces: the zone's own calibrated z-score, whether a permit is active
(and the zone's hazard class, since the same permit means different
things in different zones), shift-changeover proximity, and worker
occupancy. Deliberately excludes CV/Observation: that stream only exists
for scenarios with a scripted `cv_event` and for the live demo clip, not
for every tick of every offline harness run, so including it would leave
most of the training and scoring data with a missing feature rather than
a real one.
"""

from datetime import datetime, timedelta

from app.detection.anomaly_scorer import score_series
from app.detection.permit_conflict import active_permits_at
from app.schemas import ShiftRecord, Zone
from app.simulation.scenario_engine import ScenarioOutput

_HAZARD_ORDINAL = {"low": 0.0, "medium": 0.5, "high": 1.0}
CHANGEOVER_PROXIMITY_WINDOW_MINUTES = 60.0


def _signal_values(out: ScenarioOutput) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def _timestamps(out: ScenarioOutput) -> list[datetime]:
    if out.gas_readings:
        return [r.timestamp for r in out.gas_readings]
    return [r.timestamp for r in out.compliance_readings]


def _changeover_proximity(shifts: list[ShiftRecord], zone_id: str, at_time: datetime) -> float:
    """1.0 at the moment of changeover, decaying linearly to 0.0 at
    `CHANGEOVER_PROXIMITY_WINDOW_MINUTES` away or beyond — 0.0 if no
    shift record covers this zone/time at all."""
    relevant = [s for s in shifts if zone_id in s.zones and s.start_time <= at_time <= s.end_time]
    if not relevant:
        return 0.0
    nearest = min(relevant, key=lambda s: abs((s.end_time - at_time).total_seconds()))
    minutes_to_changeover = abs((nearest.end_time - at_time).total_seconds()) / 60
    return max(0.0, 1.0 - minutes_to_changeover / CHANGEOVER_PROXIMITY_WINDOW_MINUTES)


def _worker_count(worker_pings, zone_id: str, at_time: datetime) -> int:
    latest_by_badge: dict[str, tuple] = {}
    for ping in worker_pings:
        if ping.timestamp > at_time:
            continue
        current = latest_by_badge.get(ping.badge_id)
        if current is None or ping.timestamp > current[0]:
            latest_by_badge[ping.badge_id] = (ping.timestamp, ping.zone_id)
    return sum(1 for _, last_zone in latest_by_badge.values() if last_zone == zone_id)


def build_joint_evidence_series(zone: Zone, out: ScenarioOutput) -> list[list[float]]:
    """One fixed-length feature vector per tick of the run's own signal
    series (gas or compliance, whichever the scenario carries):
    [z_score, permit_active, hazard_ordinal, changeover_proximity, worker_count].
    """
    values = _signal_values(out)
    timestamps = _timestamps(out)
    points = score_series(values)
    hazard_ordinal = _HAZARD_ORDINAL[zone.hazard_class.value]

    vectors: list[list[float]] = []
    for point, at_time in zip(points, timestamps):
        active = active_permits_at(out.permits, zone.zone_id, at_time)
        permit_active = 1.0 if active else 0.0
        changeover_proximity = _changeover_proximity(out.shifts, zone.zone_id, at_time)
        worker_count = float(_worker_count(out.worker_pings, zone.zone_id, at_time))
        vectors.append(
            [point.z_score, permit_active, hazard_ordinal, changeover_proximity, worker_count]
        )
    return vectors
