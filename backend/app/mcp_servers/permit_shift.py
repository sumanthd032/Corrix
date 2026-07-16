"""Permit/Shift MCP Server.

Scoped to the Permit Control Officer (permit + zone data) and Shift
Operations (roster/changeover data only) agents (CORRIX_PROJECT.md §6.1).
Stub only — real wiring against the Step 2 generators lands in Step 3.
"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("corrix-permit-shift")


@server.tool()
def get_active_permits(zone_id: str) -> dict:
    """Return active permits in a zone. Stub."""
    return {"zone_id": zone_id, "permits": []}


@server.tool()
def check_permit_conflict(zone_id: str) -> dict:
    """Run the deterministic permit-conflict rule table for a zone. Stub."""
    return {"zone_id": zone_id, "conflict": False}


@server.tool()
def get_shift_status(zone_id: str) -> dict:
    """Return current shift and changeover-proximity status for a zone. Stub."""
    return {"zone_id": zone_id, "changeover_in_minutes": None}


if __name__ == "__main__":
    server.run_stdio_async()
