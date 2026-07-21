"""OPC-UA ingestion adapter (client side), per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 25: the OPC-UA analog of Step 18's
mqtt_ingest.py. Connects to a real OPC-UA server (Step 24's
virtual_scada_server.py by default) and pushes parsed
GasSensorReading objects onto a queue, the same shape csv_ingest.py
and mqtt_ingest.py already produce, so
app/api/live_factory_websocket.py can't tell the three ingestion
sources apart downstream.

Uses a real OPC-UA Subscription (subscribe_data_change), not polling:
the server pushes a data-change notification whenever a node's value
actually changes, the genuine OPC-UA client pattern. asyncua is
asyncio-native (unlike paho-mqtt, which runs its network loop on a
separate OS thread), so datachange_notification fires on the same
event loop as the caller; no call_soon_threadsafe hop is needed here.

DEFAULT_NODE_MAP assumes a factory demoed over OPC-UA has zones named
to match Step 24's demo server's fixed tag list (Z1/Z2/Z3), since that
server exposes a small, hardcoded set of tags rather than a per-factory
dynamic one. This is a documented demo-scope simplification, consistent
with Phase 5 being explicitly lower-priority than the MQTT flagship
path, not a general node-mapping system.
"""

import asyncio
import logging
from datetime import datetime, timezone

from asyncua import Client

from app.schemas import GasSensorReading, GasType

logger = logging.getLogger(__name__)

PLANT_OBJECT_NAME = "CorrixVirtualPlant"

# Browse name -> (zone_id, gas_type), matching virtual_scada_server.py's
# ZONE_TARGETS tag list.
DEFAULT_NODE_MAP: dict[str, tuple[str, str]] = {
    "Z1_LEL": ("Z1", "LEL"),
    "Z2_CO": ("Z2", "CO"),
    "Z3_H2S": ("Z3", "H2S"),
}


class _DataChangeHandler:
    def __init__(
        self,
        node_to_reading: dict[int, tuple[str, str]],
        queue: "asyncio.Queue[GasSensorReading]",
    ) -> None:
        self._node_to_reading = node_to_reading
        self._queue = queue

    def datachange_notification(self, node, val: object, _data: object) -> None:
        mapping = self._node_to_reading.get(node.nodeid.Identifier)
        if mapping is None:
            return
        zone_id, gas_type_value = mapping
        try:
            reading = GasSensorReading(
                zone_id=zone_id,
                gas_type=GasType(gas_type_value),
                concentration=float(val),  # type: ignore[arg-type]
                unit="ppm",
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.warning("opcua_ingest: dropping malformed data-change for node %s: %s", node, exc)
            return
        self._queue.put_nowait(reading)


async def stream_opcua(
    endpoint_url: str,
    queue: "asyncio.Queue[GasSensorReading]",
    node_map: dict[str, tuple[str, str]] | None = None,
) -> None:
    """Connects to `endpoint_url`, subscribes to real data-change
    notifications for every node in `node_map` (or DEFAULT_NODE_MAP),
    and pushes parsed readings onto `queue` until this coroutine is
    cancelled. Raises if the plant object or none of the mapped nodes
    can be found, rather than silently producing no data, since a
    factory with data_source="opcua" that can't reach a real server
    must never fall back to fabricated readings."""
    node_map = node_map if node_map is not None else DEFAULT_NODE_MAP

    async with Client(url=endpoint_url) as client:
        objects = await client.nodes.root.get_child(["0:Objects"])
        plant = None
        for child in await objects.get_children():
            if (await child.read_browse_name()).Name == PLANT_OBJECT_NAME:
                plant = child
                break
        if plant is None:
            raise ValueError(f"No {PLANT_OBJECT_NAME} object found at {endpoint_url}")

        node_to_reading: dict[int, tuple[str, str]] = {}
        nodes = []
        for child in await plant.get_children():
            name = (await child.read_browse_name()).Name
            if name in node_map:
                node_to_reading[child.nodeid.Identifier] = node_map[name]
                nodes.append(child)

        if not nodes:
            raise ValueError(
                f"None of {list(node_map)} were found under {PLANT_OBJECT_NAME} at {endpoint_url}"
            )

        handler = _DataChangeHandler(node_to_reading, queue)
        subscription = await client.create_subscription(500, handler)
        await subscription.subscribe_data_change(nodes)

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await subscription.delete()
