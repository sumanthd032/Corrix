"""Permit-log CSV ingestion adapter, a sibling to csv_ingest.py's gas
replay. Produces the same `PermitRecord` objects the MQTT permit stream
already produces, replayed in start_time order, so a CSV-sourced
factory's Council convenings can cite real active permits instead of
`format_permit_text` always reporting none on file (the live-factory
websocket already knows how to track `PermitRecord`s from the queue;
this only adds a second real source for them, alongside the gas CSV).
"""

import asyncio
import io
from datetime import datetime

import pandas as pd

from app.schemas import PermitRecord, PermitStatus, PermitType

REQUIRED_COLUMN_MAP_KEYS = {"permit_id", "type", "zone", "issued_by", "start_time", "end_time", "status"}
OPTIONAL_COLUMN_MAP_KEYS = {"linked_checklist_id"}


async def replay_permits(
    file_bytes: bytes,
    column_map: dict,
    speed_multiplier: float,
    queue: "asyncio.Queue[PermitRecord]",
) -> None:
    """Replays a permit-log CSV's rows in start_time order onto `queue`,
    paced exactly like `csv_ingest.replay_csv`. `column_map` maps this
    adapter's required logical fields to the CSV's actual column names,
    e.g. `{"permit_id": "id", "type": "permit_type", "zone": "zone_id",
    "issued_by": "issuer", "start_time": "start", "end_time": "end",
    "status": "status"}` (`linked_checklist_id` is optional).

    Raises `ValueError` naming the offending column/value on a
    missing/mistyped mapping or an unrecognized permit type or status,
    rather than silently skipping or mis-mapping a row.
    """
    missing_keys = REQUIRED_COLUMN_MAP_KEYS - column_map.keys()
    if missing_keys:
        raise ValueError(f"column_map is missing required keys: {sorted(missing_keys)}")

    df = pd.read_csv(io.BytesIO(file_bytes))

    for logical_key in REQUIRED_COLUMN_MAP_KEYS | (OPTIONAL_COLUMN_MAP_KEYS & column_map.keys()):
        column_name = column_map[logical_key]
        if column_name not in df.columns:
            raise ValueError(
                f"column_map[{logical_key!r}] references column {column_name!r}, "
                f"which is not present in the uploaded CSV (columns: {list(df.columns)})"
            )

    permit_id_column = column_map["permit_id"]
    type_column = column_map["type"]
    zone_column = column_map["zone"]
    issued_by_column = column_map["issued_by"]
    start_column = column_map["start_time"]
    end_column = column_map["end_time"]
    status_column = column_map["status"]
    checklist_column = column_map.get("linked_checklist_id")

    try:
        parsed_start_times = pd.to_datetime(df[start_column])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"column_map['start_time'] column {start_column!r} could not be parsed as a "
            f"timestamp: {exc}"
        ) from exc

    try:
        parsed_end_times = pd.to_datetime(df[end_column])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"column_map['end_time'] column {end_column!r} could not be parsed as a "
            f"timestamp: {exc}"
        ) from exc

    df = df.assign(**{start_column: parsed_start_times, end_column: parsed_end_times})
    df = df.sort_values(start_column).reset_index(drop=True)

    previous_timestamp: datetime | None = None
    for _, row in df.iterrows():
        start_time: datetime = row[start_column].to_pydatetime()
        if previous_timestamp is not None:
            delta_seconds = (start_time - previous_timestamp).total_seconds()
            wait_seconds = max(0.0, delta_seconds / speed_multiplier)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
        previous_timestamp = start_time

        try:
            permit_type = PermitType(row[type_column])
        except ValueError as exc:
            raise ValueError(
                f"row has an unrecognized permit type {row[type_column]!r}: {exc}"
            ) from exc

        try:
            status = PermitStatus(row[status_column])
        except ValueError as exc:
            raise ValueError(f"row has an unrecognized status {row[status_column]!r}: {exc}") from exc

        record = PermitRecord(
            permit_id=str(row[permit_id_column]),
            type=permit_type,
            zone_id=str(row[zone_column]),
            issued_by=str(row[issued_by_column]),
            start_time=start_time,
            end_time=row[end_column].to_pydatetime(),
            status=status,
            linked_checklist_id=(
                str(row[checklist_column])
                if checklist_column and pd.notna(row[checklist_column])
                else None
            ),
        )
        await queue.put(record)
