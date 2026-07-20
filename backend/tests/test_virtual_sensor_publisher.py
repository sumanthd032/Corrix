"""Virtual Sensor Simulator backend, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 19. Hits the real public MQTT test
broker (see app/ingestion/README.md), with a unique per-test
factory_id/zone_id so this doesn't collide with any other user of that
shared broker. Explicitly stops every channel it starts, since a
channel's background task otherwise runs forever."""

import asyncio
import time
import uuid

import paho.mqtt.client as mqtt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.ingestion.virtual_sensor_publisher import set_gas_target, stop_gas_channel
from app.main import app

client = TestClient(app)


def _subscribe_and_collect(topic: str, duration_seconds: float) -> list[dict]:
    settings = get_settings()
    received: list[dict] = []

    def on_message(_client, _userdata, message) -> None:
        import json

        received.append(json.loads(message.payload.decode("utf-8")))

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = on_message
    subscriber.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    subscriber.subscribe(topic)
    subscriber.loop_start()
    time.sleep(duration_seconds)
    subscriber.loop_stop()
    subscriber.disconnect()
    return received


@pytest.fixture
def factory_zone():
    factory_id = f"vsp-test-{uuid.uuid4().hex[:8]}"
    zone_id = "Z1"
    yield factory_id, zone_id
    stop_gas_channel(factory_id, zone_id, "LEL")


def test_set_gas_target_publishes_a_rising_jittering_series_not_a_smooth_jump(factory_zone):
    factory_id, zone_id = factory_zone
    topic = f"corrix/{factory_id}/{zone_id}/gas"

    async def run() -> list[dict]:
        subscribe_started = asyncio.get_running_loop().run_in_executor(
            None, _subscribe_and_collect, topic, 8.0
        )
        await asyncio.sleep(0.5)  # let the subscription register before targeting
        await set_gas_target(factory_id, zone_id, "LEL", target_concentration=25.0)
        return await subscribe_started

    readings = asyncio.run(run())

    assert len(readings) >= 3, f"expected several readings over 8s, got {len(readings)}"
    values = [r["concentration"] for r in readings]

    # Ambient baseline for LEL is 0.0; the series should climb toward
    # the target rather than starting there or jumping straight to it.
    assert values[0] < 25.0
    assert values[0] != 25.0
    assert values[-1] > values[0], f"expected a rising trend, got {values}"

    # Not a smooth staircase: consecutive deltas shouldn't all be identical.
    deltas = [round(b - a, 6) for a, b in zip(values, values[1:])]
    assert len(set(deltas)) > 1, f"expected jitter, all deltas identical: {deltas}"

    assert all(r["gas_type"] == "LEL" for r in readings)
    assert all(r["unit"] == "ppm" for r in readings)


def test_virtual_gas_endpoint_returns_200(factory_zone):
    factory_id, zone_id = factory_zone
    response = client.post(
        f"/api/virtual-sensor/{factory_id}/{zone_id}/gas",
        json={"gas_type": "LEL", "target_concentration": 10.0},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_virtual_gas_endpoint_rejects_an_unknown_gas_type(factory_zone):
    factory_id, zone_id = factory_zone
    response = client.post(
        f"/api/virtual-sensor/{factory_id}/{zone_id}/gas",
        json={"gas_type": "NOT_A_GAS", "target_concentration": 10.0},
    )
    assert response.status_code == 422


def test_virtual_badge_endpoint_returns_200(factory_zone):
    factory_id, zone_id = factory_zone
    response = client.post(
        f"/api/virtual-sensor/{factory_id}/{zone_id}/badge",
        json={"badge_id": "W-BG-001", "entering": True},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_virtual_permit_endpoint_returns_200(factory_zone):
    factory_id, zone_id = factory_zone
    response = client.post(
        f"/api/virtual-sensor/{factory_id}/{zone_id}/permit",
        json={"permit_type": "hot_work"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_virtual_permit_endpoint_rejects_an_unknown_permit_type(factory_zone):
    factory_id, zone_id = factory_zone
    response = client.post(
        f"/api/virtual-sensor/{factory_id}/{zone_id}/permit",
        json={"permit_type": "not_a_real_permit"},
    )
    assert response.status_code == 422
