"""The Emergency Response Orchestrator, per CORRIX_BUILD_PLAN.md Step 9:
real SMTP delivery and a real, persisted incident record, not mocks.
The user chose SMTP (Gmail) as the channel and asked for the integration
to be verified for real, so `test_fire_emergency_response_sends_a_real_email`
actually sends one live email and confirms it landed in the same store
the Incident Report generator will later read from.
"""

from datetime import datetime, timezone

import pytest
from neo4j import GraphDatabase

from app.config import get_settings
from app.emergency.orchestrator import build_evidence_snapshot, fire_emergency_response
from app.schemas import CouncilEvidence, CouncilVerdict, TimeToCriticalForecast
from app.state.incident_alerts import ensure_incident_alert_schema, get_recent_incident_alerts


def _sample_verdict(risk_level: str = "CRITICAL") -> CouncilVerdict:
    return CouncilVerdict(
        zone_id="Z1",
        scenario_id="TEST-ERO",
        trigger_reason="rule_threshold",
        timestamp=datetime.now(timezone.utc),
        council=CouncilEvidence(
            process_safety_engineer="Zone 1 gas concentration is at 4x the CRITICAL threshold.",
            permit_control_officer="An active hot-work permit is in effect for Zone 1.",
            shift_operations="Shift changeover begins in 8 minutes.",
            site_safety_observer="Two workers confirmed present in Zone 1.",
        ),
        risk_level=risk_level,
        confidence=0.93,
        compound_flag=True,
        time_to_critical=TimeToCriticalForecast(
            median_minutes=4.0, iqr_low_minutes=2.0, iqr_high_minutes=7.0,
            escalation_probability=0.88, horizon_minutes=60.0,
        ),
        explanation="Test fixture verdict for the ERO integration test suite.",
        recommended_action="Evacuate Zone 1 immediately via the nearest marked route.",
        evacuation_route=["Z1", "Z4"],
    )


def test_evidence_snapshot_hash_is_deterministic_and_content_sensitive():
    verdict = _sample_verdict()
    _, hash_a = build_evidence_snapshot(verdict, ["W-0001"])
    _, hash_b = build_evidence_snapshot(verdict, ["W-0001"])
    assert hash_a == hash_b

    verdict.explanation = "A different explanation changes the hash."
    _, hash_c = build_evidence_snapshot(verdict, ["W-0001"])
    assert hash_c != hash_a


@pytest.fixture(scope="module")
def driver():
    settings = get_settings()
    d = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    ensure_incident_alert_schema(d)
    yield d
    d.close()


def test_fire_emergency_response_sends_a_real_email_and_persists_the_alert(driver):
    verdict = _sample_verdict()
    alert = fire_emergency_response(verdict, ["W-0091", "W-0142"], driver)

    assert alert.delivery_error is None, f"real SMTP send failed: {alert.delivery_error}"
    assert alert.delivery_backend == "smtp"
    assert alert.zone_id == "Z1"
    assert alert.worker_badge_ids == ["W-0091", "W-0142"]

    stored = get_recent_incident_alerts(driver, limit=5)
    assert any(row["alert_id"] == alert.alert_id for row in stored)
    match = next(row for row in stored if row["alert_id"] == alert.alert_id)
    assert match["evidence_hash"] == alert.evidence_hash
    assert match["delivery_error"] is None
