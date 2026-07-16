"""Worker Location MCP Server.

Scoped, alongside CV/Observation, to the Site Safety Observer agent
(CORRIX_PROJECT.md §6.1). Also feeds the heatmap's worker markers and the
Emergency Response Orchestrator's zone-occupancy query.

Real tool as of Step 4: computes actual occupancy from the Step 2
badge-ping stream of a seeded scenario run. A badge counts as present in
a zone if its most recent ping at or before `at_minute` was in that zone
— consistent with how the generator emits events (zone_entry once, then
periodic heartbeats in the same zone until the run ends; no zone_exit
events are generated since none of the authored scenarios script a
worker leaving mid-run).
"""

from datetime import timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    find_scenario_config,
    run_scenario_from_file,
)

server = FastMCP("corrix-worker-location")

SCENARIOS_ROOT = Path(__file__).resolve().parents[3] / "data" / "scenarios"


@server.tool()
def get_zone_occupancy(scenario_id: str, seed: int, zone_id: str, at_minute: float) -> dict:
    """Return badge IDs present in a zone at a given minute into a seeded
    scenario run, derived from each badge's most recent ping."""
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    at_time = DEFAULT_START_TIME + timedelta(minutes=at_minute)

    latest_by_badge: dict[str, tuple] = {}
    for ping in out.worker_pings:
        if ping.timestamp > at_time:
            continue
        current = latest_by_badge.get(ping.badge_id)
        if current is None or ping.timestamp > current[0]:
            latest_by_badge[ping.badge_id] = (ping.timestamp, ping.zone_id)

    badge_ids = sorted(
        badge_id
        for badge_id, (_, last_zone) in latest_by_badge.items()
        if last_zone == zone_id
    )
    return {"zone_id": zone_id, "at_minute": at_minute, "badge_ids": badge_ids}


if __name__ == "__main__":
    server.run_stdio_async()
