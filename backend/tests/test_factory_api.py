"""POST/GET /api/factory, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 3.
Hits the real dev Neo4j instance, matching this suite's existing
discipline (see conftest.py) rather than mocking the driver; each test
cleans up the factory node(s) it creates."""

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app.ingestion.csv_upload_store import UPLOADS_ROOT
from app.main import app
from app.memory.exemplar_store import get_shared_driver

client = TestClient(app)


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


def _valid_payload(factory_id: str) -> dict:
    return {
        "factory_id": factory_id,
        "name": "API Test Steelworks",
        "industry": "steel",
        "location": "Test City",
        "layout": {
            "zones": [
                {
                    "zone_id": "AZ1",
                    "name": "Test Bay",
                    "hazard_class": "high",
                    "primary_role": "casting",
                    "is_confined_space": False,
                    "is_assembly_point": False,
                },
                {
                    "zone_id": "AZ2",
                    "name": "Test Control Room",
                    "hazard_class": "low",
                    "primary_role": "control",
                    "is_confined_space": False,
                    "is_assembly_point": True,
                },
            ],
            "adjacency": [{"zone_a": "AZ1", "zone_b": "AZ2"}],
        },
        "permit_types_in_use": ["hot_work"],
        "shift_pattern": [
            {
                "shift_id": "shift-a",
                "start_time": "2026-07-20T06:00:00Z",
                "end_time": "2026-07-20T14:00:00Z",
                "changeover_window_minutes": 15,
                "zones": ["AZ1", "AZ2"],
            }
        ],
        "data_source": "csv",
        "created_at": "2026-07-20T00:00:00Z",
    }


@pytest.fixture
def factory_id():
    fid = "factory-api-test"
    yield fid
    _delete_factory(fid)


def test_create_factory_with_valid_payload_returns_200(factory_id):
    response = client.post("/api/factory", json=_valid_payload(factory_id))
    assert response.status_code == 200
    assert response.json() == {"factoryId": factory_id}


def test_create_factory_with_dangling_adjacency_edge_returns_422(factory_id):
    payload = _valid_payload(factory_id)
    payload["layout"]["adjacency"] = [{"zone_a": "AZ1", "zone_b": "UNKNOWN"}]
    response = client.post("/api/factory", json=payload)
    assert response.status_code == 422
    assert "UNKNOWN" in response.json()["detail"]


def test_create_factory_with_duplicate_zone_ids_returns_422(factory_id):
    payload = _valid_payload(factory_id)
    payload["layout"]["zones"][1]["zone_id"] = "AZ1"
    response = client.post("/api/factory", json=payload)
    assert response.status_code == 422
    assert "unique" in response.json()["detail"].lower()


def test_get_unknown_factory_returns_404():
    response = client.get("/api/factory/does-not-exist")
    assert response.status_code == 404


def test_get_factory_after_create_matches_what_was_posted(factory_id):
    payload = _valid_payload(factory_id)
    create_response = client.post("/api/factory", json=payload)
    assert create_response.status_code == 200

    get_response = client.get(f"/api/factory/{factory_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["factory_id"] == factory_id
    assert body["name"] == payload["name"]
    assert body["industry"] == payload["industry"]
    assert body["data_source"] == payload["data_source"]
    assert {z["zone_id"] for z in body["layout"]["zones"]} == {"AZ1", "AZ2"}
    assert [
        {"zone_a": e["zone_a"], "zone_b": e["zone_b"]} for e in body["layout"]["adjacency"]
    ] == [{"zone_a": "AZ1", "zone_b": "AZ2"}]


def test_patch_data_source_changes_it_and_get_reflects_it(factory_id):
    payload = _valid_payload(factory_id)
    create_response = client.post("/api/factory", json=payload)
    assert create_response.status_code == 200

    patch_response = client.patch(
        f"/api/factory/{factory_id}/data-source", json={"data_source": "mqtt"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data_source"] == "mqtt"

    get_response = client.get(f"/api/factory/{factory_id}")
    assert get_response.json()["data_source"] == "mqtt"


def test_patch_data_source_on_unknown_factory_returns_404():
    response = client.patch(
        "/api/factory/does-not-exist/data-source", json={"data_source": "mqtt"}
    )
    assert response.status_code == 404


_SAMPLE_CSV = b"""ts,zone,conc,gas
2026-07-20T10:00:00Z,AZ1,5.0,LEL
2026-07-20T10:00:05Z,AZ1,5.1,LEL
2026-07-20T10:00:10Z,AZ1,4.9,LEL
"""

_VALID_COLUMN_MAP = {
    "timestamp": "ts",
    "zone": "zone",
    "gas_concentration": "conc",
    "gas_type": "gas",
}


def test_upload_csv_with_valid_column_map_returns_200(factory_id):
    create_response = client.post("/api/factory", json=_valid_payload(factory_id))
    assert create_response.status_code == 200

    response = client.post(
        f"/api/factory/{factory_id}/csv-upload",
        files={"file": ("readings.csv", _SAMPLE_CSV, "text/csv")},
        data={"column_map": json.dumps(_VALID_COLUMN_MAP), "speed_multiplier": "30"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["factoryId"] == factory_id
    assert body["rowsIngested"] == 3


def test_upload_csv_with_bad_column_map_returns_422(factory_id):
    create_response = client.post("/api/factory", json=_valid_payload(factory_id))
    assert create_response.status_code == 200

    bad_column_map = dict(_VALID_COLUMN_MAP, gas_concentration="does_not_exist")
    response = client.post(
        f"/api/factory/{factory_id}/csv-upload",
        files={"file": ("readings.csv", _SAMPLE_CSV, "text/csv")},
        data={"column_map": json.dumps(bad_column_map)},
    )
    assert response.status_code == 422
    assert "does_not_exist" in response.json()["detail"]


def test_upload_csv_with_invalid_json_column_map_returns_422(factory_id):
    create_response = client.post("/api/factory", json=_valid_payload(factory_id))
    assert create_response.status_code == 200

    response = client.post(
        f"/api/factory/{factory_id}/csv-upload",
        files={"file": ("readings.csv", _SAMPLE_CSV, "text/csv")},
        data={"column_map": "not valid json"},
    )
    assert response.status_code == 422


def test_upload_csv_on_unknown_factory_returns_404():
    response = client.post(
        "/api/factory/does-not-exist/csv-upload",
        files={"file": ("readings.csv", _SAMPLE_CSV, "text/csv")},
        data={"column_map": json.dumps(_VALID_COLUMN_MAP)},
    )
    assert response.status_code == 404
