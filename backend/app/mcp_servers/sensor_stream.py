"""Sensor Stream MCP Server.

Scoped exclusively to the Process Safety Engineer agent (CORRIX_PROJECT.md
§6.1): gas sensor readings (S2-S4) and the S1 compliance signal.

Real tools as of Step 3: both run an actual authored scenario through the
Step 2 simulator and the Step 3 anomaly scorer. There is no live-running
plant state yet (that lands with the full app in Step 9), so a scenario
config is the unit of "current state" a tool call operates on.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.detection.anomaly_scorer import max_risk_level, score_series
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    find_scenario_config,
    run_scenario_from_file,
)

server = FastMCP("corrix-sensor-stream")

SCENARIOS_ROOT = Path(__file__).resolve().parents[3] / "data" / "scenarios"


def _signal_values(out) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


@server.tool()
def get_zone_readings(scenario_id: str, seed: int, zone_id: str) -> dict:
    """Return the full gas/compliance reading series for a zone, from a
    seeded scenario run."""
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    if out.zone_id != zone_id:
        return {"zone_id": zone_id, "readings": [], "note": "scenario's zone does not match zone_id"}
    if out.gas_readings:
        readings = [
            {"timestamp": r.timestamp.isoformat(), "concentration": r.concentration, "unit": r.unit}
            for r in out.gas_readings
        ]
    else:
        readings = [
            {"timestamp": r.timestamp.isoformat(), "compliance_score": r.compliance_score}
            for r in out.compliance_readings
        ]
    return {"zone_id": zone_id, "readings": readings}


@server.tool()
def get_anomaly_score(scenario_id: str, seed: int, zone_id: str) -> dict:
    """Return the rolling z-score anomaly scorer's summary output for a
    zone, from a seeded scenario run: latest score, peak score, and the
    highest risk_level reached so far."""
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    values = _signal_values(out)
    if not values or out.zone_id != zone_id:
        return {"zone_id": zone_id, "anomaly_score": 0.0, "risk_level": "SAFE"}
    points = score_series(values)
    latest = points[-1]
    return {
        "zone_id": zone_id,
        "latest_z_score": round(latest.z_score, 3),
        "latest_risk_level": latest.risk_level,
        "max_risk_level": max_risk_level(points),
        "start_time": DEFAULT_START_TIME.isoformat(),
    }


if __name__ == "__main__":
    server.run()
