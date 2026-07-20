"""MQTT ingestion adapter (subscriber side), per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 18: the flagship hardware-free
path. Subscribes to corrix/{factory_id}/# and parses each message into
the matching schema object (GasSensorReading, BadgePingEvent, or
PermitRecord), exactly as csv_ingest.py already does for the CSV path,
so app/api/live_factory_websocket.py can't tell the two ingestion
sources apart downstream. A malformed topic or payload is logged and
dropped, never raised into the caller, since one bad message must not
take down the whole live stream.

Topic convention, per CORRIX_REAL_DATA.md §3.3:
corrix/{factory_id}/{zone_id}/{reading_type}, reading_type one of
"gas", "badge", "permit". zone_id comes from the topic, not the
payload; the payload is a JSON object carrying the schema's remaining
fields.
"""

import asyncio
import json
import logging
from datetime import datetime

import paho.mqtt.client as mqtt

from app.schemas import (
    BadgeEventType,
    BadgePingEvent,
    GasSensorReading,
    GasType,
    PermitRecord,
    PermitStatus,
    PermitType,
)

logger = logging.getLogger(__name__)

MqttReading = GasSensorReading | BadgePingEvent | PermitRecord


def _parse_gas(zone_id: str, payload: dict) -> GasSensorReading:
    return GasSensorReading(
        zone_id=zone_id,
        gas_type=GasType(payload["gas_type"]),
        concentration=float(payload["concentration"]),
        unit=payload.get("unit", "ppm"),
        timestamp=datetime.fromisoformat(payload["timestamp"]),
    )


def _parse_badge(zone_id: str, payload: dict) -> BadgePingEvent:
    return BadgePingEvent(
        badge_id=payload["badge_id"],
        zone_id=zone_id,
        timestamp=datetime.fromisoformat(payload["timestamp"]),
        event_type=BadgeEventType(payload["event_type"]),
    )


def _parse_permit(zone_id: str, payload: dict) -> PermitRecord:
    return PermitRecord(
        permit_id=payload["permit_id"],
        type=PermitType(payload["type"]),
        zone_id=zone_id,
        issued_by=payload["issued_by"],
        start_time=datetime.fromisoformat(payload["start_time"]),
        end_time=datetime.fromisoformat(payload["end_time"]),
        status=PermitStatus(payload.get("status", "active")),
        linked_checklist_id=payload.get("linked_checklist_id"),
    )


_PARSERS = {"gas": _parse_gas, "badge": _parse_badge, "permit": _parse_permit}


async def stream_mqtt(
    factory_id: str,
    broker_host: str,
    broker_port: int,
    queue: "asyncio.Queue[MqttReading]",
) -> None:
    """Subscribes to corrix/{factory_id}/# and pushes parsed readings
    onto `queue` until this coroutine is cancelled. paho-mqtt's network
    loop runs on its own background thread (`loop_start`); `on_message`
    therefore hands off to the event loop via `call_soon_threadsafe`
    rather than touching the asyncio queue directly from that thread.
    """
    loop = asyncio.get_running_loop()

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        parts = message.topic.split("/")
        if len(parts) != 4 or parts[0] != "corrix" or parts[1] != factory_id:
            logger.warning("mqtt_ingest: ignoring message on unexpected topic %r", message.topic)
            return
        _, _, zone_id, reading_type = parts

        parser = _PARSERS.get(reading_type)
        if parser is None:
            logger.warning(
                "mqtt_ingest: unknown reading_type %r on topic %r", reading_type, message.topic
            )
            return

        try:
            payload = json.loads(message.payload.decode("utf-8"))
            reading = parser(zone_id, payload)
        except Exception as exc:
            logger.warning("mqtt_ingest: dropping malformed message on topic %r: %s", message.topic, exc)
            return

        loop.call_soon_threadsafe(queue.put_nowait, reading)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(broker_host, broker_port)
    client.subscribe(f"corrix/{factory_id}/#")
    client.loop_start()

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        client.loop_stop()
        client.disconnect()
