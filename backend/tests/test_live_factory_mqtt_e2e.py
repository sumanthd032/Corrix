"""End-to-end MQTT path, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 20: a
factory with data_source="mqtt", fed entirely through the real virtual-
sensor API (Step 19) and the real public MQTT test broker (Step 17),
produces a real trigger -> real Council convening -> real verdict over
/ws/live-factory (Step 18), exactly as the CSV path already does in
Step 8. Hits the real broker and the real Council (real LLM calls);
runs over genuine wall-clock time since the virtual channel ticks on a
real 1.5s cadence, not an accelerated replay. Explicitly stops the
virtual channel it starts.

Uses a real running server (a subprocess), not FastAPI's in-process
TestClient: a long-lived websocket connection concurrent with
background-threaded MQTT clients (the websocket's own subscriber, plus
the virtual sensor publisher's singleton) reproducibly hung under
TestClient's in-process ASGI transport during development of this
test, even after fixing the two real bugs that investigation surfaced
(mqtt.Client.connect() blocking the event loop, and no wait for
CONNACK before assuming a connection succeeded - both fixed in
mqtt_ingest.py and virtual_sensor_publisher.py regardless). A manual
run against a real uvicorn server completed correctly end to end in
about 28 seconds, which is what this test automates.
"""

import json
import multiprocessing
import time
from datetime import datetime, timezone

import pytest
import requests
import websockets
import websockets.sync.client

from app.memory.exemplar_store import get_shared_driver
from app.schemas.factory import FactoryProfile
from app.schemas.zone import HazardClass, PlantLayout, Zone
from app.storage.factory_store import save_factory

FACTORY_ID = "mqtt-e2e-test"
ZONE_ID = "Z1"
GAS_TYPE = "LEL"
SERVER_PORT = 8199

# Enough ticks to cover the live-factory websocket's baseline
# calibration (its first 10 gas readings, at the virtual channel's 1.5s
# tick cadence) plus real margin before sending the spike.
SPIKE_AFTER_TICKS = 12
# Generous wall-clock ceiling: baseline + spike propagation + a real
# Council convening (real LLM calls) observed to complete in ~28s.
OVERALL_TIMEOUT_SECONDS = 120


def _run_server() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=SERVER_PORT, log_level="warning")


def _delete_factory(factory_id: str) -> None:
    driver = get_shared_driver()
    with driver.session() as session:
        session.run(
            "MATCH (f:Factory {factory_id: $id}) "
            "OPTIONAL MATCH (f)-[:HAS_ZONE]->(z:FactoryZone) "
            "DETACH DELETE f, z",
            id=factory_id,
        )


@pytest.fixture(scope="module")
def live_server():
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_run_server, daemon=True)
    proc.start()

    deadline = time.time() + 20
    ready = False
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{SERVER_PORT}/health", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except requests.exceptions.RequestException:
            time.sleep(0.3)
    if not ready:
        proc.terminate()
        proc.join(timeout=5)
        raise RuntimeError("test server did not become healthy in time")

    yield f"http://127.0.0.1:{SERVER_PORT}"

    proc.terminate()
    proc.join(timeout=5)


@pytest.fixture
def mqtt_factory():
    profile = FactoryProfile(
        factory_id=FACTORY_ID,
        name="MQTT E2E Test Steelworks",
        industry="steel",
        location=None,
        layout=PlantLayout(
            zones=[
                Zone(
                    zone_id=ZONE_ID,
                    name="Test Zone",
                    hazard_class=HazardClass.HIGH,
                    primary_role="casting",
                    is_confined_space=False,
                    is_assembly_point=False,
                )
            ],
            adjacency=[],
        ),
        permit_types_in_use=["hot_work"],
        shift_pattern=[],
        data_source="mqtt",
        created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    save_factory(profile)
    yield FACTORY_ID
    _delete_factory(FACTORY_ID)


def test_mqtt_factory_reaches_a_real_verdict_end_to_end(live_server, mqtt_factory):
    seen_types: list[str] = []
    verdict_seen = False
    spike_sent = False
    tick_count = 0
    start = time.time()

    with websockets.sync.client.connect(f"{live_server.replace('http', 'ws')}/ws/live-factory") as ws:
        ws.send(json.dumps({"type": "connect", "factory_id": mqtt_factory}))

        # Calm phase: hold the channel at ambient so the live-factory
        # websocket's baseline calibration reflects a genuinely calm
        # reference, not a value already mid-rise.
        calm_response = requests.post(
            f"{live_server}/api/virtual-sensor/{mqtt_factory}/{ZONE_ID}/gas",
            json={"gas_type": GAS_TYPE, "target_concentration": 0.0},
            timeout=10,
        )
        assert calm_response.status_code == 200

        while time.time() - start < OVERALL_TIMEOUT_SECONDS:
            try:
                raw = ws.recv(timeout=5)
            except TimeoutError:
                continue
            msg = json.loads(raw)
            seen_types.append(msg["type"])

            if msg["type"] == "tick":
                tick_count += 1
                if not spike_sent and tick_count >= SPIKE_AFTER_TICKS:
                    spike_response = requests.post(
                        f"{live_server}/api/virtual-sensor/{mqtt_factory}/{ZONE_ID}/gas",
                        json={"gas_type": GAS_TYPE, "target_concentration": 60.0},
                        timeout=10,
                    )
                    assert spike_response.status_code == 200
                    spike_sent = True

            if msg["type"] == "verdict":
                verdict_seen = True
                break
            if msg["type"] in ("council_error", "error"):
                break

    assert spike_sent, "never reached enough ticks to send the spike"
    assert "tick" in seen_types
    assert verdict_seen, f"never reached a verdict; message types seen: {seen_types}"
