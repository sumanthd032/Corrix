"""The live compound-risk state Corrix's outward-facing MCP server
exposes, per CORRIX_PROJECT.md §7.2's "dual-role MCP citizen" story:
the Council's own judgment, made queryable by anything that speaks MCP,
not just consumed internally.

Stored in the same Neo4j substrate as everything else (§7.1, one
free, persistent, real database), specifically because the outward-
facing MCP server (`app/mcp_servers/corrix_risk.py`) runs as its own
process over stdio when a real external client connects to it. It
cannot share in-memory state with the FastAPI backend process that
actually convenes the Council, so this has to be a real, persistent
write both sides can reach, not a Python dict.
"""

from datetime import datetime, timezone

from neo4j import Driver

LIVE_RISK_STATE_CONSTRAINT = (
    "CREATE CONSTRAINT live_risk_state_zone_id_unique IF NOT EXISTS "
    "FOR (r:LiveRiskState) REQUIRE r.zone_id IS UNIQUE"
)


def ensure_live_risk_state_schema(driver: Driver) -> None:
    with driver.session() as session:
        session.run(LIVE_RISK_STATE_CONSTRAINT)


def update_zone_risk_state(
    driver: Driver,
    zone_id: str,
    risk_level: str,
    confidence: float,
    compound_flag: bool,
    trigger_reason: str,
    explanation: str,
    recommended_action: str,
    scenario_id: str | None,
) -> None:
    with driver.session() as session:
        session.run(
            """
            MERGE (r:LiveRiskState {zone_id: $zone_id})
            SET r.risk_level = $risk_level,
                r.confidence = $confidence,
                r.compound_flag = $compound_flag,
                r.trigger_reason = $trigger_reason,
                r.explanation = $explanation,
                r.recommended_action = $recommended_action,
                r.scenario_id = $scenario_id,
                r.updated_at = $updated_at
            """,
            zone_id=zone_id,
            risk_level=risk_level,
            confidence=confidence,
            compound_flag=compound_flag,
            trigger_reason=trigger_reason,
            explanation=explanation,
            recommended_action=recommended_action,
            scenario_id=scenario_id,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )


def get_zone_risk_state(driver: Driver, zone_id: str) -> dict | None:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (r:LiveRiskState {zone_id: $zone_id})
            RETURN r.zone_id AS zone_id,
                   r.risk_level AS risk_level,
                   r.confidence AS confidence,
                   r.compound_flag AS compound_flag,
                   r.trigger_reason AS trigger_reason,
                   r.explanation AS explanation,
                   r.recommended_action AS recommended_action,
                   r.scenario_id AS scenario_id,
                   r.updated_at AS updated_at
            """,
            zone_id=zone_id,
        )
        record = result.single()
        return dict(record) if record else None


def wipe_all_live_risk_state(driver: Driver) -> None:
    """Testing convenience, never called by application code paths."""
    with driver.session() as session:
        session.run("MATCH (r:LiveRiskState) DETACH DELETE r")
