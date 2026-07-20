"""Rate limiting on POST /api/virtual-sensor/*, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 26: a scripted flood is throttled
with a clear 429 rather than crashing the backend or overwhelming the
live-factory websocket's Council-convening loop."""

from fastapi.testclient import TestClient

from app.api import virtual_sensor
from app.main import app

client = TestClient(app)


def test_rapid_requests_are_throttled_with_429(monkeypatch):
    # Reset any bucket state left over from other tests/imports.
    monkeypatch.setattr(virtual_sensor, "_buckets", {})

    factory_id = "rate-limit-test-factory"
    zone_id = "Z1"
    statuses = []
    for _ in range(30):
        response = client.post(
            f"/api/virtual-sensor/{factory_id}/{zone_id}/badge",
            json={"badge_id": "W-0001", "entering": True},
        )
        statuses.append(response.status_code)

    assert 200 in statuses, "expected at least the burst allowance to succeed"
    assert 429 in statuses, f"expected a scripted flood to be throttled, got: {statuses}"
    # First requests (within burst capacity) should succeed before any 429s appear.
    first_429_index = statuses.index(429)
    assert all(s == 200 for s in statuses[:first_429_index])


def test_different_factories_have_independent_rate_limits(monkeypatch):
    monkeypatch.setattr(virtual_sensor, "_buckets", {})

    # Exhaust factory A's burst allowance.
    for _ in range(25):
        client.post(
            "/api/virtual-sensor/rate-limit-factory-a/Z1/badge",
            json={"badge_id": "W-0001", "entering": True},
        )

    # Factory B should be unaffected.
    response = client.post(
        "/api/virtual-sensor/rate-limit-factory-b/Z1/badge",
        json={"badge_id": "W-0001", "entering": True},
    )
    assert response.status_code == 200
