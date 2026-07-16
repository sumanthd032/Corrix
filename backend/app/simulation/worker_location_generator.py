"""Worker-location/badge-ping generator, per CORRIX_DATA_METHODOLOGY.md §8.2.

Zone-level granularity, mirroring real badge/turnstile RTLS reporting, not
fabricated continuous GPS. Background pings (a small roster stationed
across zones, low-hazard-weighted) plus one scripted zone-entry event
consistent with the scenario's own permit/zone context — a worker with an
active permit in the scenario's zone actually shows up as present there.
"""

from datetime import datetime, timedelta

import numpy as np

from app.schemas import BadgeEventType, BadgePingEvent, PlantLayout
from app.schemas.scenario import WorkerLocationInjectionConfig

BACKGROUND_PING_INTERVAL_SECONDS = 45


def generate_background_pings(
    plant_layout: PlantLayout,
    duration_minutes: int,
    seed: int,
    start_time: datetime,
    num_workers: int = 20,
) -> list[BadgePingEvent]:
    rng = np.random.default_rng(seed)
    # Low-hazard zones get more of the background roster, matching a real
    # plant's actual worker distribution (control room, perimeter staffed
    # more continuously than a confined-space gas vault).
    zones = plant_layout.zones
    weights = np.array(
        [3.0 if z.hazard_class.value == "low" else 1.0 for z in zones]
    )
    weights = weights / weights.sum()

    events: list[BadgePingEvent] = []
    n_ticks = int(duration_minutes * 60 / BACKGROUND_PING_INTERVAL_SECONDS)
    for w in range(num_workers):
        badge_id = f"W-BG-{seed}-{w:03d}"
        home_zone = zones[rng.choice(len(zones), p=weights)].zone_id
        events.append(
            BadgePingEvent(
                badge_id=badge_id,
                zone_id=home_zone,
                timestamp=start_time,
                event_type=BadgeEventType.ZONE_ENTRY,
            )
        )
        for tick in range(1, n_ticks + 1):
            events.append(
                BadgePingEvent(
                    badge_id=badge_id,
                    zone_id=home_zone,
                    timestamp=start_time
                    + timedelta(seconds=tick * BACKGROUND_PING_INTERVAL_SECONDS),
                    event_type=BadgeEventType.HEARTBEAT,
                )
            )
    return events


def generate_scripted_ping(
    config: WorkerLocationInjectionConfig,
    zone_id: str,
    start_time: datetime,
) -> BadgePingEvent:
    return BadgePingEvent(
        badge_id=config.badge_id,
        zone_id=zone_id,
        timestamp=start_time + timedelta(minutes=config.zone_entry_at_minute),
        event_type=BadgeEventType.ZONE_ENTRY,
    )
