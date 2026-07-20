"""CSV ingestion adapter, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 6."""

import asyncio

import pytest

from app.ingestion.csv_ingest import replay_csv
from app.schemas import GasSensorReading, GasType

SAMPLE_CSV = b"""ts,zone,conc,gas
2026-07-20T10:00:00Z,Z1,12.0,LEL
2026-07-20T10:00:05Z,Z1,12.4,LEL
2026-07-20T10:00:10Z,Z1,13.1,LEL
2026-07-20T10:00:15Z,Z1,14.0,LEL
2026-07-20T10:00:20Z,Z1,15.2,LEL
"""

VALID_COLUMN_MAP = {
    "timestamp": "ts",
    "zone": "zone",
    "gas_concentration": "conc",
    "gas_type": "gas",
}


async def _drain(queue: asyncio.Queue) -> list[GasSensorReading]:
    readings = []
    while not queue.empty():
        readings.append(queue.get_nowait())
    return readings


def test_replay_csv_produces_readings_in_chronological_order():
    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_csv(SAMPLE_CSV, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)
        return await _drain(queue)

    readings = asyncio.run(run())
    assert len(readings) == 5
    assert all(isinstance(r, GasSensorReading) for r in readings)
    assert all(r.zone_id == "Z1" and r.gas_type == GasType.LEL for r in readings)
    assert [r.concentration for r in readings] == [12.0, 12.4, 13.1, 14.0, 15.2]
    assert [r.timestamp for r in readings] == sorted(r.timestamp for r in readings)


def test_replay_csv_with_shuffled_rows_still_replays_in_chronological_order():
    shuffled_csv = b"""ts,zone,conc,gas
2026-07-20T10:00:10Z,Z1,13.1,LEL
2026-07-20T10:00:00Z,Z1,12.0,LEL
2026-07-20T10:00:20Z,Z1,15.2,LEL
2026-07-20T10:00:05Z,Z1,12.4,LEL
2026-07-20T10:00:15Z,Z1,14.0,LEL
"""

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_csv(shuffled_csv, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)
        return await _drain(queue)

    readings = asyncio.run(run())
    assert [r.concentration for r in readings] == [12.0, 12.4, 13.1, 14.0, 15.2]


def test_replay_csv_missing_mapped_column_raises_value_error():
    bad_column_map = dict(VALID_COLUMN_MAP, gas_concentration="does_not_exist")

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_csv(SAMPLE_CSV, bad_column_map, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="does_not_exist"):
        asyncio.run(run())


def test_replay_csv_missing_required_key_in_column_map_raises_value_error():
    incomplete_column_map = {"timestamp": "ts", "zone": "zone"}

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_csv(SAMPLE_CSV, incomplete_column_map, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="missing required keys"):
        asyncio.run(run())


def test_replay_csv_non_numeric_concentration_raises_a_clear_value_error():
    """Step 26 re-verification: a malformed column *type* (present, but
    not numeric) must raise a clear error, not silently mis-parse or
    partially import."""
    bad_type_csv = b"""ts,zone,conc,gas
2026-07-20T10:00:00Z,Z1,12.0,LEL
2026-07-20T10:00:05Z,Z1,not-a-number,LEL
"""

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_csv(bad_type_csv, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="non-numeric value"):
        asyncio.run(run())
