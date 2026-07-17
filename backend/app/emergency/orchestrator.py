"""The Emergency Response Orchestrator, per CORRIX_PROJECT.md §8 Pillar 4
and CORRIX_BUILD_PLAN.md Step 9: a real webhook notification firing on a
CRITICAL verdict, a timestamped/hashed evidence snapshot, the Step 8
evacuation route attached, and a persisted record the (not yet built)
Incident Intelligence Report generator can attach to.

SMTP is the channel the user chose for this build (CLAUDE.md Section 3).
The evidence snapshot's SHA-256 hash gives a tamper-evident fingerprint
of exactly what the Council saw when it fired: anyone holding both the
alert and a copy of the canonical payload can independently confirm
neither was altered after the fact, without trusting either document on
its own.

Firing never raises into the live convening that produced it: a failed
send is itself recorded (delivery_error) and returned, not swallowed
silently and not allowed to crash the WebSocket handler mid-verdict.
"""

import hashlib
import json
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage

from neo4j import Driver

from app.config import get_settings
from app.schemas import CouncilVerdict
from app.state.incident_alerts import ensure_incident_alert_schema, store_incident_alert


@dataclass
class IncidentAlert:
    alert_id: str
    zone_id: str
    scenario_id: str | None
    risk_level: str
    trigger_reason: str
    explanation: str
    recommended_action: str
    evacuation_route: list[str] | None
    worker_badge_ids: list[str]
    fired_at: str
    evidence_hash: str
    delivery_backend: str
    delivery_error: str | None = None


def _canonical_evidence_payload(verdict: CouncilVerdict, worker_badge_ids: list[str]) -> dict:
    return {
        "zone_id": verdict.zone_id,
        "scenario_id": verdict.scenario_id,
        "trigger_reason": verdict.trigger_reason,
        "timestamp": verdict.timestamp.isoformat(),
        "risk_level": verdict.risk_level,
        "confidence": verdict.confidence,
        "compound_flag": verdict.compound_flag,
        "council": {
            "process_safety_engineer": verdict.council.process_safety_engineer,
            "permit_control_officer": verdict.council.permit_control_officer,
            "shift_operations": verdict.council.shift_operations,
            "site_safety_observer": verdict.council.site_safety_observer,
        },
        "explanation": verdict.explanation,
        "recommended_action": verdict.recommended_action,
        "evacuation_route": verdict.evacuation_route,
        "worker_badge_ids": sorted(worker_badge_ids),
    }


def build_evidence_snapshot(
    verdict: CouncilVerdict, worker_badge_ids: list[str]
) -> tuple[dict, str]:
    """Returns the canonical payload and its SHA-256 hex digest."""
    payload = _canonical_evidence_payload(verdict, worker_badge_ids)
    canonical = json.dumps(payload, sort_keys=True, default=str)
    evidence_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload, evidence_hash


def _format_email_body(
    verdict: CouncilVerdict, worker_badge_ids: list[str], evidence_hash: str, fired_at: str
) -> str:
    route_text = (
        " -> ".join(verdict.evacuation_route)
        if verdict.evacuation_route
        else "No evacuation route computed."
    )
    workers_text = ", ".join(sorted(worker_badge_ids)) if worker_badge_ids else "none detected"
    return (
        "CORRIX EMERGENCY RESPONSE ORCHESTRATOR\n"
        f"CRITICAL compound risk verdict, Zone {verdict.zone_id}\n\n"
        f"Fired at: {fired_at}\n"
        f"Evidence hash (SHA-256): {evidence_hash}\n"
        f"Trigger reason: {verdict.trigger_reason}\n"
        f"Confidence: {verdict.confidence:.2f}\n\n"
        f"Explanation:\n{verdict.explanation}\n\n"
        f"Recommended action:\n{verdict.recommended_action}\n\n"
        f"Evacuation route: {route_text}\n"
        f"Workers currently in zone: {workers_text}\n"
    )


def send_incident_email(subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.ero_alert_from_email
    message["To"] = settings.ero_alert_to_email
    message.set_content(body)

    if settings.ero_smtp_port == 465:
        with smtplib.SMTP_SSL(settings.ero_smtp_host, settings.ero_smtp_port, timeout=15) as server:
            server.login(settings.ero_smtp_username, settings.ero_smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.ero_smtp_host, settings.ero_smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.ero_smtp_username, settings.ero_smtp_password)
            server.send_message(message)


def fire_emergency_response(
    verdict: CouncilVerdict, worker_badge_ids: list[str], driver: Driver
) -> IncidentAlert:
    """Fires on a CRITICAL verdict only, per CORRIX_BUILD_PLAN.md Step 9."""
    fired_at = datetime.now(timezone.utc).isoformat()
    evidence_snapshot, evidence_hash = build_evidence_snapshot(verdict, worker_badge_ids)
    subject = f"[CORRIX] CRITICAL compound risk in Zone {verdict.zone_id}"
    body = _format_email_body(verdict, worker_badge_ids, evidence_hash, fired_at)

    delivery_error: str | None = None
    try:
        send_incident_email(subject, body)
    except Exception as exc:
        delivery_error = str(exc)

    alert = IncidentAlert(
        alert_id=str(uuid.uuid4()),
        zone_id=verdict.zone_id,
        scenario_id=verdict.scenario_id,
        risk_level=verdict.risk_level,
        trigger_reason=verdict.trigger_reason,
        explanation=verdict.explanation,
        recommended_action=verdict.recommended_action,
        evacuation_route=verdict.evacuation_route,
        worker_badge_ids=sorted(worker_badge_ids),
        fired_at=fired_at,
        evidence_hash=evidence_hash,
        delivery_backend="smtp",
        delivery_error=delivery_error,
    )

    ensure_incident_alert_schema(driver)
    store_incident_alert(
        driver,
        alert_id=alert.alert_id,
        zone_id=alert.zone_id,
        scenario_id=alert.scenario_id,
        risk_level=alert.risk_level,
        trigger_reason=alert.trigger_reason,
        explanation=alert.explanation,
        recommended_action=alert.recommended_action,
        evacuation_route=alert.evacuation_route,
        worker_badge_ids=alert.worker_badge_ids,
        fired_at=alert.fired_at,
        evidence_hash=alert.evidence_hash,
        evidence_snapshot=evidence_snapshot,
        delivery_backend=alert.delivery_backend,
        delivery_error=alert.delivery_error,
    )

    return alert
