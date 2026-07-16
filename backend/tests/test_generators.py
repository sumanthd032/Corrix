"""Permit, shift, and worker-location generators: determinism and
consistency checks, per CORRIX_DATA_METHODOLOGY.md §5, §6, §8.2."""

from datetime import datetime

from app.schemas.scenario import PermitInjectionConfig, WorkerLocationInjectionConfig
from app.simulation.permit_generator import (
    generate_background_permits,
    generate_scripted_permit,
)
from app.simulation.plant_layout import load_plant_layout
from app.simulation.shift_generator import (
    generate_background_shifts,
    generate_scenario_shift,
)
from app.simulation.worker_location_generator import (
    generate_background_pings,
    generate_scripted_ping,
)

START = datetime(2026, 7, 19, 10, 0, 0)


def test_background_permits_deterministic_and_cover_all_zones():
    layout = load_plant_layout()
    p1 = generate_background_permits(layout, 90, seed=7, start_time=START)
    p2 = generate_background_permits(layout, 90, seed=7, start_time=START)
    assert [p.permit_id for p in p1] == [p.permit_id for p in p2]
    assert len(p1) > 0


def test_scripted_permit_matches_injection_config():
    config = PermitInjectionConfig(
        type="lifting_operation", inject_at_minute=20, linked_checklist_id="CHK-0410"
    )
    permit = generate_scripted_permit(config, "Z1", START, scenario_duration_minutes=90)
    assert permit.zone_id == "Z1"
    assert permit.type.value == "lifting_operation"
    assert permit.linked_checklist_id == "CHK-0410"
    assert (permit.start_time - START).total_seconds() / 60 == 20


def test_background_shifts_are_three_and_cover_full_day():
    layout = load_plant_layout()
    shifts = generate_background_shifts(layout, START)
    assert len(shifts) == 3
    assert shifts[0].end_time == shifts[1].start_time
    assert shifts[1].end_time == shifts[2].start_time


def test_scenario_shift_changeover_lands_at_configured_minute():
    from app.schemas.scenario import ShiftInjectionConfig

    config = ShiftInjectionConfig(changeover_at_minute=68)
    shift = generate_scenario_shift(config, "Z1", START)
    assert (shift.end_time - START).total_seconds() / 60 == 68


def test_background_pings_deterministic():
    layout = load_plant_layout()
    e1 = generate_background_pings(layout, 30, seed=3, start_time=START, num_workers=5)
    e2 = generate_background_pings(layout, 30, seed=3, start_time=START, num_workers=5)
    assert [(e.badge_id, e.zone_id, e.timestamp) for e in e1] == [
        (e.badge_id, e.zone_id, e.timestamp) for e in e2
    ]


def test_scripted_ping_matches_scenario_permit_zone():
    """A worker with an active permit in the scenario's zone actually shows
    up as present in that zone, per the Step 2 Definition of Done."""
    permit_config = PermitInjectionConfig(type="lifting_operation", inject_at_minute=20)
    worker_config = WorkerLocationInjectionConfig(badge_id="W-0142", zone_entry_at_minute=55)

    permit = generate_scripted_permit(permit_config, "Z1", START, 90)
    ping = generate_scripted_ping(worker_config, "Z1", START)

    assert ping.zone_id == permit.zone_id == "Z1"
    assert permit.start_time <= ping.timestamp <= permit.end_time
