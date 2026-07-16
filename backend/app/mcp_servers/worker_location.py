"""Worker Location MCP Server.

Scoped, alongside CV/Observation, to the Site Safety Observer agent
(CORRIX_PROJECT.md §6.1). Also feeds the heatmap's worker markers and the
Emergency Response Orchestrator's zone-occupancy query. Stub only — real
wiring against the Step 2 badge-ping generator lands in Step 3.
"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("corrix-worker-location")


@server.tool()
def get_zone_occupancy(zone_id: str) -> dict:
    """Return badge IDs currently present in a zone. Stub."""
    return {"zone_id": zone_id, "badge_ids": []}


if __name__ == "__main__":
    server.run_stdio_async()
