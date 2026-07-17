"""Sensor Stream and Permit/Shift MCP servers' real Step 3 tools, called
the way an MCP client actually would: through call_tool, not by
importing the underlying Python functions directly."""

import json

import pytest

from app.mcp_servers.permit_shift import server as permit_server
from app.mcp_servers.sensor_stream import server as sensor_server


def _content_json(result):
    return json.loads(result[0].text)


@pytest.mark.anyio
async def test_get_anomaly_score_returns_real_critical_for_s1():
    result = await sensor_server.call_tool(
        "get_anomaly_score", {"scenario_id": "S1", "seed": 20260714, "zone_id": "Z1"}
    )
    data = _content_json(result)
    assert data["zone_id"] == "Z1"
    assert data["max_risk_level"] == "CRITICAL"


@pytest.mark.anyio
async def test_get_zone_readings_returns_real_compliance_series():
    result = await sensor_server.call_tool(
        "get_zone_readings", {"scenario_id": "S1", "seed": 20260714, "zone_id": "Z1"}
    )
    data = _content_json(result)
    assert len(data["readings"]) > 0
    assert "compliance_score" in data["readings"][0]


@pytest.mark.anyio
async def test_check_permit_conflict_flags_real_scripted_conflict():
    result = await permit_server.call_tool(
        "check_permit_conflict",
        {
            "scenario_id": "S1",
            "seed": 20260714,
            "zone_id": "Z1",
            "at_minute": 70,
            "risk_level": "HIGH",
        },
    )
    data = _content_json(result)
    assert data["conflict"] is True
    assert "P-SCRIPT-Z1-20" in data["conflicting_permits"]


@pytest.mark.anyio
async def test_get_shift_status_reports_real_changeover_proximity():
    result = await permit_server.call_tool(
        "get_shift_status",
        {"scenario_id": "S1", "seed": 20260714, "zone_id": "Z1", "at_minute": 60},
    )
    data = _content_json(result)
    assert data["changeover_in_minutes"] == 8.0


@pytest.fixture
def anyio_backend():
    return "asyncio"
