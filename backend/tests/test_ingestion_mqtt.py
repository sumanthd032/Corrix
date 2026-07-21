"""MQTT ingestion adapter, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 18.
Hits the real public test broker (see app/ingestion/README.md), the
same broker app.config.Settings.mqtt_broker_host/port already points
at, with a unique per-test factory_id so this doesn't collide with any
other user of that shared, third-party broker."""

import asyncio
import json
import time
import uuid

import paho.mqtt.client as mqtt

from app.config import get_settings
from app.ingestion.mqtt_ingest import stream_mqtt
from app.schemas import BadgePingEvent, GasSensorReading, GasType, PermitRecord


def _publish(factory_id: str, zone_id: str, reading_type: str, body: str) -> None:
    settings = get_settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    client.loop_start()
    client.publish(f"corrix/{factory_id}/{zone_id}/{reading_type}", body)
    time.sleep(0.5)  # let the publish actually go out before disconnecting
    client.loop_stop()
    client.disconnect()


def test_stream_mqtt_parses_well_formed_messages_and_drops_a_malformed_one():
    factory_id = f"mqtt-test-{uuid.uuid4().hex[:8]}"
    settings = get_settings()

    async def run() -> list:
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(
            stream_mqtt(factory_id, settings.mqtt_broker_host, settings.mqtt_broker_port, queue)
        )
        await asyncio.sleep(1.5)  # let the subscription actually register

        _publish(
            factory_id,
            "Z1",
            "gas",
            json.dumps(
                {"gas_type": "LEL", "concentration": 12.3, "unit": "ppm", "timestamp": "2026-07-20T10:00:00+00:00"}
            ),
        )
        _publish(
            factory_id,
            "Z1",
            "badge",
            json.dumps({"badge_id": "W-BG-001", "event_type": "zone_entry", "timestamp": "2026-07-20T10:00:05+00:00"}),
        )
        _publish(
            factory_id,
            "Z2",
            "permit",
            json.dumps(
                {
                    "permit_id": "P-001",
                    "type": "hot_work",
                    "issued_by": "officer-1",
                    "start_time": "2026-07-20T09:00:00+00:00",
                    "end_time": "2026-07-20T11:00:00+00:00",
                    "status": "active",
                }
            ),
        )
        _publish(factory_id, "Z1", "gas", "not valid json")  # malformed, must be dropped

        readings = []
        try:
            for _ in range(3):
                readings.append(await asyncio.wait_for(queue.get(), timeout=15))
        except asyncio.TimeoutError:
            pass

        extra_item = None
        try:
            extra_item = queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        return readings, extra_item

    readings, extra_item = asyncio.run(run())

    assert len(readings) == 3, f"expected exactly 3 parsed readings, got {len(readings)}: {readings}"
    assert extra_item is None, f"malformed message should not have produced a 4th queue item: {extra_item}"

    gas = next(r for r in readings if isinstance(r, GasSensorReading))
    assert gas.zone_id == "Z1"
    assert gas.gas_type == GasType.LEL
    assert gas.concentration == 12.3

    badge = next(r for r in readings if isinstance(r, BadgePingEvent))
    assert badge.zone_id == "Z1"
    assert badge.badge_id == "W-BG-001"

    permit = next(r for r in readings if isinstance(r, PermitRecord))
    assert permit.zone_id == "Z2"
    assert permit.permit_id == "P-001"
