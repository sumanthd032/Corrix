"""Worker Location MCP server's real Step 4 tool."""

import json

import pytest

from app.mcp_servers.worker_location import server


def _content_json(result):
    return json.loads(result[0].text)


@pytest.mark.anyio
async def test_scripted_worker_present_in_scripted_zone_after_entry():
    result = await server.call_tool(
        "get_zone_occupancy",
        {"scenario_id": "S1", "seed": 20260714, "zone_id": "Z1", "at_minute": 60},
    )
    data = _content_json(result)
    assert "W-0142" in data["badge_ids"]


@pytest.mark.anyio
async def test_scripted_worker_absent_before_entry_minute():
    result = await server.call_tool(
        "get_zone_occupancy",
        {"scenario_id": "S1", "seed": 20260714, "zone_id": "Z1", "at_minute": 10},
    )
    data = _content_json(result)
    assert "W-0142" not in data["badge_ids"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
