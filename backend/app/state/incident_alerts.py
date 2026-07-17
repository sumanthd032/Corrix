"""Fired Emergency Response Orchestrator incidents, persisted so the
Incident Intelligence Report generator (CORRIX_BUILD_PLAN.md Step 9, not
yet built) has a real record to attach to, not just the live in-memory
verdict that produced it. Stored in the same shared Neo4j substrate as
everything else, per CORRIX_PROJECT.md §7.1.
"""

import json
from datetime import datetime, timezone

from neo4j import Driver

INCIDENT_ALERT_CONSTRAINT = (
    "CREATE CONSTRAINT incident_alert_id_unique IF NOT EXISTS "
    "FOR (a:IncidentAlert) REQUIRE a.alert_id IS UNIQUE"
)


def ensure_incident_alert_schema(driver: Driver) -> None:
    with driver.session() as session:
        session.run(INCIDENT_ALERT_CONSTRAINT)


def store_incident_alert(
    driver: Driver,
    alert_id: str,
    zone_id: str,
    scenario_id: str | None,
    risk_level: str,
    trigger_reason: str,
    explanation: str,
    recommended_action: str,
    evacuation_route: list[str] | None,
    worker_badge_ids: list[str],
    fired_at: str,
    evidence_hash: str,
    evidence_snapshot: dict,
    delivery_backend: str,
    delivery_error: str | None,
) -> None:
    with driver.session() as session:
        session.run(
            """
            MERGE (a:IncidentAlert {alert_id: $alert_id})
            SET a.zone_id = $zone_id,
                a.scenario_id = $scenario_id,
                a.risk_level = $risk_level,
                a.trigger_reason = $trigger_reason,
                a.explanation = $explanation,
                a.recommended_action = $recommended_action,
                a.evacuation_route = $evacuation_route,
                a.worker_badge_ids = $worker_badge_ids,
                a.fired_at = $fired_at,
                a.evidence_hash = $evidence_hash,
                a.evidence_snapshot_json = $evidence_snapshot_json,
                a.delivery_backend = $delivery_backend,
                a.delivery_error = $delivery_error,
                a.stored_at = $stored_at
            """,
            alert_id=alert_id,
            zone_id=zone_id,
            scenario_id=scenario_id,
            risk_level=risk_level,
            trigger_reason=trigger_reason,
            explanation=explanation,
            recommended_action=recommended_action,
            evacuation_route=evacuation_route or [],
            worker_badge_ids=worker_badge_ids,
            fired_at=fired_at,
            evidence_hash=evidence_hash,
            evidence_snapshot_json=json.dumps(evidence_snapshot, sort_keys=True, default=str),
            delivery_backend=delivery_backend,
            delivery_error=delivery_error,
            stored_at=datetime.now(timezone.utc).isoformat(),
        )


def get_recent_incident_alerts(driver: Driver, limit: int = 20) -> list[dict]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:IncidentAlert)
            RETURN a.alert_id AS alert_id,
                   a.zone_id AS zone_id,
                   a.scenario_id AS scenario_id,
                   a.risk_level AS risk_level,
                   a.trigger_reason AS trigger_reason,
                   a.explanation AS explanation,
                   a.recommended_action AS recommended_action,
                   a.evacuation_route AS evacuation_route,
                   a.worker_badge_ids AS worker_badge_ids,
                   a.fired_at AS fired_at,
                   a.evidence_hash AS evidence_hash,
                   a.evidence_snapshot_json AS evidence_snapshot_json,
                   a.delivery_backend AS delivery_backend,
                   a.delivery_error AS delivery_error
            ORDER BY a.fired_at DESC
            LIMIT $limit
            """,
            limit=limit,
        )
        return [dict(r) for r in result]


def wipe_all_incident_alerts(driver: Driver) -> None:
    """Testing convenience, never called by application code paths."""
    with driver.session() as session:
        session.run("MATCH (a:IncidentAlert) DETACH DELETE a")
