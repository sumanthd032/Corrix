"""All five MCP server stubs boot and respond to a basic tool-list call —
Step 1's Definition of Done for the MCP tool layer."""

import pytest

from app.mcp_servers import (
    cv_observation,
    permit_shift,
    regulatory_intelligence,
    sensor_stream,
    worker_location,
)

SERVERS = [
    (sensor_stream.server, {"get_zone_readings", "get_anomaly_score"}),
    (
        permit_shift.server,
        {"get_active_permits", "check_permit_conflict", "get_shift_status"},
    ),
    (
        regulatory_intelligence.server,
        {"query_regulatory_corpus", "lookup_incident_pattern", "check_compliance"},
    ),
    (cv_observation.server, {"get_recent_detections"}),
    (worker_location.server, {"get_zone_occupancy"}),
]


@pytest.mark.anyio
@pytest.mark.parametrize("server,expected_tools", SERVERS)
async def test_server_boots_and_lists_tools(server, expected_tools):
    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}
    assert expected_tools == tool_names


@pytest.fixture
def anyio_backend():
    return "asyncio"
