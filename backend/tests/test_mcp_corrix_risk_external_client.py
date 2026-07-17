"""The real external-client proof Step 9's Definition of Done asks for:
Corrix's outward-facing MCP server (app/mcp_servers/corrix_risk.py) is
the one server in this package meant to run as its own standalone
process, reachable by anything that speaks MCP, not consumed
in-process like the other five. So unlike every other MCP test in this
project, this one spawns the server as a genuine subprocess over stdio
and drives it with the real `mcp` client library, the same way an
external judge's Claude or Gemini session would.

This is also the test that caught a real bug: an em dash in a tool's
docstring (which becomes its MCP `description` field) got written as a
single cp1252 byte by the child process's default piped-stdout
encoding on Windows, corrupting the JSON-RPC stream for this strict
UTF-8 client. Plain ASCII punctuation in tool docstrings is a real
correctness requirement here, not just a style preference.
"""

import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.anyio
async def test_real_external_client_can_list_tools_and_call_them():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "app.mcp_servers.corrix_risk"]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = (await session.list_tools()).tools
            tool_names = {t.name for t in tools}
            assert tool_names == {"get_zone_compound_risk", "list_zones"}

            zones_result = await session.call_tool("list_zones", {})
            assert zones_result.isError is not True

            risk_result = await session.call_tool(
                "get_zone_compound_risk", {"zone_id": "Z1"}
            )
            assert risk_result.isError is not True


@pytest.fixture
def anyio_backend():
    return "asyncio"
