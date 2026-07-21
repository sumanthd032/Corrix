"""Badge-log CSV ingestion adapter, a sibling to test_ingestion_csv.py:
proves BYOF's CSV data source can carry real badge/turnstile events, so
"workers on site" stops being permanently empty for a CSV factory."""

import asyncio

import pytest

from app.ingestion.badge_ingest import replay_badges
from app.schemas import BadgeEventType, BadgePingEvent

SAMPLE_CSV = b"""ts,badge,z,ev
2026-07-21T06:00:00Z,W-BG-001,Z1,zone_entry
2026-07-21T06:05:00Z,W-BG-002,Z1,zone_entry
2026-07-21T06:10:00Z,W-BG-001,Z1,zone_exit
"""

VALID_COLUMN_MAP = {
    "timestamp": "ts",
    "badge_id": "badge",
    "zone": "z",
    "event_type": "ev",
}


async def _drain(queue: asyncio.Queue) -> list[BadgePingEvent]:
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def test_replay_badges_produces_events_in_chronological_order():
    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_badges(SAMPLE_CSV, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)
        return await _drain(queue)

    events = asyncio.run(run())
    assert len(events) == 3
    assert all(isinstance(e, BadgePingEvent) for e in events)
    assert events[0].badge_id == "W-BG-001"
    assert events[0].event_type == BadgeEventType.ZONE_ENTRY
    assert events[2].event_type == BadgeEventType.ZONE_EXIT


def test_replay_badges_missing_required_key_raises_value_error():
    incomplete_column_map = {"timestamp": "ts", "badge_id": "badge"}

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_badges(SAMPLE_CSV, incomplete_column_map, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="missing required keys"):
        asyncio.run(run())


def test_replay_badges_unrecognized_event_type_raises_value_error():
    bad_event_csv = b"""ts,badge,z,ev
2026-07-21T06:00:00Z,W-BG-001,Z1,badge_swipe
"""

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_badges(bad_event_csv, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="unrecognized event_type"):
        asyncio.run(run())


def test_replay_badges_missing_mapped_column_raises_value_error():
    bad_column_map = dict(VALID_COLUMN_MAP, zone="does_not_exist")

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_badges(SAMPLE_CSV, bad_column_map, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="does_not_exist"):
        asyncio.run(run())
