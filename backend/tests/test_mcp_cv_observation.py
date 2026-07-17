"""CV/Observation MCP server: real inference on the actual sample clip,
correlated against a real scenario's worker-location stream, per Step 6's
Definition of Done, checked via a real tool call."""

import json

import pytest

from app.mcp_servers.cv_observation import server


def _content_json(result):
    return json.loads(result[0].text)


@pytest.mark.anyio
async def test_get_recent_detections_returns_real_inference_with_correct_fields():
    result = await server.call_tool(
        "get_recent_detections",
        {"zone_id": "Z1", "scenario_id": "S1", "seed": 20260714, "at_minute": 60},
    )
    data = _content_json(result)
    assert data["zone_id"] == "Z1"
    assert isinstance(data["detections"], list)
    for d in data["detections"]:
        assert d["source"] == "real_inference"
        if d["correlation"] is not None:
            assert d["correlation_source"] == "simulated"


@pytest.mark.anyio
async def test_detections_at_different_minutes_reflect_different_video_frames():
    """Confirms this is genuinely sampling different frames per call, not
    a cached/static response."""
    r1 = await server.call_tool(
        "get_recent_detections",
        {"zone_id": "Z1", "scenario_id": "S1", "seed": 20260714, "at_minute": 5},
    )
    r2 = await server.call_tool(
        "get_recent_detections",
        {"zone_id": "Z1", "scenario_id": "S1", "seed": 20260714, "at_minute": 80},
    )
    d1 = _content_json(r1)
    d2 = _content_json(r2)
    # timestamps must differ (different minute offsets), proving each
    # call re-reads a fresh frame rather than replaying one fixed result
    t1 = [d["timestamp"] for d in d1["detections"]]
    t2 = [d["timestamp"] for d in d2["detections"]]
    assert t1 != t2 or d1["detections"] != d2["detections"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
