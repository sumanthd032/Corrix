"""Corrix Risk MCP Server, the outward-facing half of the dual-role
MCP story (CORRIX_PROJECT.md §7.2). Every other server in this package
is a source the Safety Council consumes as a *client*; this one exposes
the Council's own compound-risk verdicts back out as an MCP *server*,
so any external MCP client (a judge's own Claude/Gemini session, a
plant's existing ServiceNow/Slack integration) can ask "what's the
current compound risk in Zone 4 and why" and get a live, grounded
answer, without a bespoke chat integration built for that purpose.

Architecturally distinct from the other five servers in this package:
those are consumed in-process (the Council calls their Python objects
directly), so a live wire round trip was never load-bearing for them.
This one is meant to run as its own standalone process, reachable by a
real external client over stdio. It cannot share the FastAPI backend
process's memory, so it reads live state from the same Neo4j substrate
`_convene_council` (app/api/websocket.py) writes to after every real
verdict, via `app.state.live_risk_state`.

Run standalone: python -m app.mcp_servers.corrix_risk
"""

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase

from app.config import get_settings
from app.simulation.plant_layout import load_plant_layout
from app.state.live_risk_state import get_zone_risk_state

server = FastMCP("corrix-risk")

_settings = get_settings()
_driver = GraphDatabase.driver(
    _settings.neo4j_uri, auth=(_settings.neo4j_username, _settings.neo4j_password)
)


@server.tool()
def get_zone_compound_risk(zone_id: str) -> dict:
    """Return the Safety Council's latest live compound-risk verdict for
    a plant zone: risk level, confidence, the explanation reached, and
    the recommended action, exactly the judgment the Council itself
    produced, not a re-derived summary. If the Council has never
    convened for this zone in the current run, says so honestly rather
    than fabricating a SAFE default."""
    zones_by_id = {z.zone_id for z in load_plant_layout().zones}
    if zone_id not in zones_by_id:
        return {"zone_id": zone_id, "error": f"unknown zone_id, expected one of {sorted(zones_by_id)}"}

    state = get_zone_risk_state(_driver, zone_id)
    if state is None:
        return {
            "zone_id": zone_id,
            "has_verdict": False,
            "note": "The Safety Council has not convened for this zone in the current run.",
        }
    return {"zone_id": zone_id, "has_verdict": True, **{k: v for k, v in state.items() if k != "zone_id"}}


@server.tool()
def list_zones() -> dict:
    """List every plant zone Corrix models, for a client that doesn't
    already know the zone IDs to ask about."""
    return {
        "zones": [
            {"zone_id": z.zone_id, "name": z.name, "hazard_class": z.hazard_class}
            for z in load_plant_layout().zones
        ]
    }


if __name__ == "__main__":
    server.run()
