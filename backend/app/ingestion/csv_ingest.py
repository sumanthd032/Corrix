"""CSV historian-replay ingestion adapter, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 6: the safety-net data source that
proves the live pipeline accepts arbitrary real data, no broker or
simulator required. Produces the same `GasSensorReading` objects
`app/simulation/gas_process.run_gas_process` already produces, so
downstream code (the live-factory WebSocket, Step 8) can't tell the
difference between a scripted scenario and a real uploaded file.
"""

import asyncio
import io
from datetime import datetime

import pandas as pd

from app.schemas import GasSensorReading, GasType

REQUIRED_COLUMN_MAP_KEYS = {"timestamp", "zone", "gas_concentration", "gas_type"}
DEFAULT_UNIT = "ppm"


async def replay_csv(
    file_bytes: bytes,
    column_map: dict,
    speed_multiplier: float,
    queue: "asyncio.Queue[GasSensorReading]",
) -> None:
    """Replays a historian CSV's rows in chronological order onto `queue`,
    paced at `(real_dt_between_rows / speed_multiplier)` so a 1x replay
    matches the historian's real pace and, e.g., 30x makes it watchable
    in a live demo. `column_map` maps this adapter's required logical
    fields to the CSV's actual column names, e.g.
    `{"timestamp": "ts", "zone": "zone_id", "gas_concentration": "conc",
    "gas_type": "gas", "unit": "unit"}` ("unit" is optional; defaults to
    "ppm" when the CSV doesn't carry it).

    Raises `ValueError` naming the offending column on a missing/mistyped
    mapping rather than silently skipping or mis-mapping a column.
    """
    missing_keys = REQUIRED_COLUMN_MAP_KEYS - column_map.keys()
    if missing_keys:
        raise ValueError(f"column_map is missing required keys: {sorted(missing_keys)}")

    df = pd.read_csv(io.BytesIO(file_bytes))

    for logical_key in REQUIRED_COLUMN_MAP_KEYS | ({"unit"} & column_map.keys()):
        column_name = column_map[logical_key]
        if column_name not in df.columns:
            raise ValueError(
                f"column_map[{logical_key!r}] references column {column_name!r}, "
                f"which is not present in the uploaded CSV (columns: {list(df.columns)})"
            )

    timestamp_column = column_map["timestamp"]
    zone_column = column_map["zone"]
    gas_concentration_column = column_map["gas_concentration"]
    gas_type_column = column_map["gas_type"]
    unit_column = column_map.get("unit")

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
            gas_type = GasType(row[gas_type_column])
        except ValueError as exc:
            raise ValueError(
                f"row has an unrecognized gas_type {row[gas_type_column]!r}: {exc}"
            ) from exc

        reading = GasSensorReading(
            zone_id=str(row[zone_column]),
            gas_type=gas_type,
            concentration=float(row[gas_concentration_column]),
            unit=str(row[unit_column]) if unit_column else DEFAULT_UNIT,
            timestamp=timestamp,
        )
        await queue.put(reading)
