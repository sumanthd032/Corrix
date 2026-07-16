"""Permit-to-work generator, per CORRIX_DATA_METHODOLOGY.md §5.

Two parts: the scenario's own scripted/injected permit (the one the
compound-risk narrative depends on), and a continuous background rate of
routine, non-conflicting permits across all zones so the plant looks
operationally busy rather than artificially quiet outside "the" scenario —
this also matters for negative-control runs (§12.4), which get the
background generator only.
"""

from datetime import datetime, timedelta

import numpy as np

from app.schemas import PermitRecord, PermitStatus, PermitType, PlantLayout
from app.schemas.scenario import PermitInjectionConfig

BACKGROUND_ISSUERS = [
    "Shift Supervisor A. Rao",
    "Shift Supervisor N. Verma",
    "Area Engineer P. Iyer",
    "Area Engineer S. Krishnan",
]

# Only low-conflict-risk permit types are used for background traffic —
# deterministic conflict checking is Step 3's job; Step 2 just needs
# plausible, non-scenario-narrative activity in the background.
BACKGROUND_PERMIT_TYPES = [PermitType.COLD_WORK, PermitType.ELECTRICAL_ISOLATION]


def generate_background_permits(
    plant_layout: PlantLayout,
    duration_minutes: int,
    seed: int,
    start_time: datetime,
    permits_per_zone_per_hour: float = 0.4,
) -> list[PermitRecord]:
    rng = np.random.default_rng(seed)
    permits: list[PermitRecord] = []
    counter = 0
    for zone in plant_layout.zones:
        expected_count = permits_per_zone_per_hour * (duration_minutes / 60.0)
        n = rng.poisson(max(expected_count, 0.1))
        for _ in range(int(n)):
            counter += 1
            offset_minutes = rng.uniform(0, duration_minutes)
            length_minutes = rng.uniform(30, 180)
            permit_start = start_time + timedelta(minutes=offset_minutes)
            permits.append(
                PermitRecord(
                    permit_id=f"P-BG-{seed}-{counter:04d}",
                    type=BACKGROUND_PERMIT_TYPES[
                        rng.integers(0, len(BACKGROUND_PERMIT_TYPES))
                    ],
                    zone_id=zone.zone_id,
                    issued_by=BACKGROUND_ISSUERS[
                        rng.integers(0, len(BACKGROUND_ISSUERS))
                    ],
                    start_time=permit_start,
                    end_time=permit_start + timedelta(minutes=length_minutes),
                    status=PermitStatus.ACTIVE,
                    linked_checklist_id=None,
                )
            )
    return permits


def generate_scripted_permit(
    config: PermitInjectionConfig,
    zone_id: str,
    start_time: datetime,
    scenario_duration_minutes: int,
) -> PermitRecord:
    permit_start = start_time + timedelta(minutes=config.inject_at_minute)
    permit_end = start_time + timedelta(minutes=scenario_duration_minutes)
    return PermitRecord(
        permit_id=f"P-SCRIPT-{zone_id}-{config.inject_at_minute:.0f}",
        type=PermitType(config.type),
        zone_id=zone_id,
        issued_by="Shift Supervisor A. Rao",
        start_time=permit_start,
        end_time=permit_end,
        status=PermitStatus.ACTIVE,
        linked_checklist_id=config.linked_checklist_id,
    )
