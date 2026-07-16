"""Sensor Stream MCP Server.

Scoped exclusively to the Process Safety Engineer agent (CORRIX_PROJECT.md
§6.1): gas sensor readings (S2-S4) and the S1 compliance signal. Stub only —
real wiring against the Step 2 simulator lands in Step 3.
"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("corrix-sensor-stream")


@server.tool()
def get_zone_readings(zone_id: str) -> dict:
    """Return the latest gas/compliance readings for a zone. Stub."""
    return {"zone_id": zone_id, "readings": []}


@server.tool()
def get_anomaly_score(zone_id: str) -> dict:
    """Return the rolling z-score anomaly scorer's current output. Stub."""
    return {"zone_id": zone_id, "anomaly_score": 0.0}


if __name__ == "__main__":
    server.run_stdio_async()
