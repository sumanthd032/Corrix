"""Permit/Shift MCP Server.

Scoped to the Permit Control Officer (permit + zone data) and Shift
Operations (roster/changeover data only) agents (CORRIX_PROJECT.md §6.1).

Real tools as of Step 3, operating against a seeded scenario run (there is
no live-running plant state yet, that lands with the full app in Step 9).
`check_permit_conflict` takes `risk_level` as an explicit caller-supplied
argument rather than reaching into Sensor Stream's data itself: this MCP
server has no access to sensor data, consistent with the agent-silo design
this tool layer exists to support from Step 4 onward.
"""

from datetime import datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.detection.permit_conflict import active_permits_at, check_permit_conflict as _check_conflict
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    find_scenario_config,
    run_scenario_from_file,
)

server = FastMCP("corrix-permit-shift")

SCENARIOS_ROOT = Path(__file__).resolve().parents[3] / "data" / "scenarios"


def _zone(zone_id: str):
    layout = load_plant_layout()
    return next(z for z in layout.zones if z.zone_id == zone_id)


@server.tool()
def get_active_permits(scenario_id: str, seed: int, zone_id: str, at_minute: float) -> dict:
    """Return permits active in a zone at a given minute into a seeded
    scenario run."""
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    at_time = DEFAULT_START_TIME + timedelta(minutes=at_minute)
    active = active_permits_at(out.permits, zone_id, at_time)
    return {
        "zone_id": zone_id,
        "at_minute": at_minute,
        "permits": [
            {
                "permit_id": p.permit_id,
                "type": p.type.value,
                "status": p.status.value,
                "start_time": p.start_time.isoformat(),
                "end_time": p.end_time.isoformat(),
            }
            for p in active
        ],
    }


@server.tool()
def check_permit_conflict(
    scenario_id: str, seed: int, zone_id: str, at_minute: float, risk_level: str
) -> dict:
    """Run the deterministic permit-conflict rule table for a zone at a
    given minute, against a caller-supplied anomaly risk_level."""
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    at_time = DEFAULT_START_TIME + timedelta(minutes=at_minute)
    zone = _zone(zone_id)
    active = active_permits_at(out.permits, zone_id, at_time)
    result = _check_conflict(zone, active, risk_level)
    return {
        "zone_id": zone_id,
        "conflict": result.conflict,
        "reason": result.reason,
        "conflicting_permits": result.conflicting_permits,
    }


@server.tool()
def get_shift_status(scenario_id: str, seed: int, zone_id: str, at_minute: float) -> dict:
    """Return current shift and changeover-proximity status for a zone at
    a given minute into a seeded scenario run."""
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    at_time = DEFAULT_START_TIME + timedelta(minutes=at_minute)
    covering = [
        s
        for s in out.shifts
        if zone_id in s.zones and s.start_time <= at_time <= s.end_time
    ]
    if not covering:
        return {"zone_id": zone_id, "at_minute": at_minute, "changeover_in_minutes": None}
    # nearest upcoming changeover among shifts covering this zone
    nearest = min(
        (s.end_time - at_time).total_seconds() / 60
        for s in covering
        if s.end_time >= at_time
    )
    return {
        "zone_id": zone_id,
        "at_minute": at_minute,
        "changeover_in_minutes": round(nearest, 2),
        "changeover_window_minutes": covering[0].changeover_window_minutes,
    }


if __name__ == "__main__":
    server.run()
