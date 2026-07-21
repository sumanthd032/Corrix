"""Permit-log CSV ingestion adapter, a sibling to test_ingestion_csv.py:
proves BYOF's CSV data source can carry real permit records, not just
the wizard's permit_types_in_use list."""

import asyncio

import pytest

from app.ingestion.permit_ingest import replay_permits
from app.schemas import PermitRecord, PermitStatus, PermitType

SAMPLE_CSV = b"""id,ptype,zone,issuer,start,end,st,checklist
P-1001,hot_work,Z1,J. Rao,2026-07-21T06:00:00Z,2026-07-21T07:00:00Z,active,CL-9
P-1002,confined_space_entry,Z3,A. Menon,2026-07-21T06:05:00Z,2026-07-21T06:45:00Z,active,
"""

VALID_COLUMN_MAP = {
    "permit_id": "id",
    "type": "ptype",
    "zone": "zone",
    "issued_by": "issuer",
    "start_time": "start",
    "end_time": "end",
    "status": "st",
    "linked_checklist_id": "checklist",
}


async def _drain(queue: asyncio.Queue) -> list[PermitRecord]:
    records = []
    while not queue.empty():
        records.append(queue.get_nowait())
    return records


def test_replay_permits_produces_records_in_start_time_order():
    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_permits(SAMPLE_CSV, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)
        return await _drain(queue)

    records = asyncio.run(run())
    assert len(records) == 2
    assert all(isinstance(r, PermitRecord) for r in records)
    assert records[0].permit_id == "P-1001"
    assert records[0].type == PermitType.HOT_WORK
    assert records[0].zone_id == "Z1"
    assert records[0].status == PermitStatus.ACTIVE
    assert records[0].linked_checklist_id == "CL-9"
    assert records[1].permit_id == "P-1002"
    assert records[1].linked_checklist_id is None


def test_replay_permits_missing_required_key_raises_value_error():
    incomplete_column_map = {"permit_id": "id", "type": "ptype"}

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_permits(SAMPLE_CSV, incomplete_column_map, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="missing required keys"):
        asyncio.run(run())


def test_replay_permits_unrecognized_type_raises_value_error():
    bad_type_csv = b"""id,ptype,zone,issuer,start,end,st,checklist
P-1,crane_operation,Z1,J. Rao,2026-07-21T06:00:00Z,2026-07-21T07:00:00Z,active,
"""

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_permits(bad_type_csv, VALID_COLUMN_MAP, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="unrecognized permit type"):
        asyncio.run(run())


def test_replay_permits_missing_mapped_column_raises_value_error():
    bad_column_map = dict(VALID_COLUMN_MAP, status="does_not_exist")

    async def run():
        queue: asyncio.Queue = asyncio.Queue()
        await replay_permits(SAMPLE_CSV, bad_column_map, speed_multiplier=1_000_000.0, queue=queue)

    with pytest.raises(ValueError, match="does_not_exist"):
        asyncio.run(run())
