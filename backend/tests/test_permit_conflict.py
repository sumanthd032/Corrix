"""Deterministic permit-conflict rule table: correctness and Step 3's
Definition of Done, checked against the real scenario library."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.detection.anomaly_scorer import score_series
from app.detection.permit_conflict import active_permits_at, check_permit_conflict
from app.schemas import HazardClass, PermitRecord, PermitStatus, PermitType, Zone
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    load_scenario_config,
    run_scenario,
)

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
POSITIVE_DIRS = ["s1", "s2", "s3", "s4"]


def _signal_values(out) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def _zone(zone_id: str) -> Zone:
    layout = load_plant_layout()
    return next(z for z in layout.zones if z.zone_id == zone_id)


def test_low_hazard_zone_never_conflicts():
    zone = Zone(zone_id="Z8", name="Perimeter", hazard_class=HazardClass.LOW, primary_role="")
    permit = PermitRecord(
        permit_id="P-1", type=PermitType.HOT_WORK, zone_id="Z8",
        issued_by="x", start_time=DEFAULT_START_TIME,
        end_time=DEFAULT_START_TIME + timedelta(hours=4), status=PermitStatus.ACTIVE,
    )
    result = check_permit_conflict(zone, [permit], "CRITICAL")
    assert result.conflict is False


def test_no_active_permits_never_conflicts():
    zone = _zone("Z1")
    result = check_permit_conflict(zone, [], "CRITICAL")
    assert result.conflict is False


def test_high_hazard_zone_conflicts_at_caution_or_above():
    zone = _zone("Z1")
    permit = PermitRecord(
        permit_id="P-1", type=PermitType.LIFTING_OPERATION, zone_id="Z1",
        issued_by="x", start_time=DEFAULT_START_TIME,
        end_time=DEFAULT_START_TIME + timedelta(hours=4), status=PermitStatus.ACTIVE,
    )
    assert check_permit_conflict(zone, [permit], "SAFE").conflict is False
    assert check_permit_conflict(zone, [permit], "CAUTION").conflict is True
    assert check_permit_conflict(zone, [permit], "HIGH").conflict is True


def test_medium_hazard_zone_requires_high_not_just_caution():
    zone = _zone("Z3")  # medium hazard
    permit = PermitRecord(
        permit_id="P-1", type=PermitType.COLD_WORK, zone_id="Z3",
        issued_by="x", start_time=DEFAULT_START_TIME,
        end_time=DEFAULT_START_TIME + timedelta(hours=4), status=PermitStatus.ACTIVE,
    )
    assert check_permit_conflict(zone, [permit], "CAUTION").conflict is False
    assert check_permit_conflict(zone, [permit], "HIGH").conflict is True


@pytest.mark.parametrize(
    "path",
    [p for d in POSITIVE_DIRS for p in sorted((SCENARIOS_DIR / d).glob("*.yaml"))],
    ids=lambda p: p.stem,
)
def test_every_positive_scenario_flags_its_scripted_permit_conflict(path):
    """Step 3's Definition of Done: the permit-conflict checker correctly
    flags the scripted conflict (permit active + rising gas/degrading
    compliance in a hazardous zone) for every authored positive scenario."""
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = _zone(config.zone)
    points = score_series(_signal_values(out))

    peak_point = max(points, key=lambda p: abs(p.z_score))
    peak_time = DEFAULT_START_TIME + timedelta(seconds=5 * peak_point.index)

    active = active_permits_at(out.permits, config.zone, peak_time)
    result = check_permit_conflict(zone, active, peak_point.risk_level)
    assert result.conflict is True, f"{path.stem}: expected a conflict at peak anomaly"
