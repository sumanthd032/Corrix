"""Badge-log CSV ingestion adapter, a sibling to csv_ingest.py's gas
replay. Produces the same `BadgePingEvent` objects the MQTT badge
stream already produces, replayed in timestamp order, so a CSV-sourced
factory's "workers on site" state and Council evidence
(`format_site_safety_text`) reflect a real uploaded roster/turnstile
log instead of staying permanently empty.
"""

import asyncio
import io
from datetime import datetime

import pandas as pd

from app.schemas import BadgeEventType, BadgePingEvent

REQUIRED_COLUMN_MAP_KEYS = {"timestamp", "badge_id", "zone", "event_type"}


async def replay_badges(
    file_bytes: bytes,
    column_map: dict,
    speed_multiplier: float,
    queue: "asyncio.Queue[BadgePingEvent]",
) -> None:
    """Replays a badge-log CSV's rows in chronological order onto
    `queue`, paced exactly like `csv_ingest.replay_csv`. `column_map`
    maps this adapter's required logical fields to the CSV's actual
    column names, e.g. `{"timestamp": "ts", "badge_id": "badge",
    "zone": "zone_id", "event_type": "event"}`. `event_type` values
    must be one of `zone_entry`, `zone_exit`, `heartbeat`.

    Raises `ValueError` naming the offending column/value on a
    missing/mistyped mapping or an unrecognized event type, rather than
    silently skipping or mis-mapping a row.
    """
    missing_keys = REQUIRED_COLUMN_MAP_KEYS - column_map.keys()
    if missing_keys:
        raise ValueError(f"column_map is missing required keys: {sorted(missing_keys)}")

    df = pd.read_csv(io.BytesIO(file_bytes))

    for logical_key in REQUIRED_COLUMN_MAP_KEYS:
        column_name = column_map[logical_key]
        if column_name not in df.columns:
            raise ValueError(
                f"column_map[{logical_key!r}] references column {column_name!r}, "
                f"which is not present in the uploaded CSV (columns: {list(df.columns)})"
            )

    timestamp_column = column_map["timestamp"]
    badge_column = column_map["badge_id"]
    zone_column = column_map["zone"]
    event_column = column_map["event_type"]

    try:
        parsed_timestamps = pd.to_datetime(df[timestamp_column])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"column_map['timestamp'] column {timestamp_column!r} could not be parsed as a "
            f"timestamp: {exc}"
        ) from exc

    df = df.assign(**{timestamp_column: parsed_timestamps})
    df = df.sort_values(timestamp_column).reset_index(drop=True)

    previous_timestamp: datetime | None = None
    for _, row in df.iterrows():
        timestamp: datetime = row[timestamp_column].to_pydatetime()
        if previous_timestamp is not None:
            delta_seconds = (timestamp - previous_timestamp).total_seconds()
            wait_seconds = max(0.0, delta_seconds / speed_multiplier)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
        previous_timestamp = timestamp

        try:
            event_type = BadgeEventType(row[event_column])
        except ValueError as exc:
            raise ValueError(
                f"row has an unrecognized event_type {row[event_column]!r}: {exc}"
            ) from exc

        event = BadgePingEvent(
            badge_id=str(row[badge_column]),
            zone_id=str(row[zone_column]),
            timestamp=timestamp,
            event_type=event_type,
        )
        await queue.put(event)
