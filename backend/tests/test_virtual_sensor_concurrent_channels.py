"""Confirms Step 19's virtual channels genuinely run concurrently, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 22: one independent asyncio task
per (factory_id, zone_id, gas_type), not a single shared loop that
would serialize or overwrite zones. "Confirm, don't just assume" is
the step's own instruction, so this checks both the observable
behavior (three zones rising toward three different targets,
interleaved in arrival order) and the internal structure (three
distinct asyncio.Task objects). Hits the real public MQTT test broker;
explicitly stops every channel it starts."""

import asyncio
import json
import time
import uuid

import paho.mqtt.client as mqtt
import pytest

from app.config import get_settings
from app.ingestion.virtual_sensor_publisher import _channels, set_gas_target, stop_gas_channel

ZONE_IDS = ["Z1", "Z2", "Z3"]
GAS_TYPE = "LEL"
TARGETS = {"Z1": 20.0, "Z2": 40.0, "Z3": 60.0}
COLLECT_SECONDS = 10.0


def _subscribe_and_collect(factory_id: str, duration_seconds: float) -> list[dict]:
    settings = get_settings()
    received: list[dict] = []

    def on_message(_client, _userdata, message) -> None:
        parts = message.topic.split("/")
        if len(parts) == 4:
            received.append({"zone_id": parts[2], "payload": json.loads(message.payload.decode("utf-8"))})

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = on_message
    subscriber.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    subscriber.subscribe(f"corrix/{factory_id}/#")
    subscriber.loop_start()
    time.sleep(duration_seconds)
    subscriber.loop_stop()
    subscriber.disconnect()
    return received


@pytest.fixture
def factory_id():
    fid = f"concurrent-test-{uuid.uuid4().hex[:8]}"
    yield fid
    for zone_id in ZONE_IDS:
        stop_gas_channel(fid, zone_id, GAS_TYPE)


def test_three_zones_tick_independently_and_concurrently(factory_id):
    async def run() -> list[dict]:
        subscribe_future = asyncio.get_running_loop().run_in_executor(
            None, _subscribe_and_collect, factory_id, COLLECT_SECONDS
        )
        await asyncio.sleep(0.5)  # let the subscription register
        for zone_id in ZONE_IDS:
            await set_gas_target(factory_id, zone_id, GAS_TYPE, TARGETS[zone_id])
        return await subscribe_future

    readings = asyncio.run(run())

    by_zone: dict[str, list[float]] = {z: [] for z in ZONE_IDS}
    for r in readings:
        if r["zone_id"] in by_zone:
            by_zone[r["zone_id"]].append(r["payload"]["concentration"])

    for zone_id in ZONE_IDS:
        assert len(by_zone[zone_id]) >= 3, (
            f"{zone_id} only got {len(by_zone[zone_id])} readings in {COLLECT_SECONDS}s; "
            "expected several from an independently-ticking channel"
        )

    # Each zone's series should rise toward its OWN target, not stall or
    # drift toward another zone's target (which a shared-loop bug would
    # cause by overwriting one global current_value/target_value pair).
    for zone_id in ZONE_IDS:
        values = by_zone[zone_id]
        assert values[-1] > values[0], f"{zone_id} did not rise toward its target: {values}"
        own_distance = abs(values[-1] - TARGETS[zone_id])
        for other_zone in ZONE_IDS:
            if other_zone == zone_id:
                continue
            other_distance = abs(values[-1] - TARGETS[other_zone])
            assert own_distance < other_distance, (
                f"{zone_id}'s final reading {values[-1]:.1f} is closer to "
                f"{other_zone}'s target ({TARGETS[other_zone]}) than its own "
                f"({TARGETS[zone_id]}); channels may not be independent"
            )

    # Concurrency, not just correctness: readings from different zones
    # should be interleaved in arrival order. A single shared loop
    # publishing zones one at a time (sequentially) would instead show
    # one zone's full run before another zone's first reading.
    zone_sequence = [r["zone_id"] for r in readings if r["zone_id"] in ZONE_IDS]
    first_half = zone_sequence[: max(3, len(zone_sequence) // 2)]
    assert len(set(first_half)) > 1, (
        f"all early readings came from a single zone, suggesting sequential "
        f"rather than concurrent publishing: {zone_sequence}"
    )

    # And the internal structure really is three independent tasks, not
    # one task looping over a list of channels.
    tasks = {
        _channels[(factory_id, zone_id, GAS_TYPE)].task
        for zone_id in ZONE_IDS
        if (factory_id, zone_id, GAS_TYPE) in _channels
    }
    assert len(tasks) == 3, f"expected 3 distinct background tasks, found {len(tasks)}"
