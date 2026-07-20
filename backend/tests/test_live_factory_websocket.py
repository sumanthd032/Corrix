"""The live-factory WebSocket, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 8,
wired to the CSV replay path. Hits the real dev Neo4j instance and the
real Council (real LLM calls), matching this suite's existing
discipline; cleans up the factory node and uploaded CSV it creates."""

import shutil
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.ingestion.csv_upload_store import UPLOADS_ROOT, save_uploaded_csv
from app.main import app
from app.memory.exemplar_store import get_shared_driver
from app.schemas.factory import FactoryProfile
from app.schemas.zone import HazardClass, PlantLayout, Zone
from app.storage.factory_store import save_factory

FACTORY_ID = "factory-live-ws-test"
ZONE_ID = "TZ1"

# 10 calm baseline readings (LIVE_BASELINE_TICKS) followed by a sharp
# spike, engineered to cross the HIGH/CRITICAL z-score threshold once
# the baseline is calibrated.
CALM_VALUES = [5.0, 5.02, 4.98, 5.01, 4.99, 5.03, 4.97, 5.0, 5.02, 4.98]
SPIKE_VALUE = 45.0


def _build_csv() -> bytes:
    rows = ["ts,zone,conc,gas"]
    for i, value in enumerate(CALM_VALUES + [SPIKE_VALUE]):
        rows.append(f"2026-07-20T10:{i:02d}:00Z,{ZONE_ID},{value},LEL")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _delete_factory(factory_id: str) -> None:
    driver = get_shared_driver()
    with driver.session() as session:
        session.run(
            "MATCH (f:Factory {factory_id: $id}) "
            "OPTIONAL MATCH (f)-[:HAS_ZONE]->(z:FactoryZone) "
            "DETACH DELETE f, z",
            id=factory_id,
        )
    shutil.rmtree(UPLOADS_ROOT / factory_id, ignore_errors=True)


@pytest.fixture
def factory_with_csv():
    profile = FactoryProfile(
        factory_id=FACTORY_ID,
        name="Live WS Test Steelworks",
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
        data_source="csv",
        created_at=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
    )
    save_factory(profile)
    save_uploaded_csv(
        FACTORY_ID,
        _build_csv(),
        column_map={
            "timestamp": "ts",
            "zone": "zone",
            "gas_concentration": "conc",
            "gas_type": "gas",
        },
        speed_multiplier=1_000_000.0,
    )
    yield FACTORY_ID
    _delete_factory(FACTORY_ID)


def test_live_factory_websocket_streams_ticks_and_reaches_a_verdict(factory_with_csv):
    client = TestClient(app)
    seen_types = []
    verdict_seen = False

    with client.websocket_connect("/ws/live-factory") as websocket:
        websocket.send_json({"type": "connect", "factory_id": factory_with_csv})
        for _ in range(200):
            msg = websocket.receive_json()
            seen_types.append(msg["type"])
            if msg["type"] == "verdict":
                verdict_seen = True
                break
            if msg["type"] in ("replay_complete", "error"):
                break

    assert "tick" in seen_types
    assert verdict_seen, f"never reached a verdict; message types seen: {seen_types}"


def test_live_factory_websocket_unknown_factory_returns_error():
    client = TestClient(app)
    with client.websocket_connect("/ws/live-factory") as websocket:
        websocket.send_json({"type": "connect", "factory_id": "does-not-exist"})
        msg = websocket.receive_json()
        assert msg["type"] == "error"
