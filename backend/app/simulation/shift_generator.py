"""Shift roster generator, per CORRIX_DATA_METHODOLOGY.md §6.

Standard three-shift industrial pattern (06:00-14:00, 14:00-22:00,
22:00-06:00), deterministic, not seeded/stochastic, since shift
boundaries don't vary run to run. Plus one scenario-specific ShiftRecord
whose changeover lands exactly at the scenario's configured
`changeover_at_minute`, so the Shift Operations agent can answer "is a
changeover imminent in this zone specifically" for the scripted scenario.
"""

from datetime import datetime, timedelta

from app.schemas import PlantLayout, ShiftRecord
from app.schemas.scenario import ShiftInjectionConfig

STANDARD_SHIFT_LENGTH_HOURS = 8
DEFAULT_CHANGEOVER_WINDOW_MINUTES = 15


def _day_start(reference: datetime) -> datetime:
    return reference.replace(hour=0, minute=0, second=0, microsecond=0)


def generate_background_shifts(
    plant_layout: PlantLayout,
    reference_time: datetime,
) -> list[ShiftRecord]:
    day_start = _day_start(reference_time)
    all_zone_ids = [z.zone_id for z in plant_layout.zones]
    shift_starts = [0, 8, 16]  # hours past midnight
    return [
        ShiftRecord(
            shift_id=f"shift-{i}",
            start_time=day_start + timedelta(hours=h),
            end_time=day_start + timedelta(hours=h + STANDARD_SHIFT_LENGTH_HOURS),
            changeover_window_minutes=DEFAULT_CHANGEOVER_WINDOW_MINUTES,
            zones=all_zone_ids,
        )
        for i, h in enumerate(shift_starts)
    ]


def generate_scenario_shift(
    config: ShiftInjectionConfig,
    zone_id: str,
    start_time: datetime,
) -> ShiftRecord:
    changeover_time = start_time + timedelta(minutes=config.changeover_at_minute)
    shift_start = changeover_time - timedelta(hours=STANDARD_SHIFT_LENGTH_HOURS)
    return ShiftRecord(
        shift_id=f"shift-scripted-{zone_id}",
        start_time=shift_start,
        end_time=changeover_time,
        changeover_window_minutes=DEFAULT_CHANGEOVER_WINDOW_MINUTES,
        zones=[zone_id],
    )
