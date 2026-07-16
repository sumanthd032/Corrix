"""CV/Observation MCP Server.

Scoped, alongside Worker Location, to the Site Safety Observer agent
(CORRIX_PROJECT.md §6.1). Stub only — real YOLO26 inference wiring lands
in Step 6.
"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("corrix-cv-observation")


@server.tool()
def get_recent_detections(zone_id: str) -> dict:
    """Return recent CV detection events for a zone, with source/
    correlation_source fields intact. Stub."""
    return {"zone_id": zone_id, "detections": []}


if __name__ == "__main__":
    server.run_stdio_async()
