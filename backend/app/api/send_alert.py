"""Manual "send email alert" endpoint. The Emergency Response Orchestrator
fires automatically only on a CRITICAL verdict to the backend-configured
recipient; this lets a safety officer send the same real, hashed-evidence
alert on demand for a HIGH or CRITICAL verdict, to a recipient they choose
in the UI.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.emergency.orchestrator import fire_emergency_response
from app.memory.exemplar_store import get_shared_driver
from app.schemas import CouncilEvidence, CouncilVerdict, TimeToCriticalForecast

router = APIRouter()


class SendAlertRequest(BaseModel):
    verdict: dict
    toEmail: str | None = None


def _verdict_from_camel(d: dict) -> CouncilVerdict:
    ttc = d.get("timeToCritical") or {}
    c = d.get("council") or {}
    ts = d.get("timestamp")
    return CouncilVerdict(
        zone_id=d.get("zoneId", "?"),
        scenario_id=d.get("scenarioId"),
        trigger_reason=d.get("triggerReason", "rule_threshold"),
        timestamp=datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc),
        council=CouncilEvidence(
            process_safety_engineer=c.get("processSafetyEngineer", ""),
            permit_control_officer=c.get("permitControlOfficer", ""),
            shift_operations=c.get("shiftOperations", ""),
            site_safety_observer=c.get("siteSafetyObserver", ""),
        ),
        risk_level=d.get("riskLevel", "HIGH"),
        confidence=float(d.get("confidence", 0.0)),
        compound_flag=bool(d.get("compoundFlag", False)),
        time_to_critical=TimeToCriticalForecast(
            median_minutes=float(ttc.get("medianMinutes", 0.0)),
            iqr_low_minutes=float(ttc.get("iqrLowMinutes", 0.0)),
            iqr_high_minutes=float(ttc.get("iqrHighMinutes", 0.0)),
            escalation_probability=float(ttc.get("escalationProbability", 0.0)),
            horizon_minutes=int(ttc.get("horizonMinutes", 60)),
        ),
        explanation=d.get("explanation", ""),
        recommended_action=d.get("recommendedAction", ""),
        evacuation_route=d.get("evacuationRoute"),
    )


@router.post("/api/send-alert")
def send_alert(req: SendAlertRequest) -> dict:
    settings = get_settings()
    if not (settings.ero_smtp_host and settings.ero_smtp_username and settings.ero_alert_from_email):
        return {
            "ok": False,
            "error": "Email alerts are not configured on the server. Set the ERO_SMTP_* and ERO_ALERT_FROM_EMAIL values in the backend .env.",
        }

    recipient = (req.toEmail or "").strip() or settings.ero_alert_to_email
    if not recipient or "@" not in recipient:
        return {"ok": False, "error": "Enter a valid recipient email address."}

    verdict = _verdict_from_camel(req.verdict)
    if verdict.risk_level not in ("HIGH", "CRITICAL"):
        return {"ok": False, "error": "Alerts can only be sent for a HIGH or CRITICAL verdict."}

    alert = fire_emergency_response(verdict, [], get_shared_driver(), to_email=recipient)
    if alert.delivery_error is not None:
        return {"ok": False, "error": f"The email could not be delivered: {alert.delivery_error}"}

    return {
        "ok": True,
        "toEmail": recipient,
        "zoneId": alert.zone_id,
        "riskLevel": alert.risk_level,
        "evidenceHash": alert.evidence_hash,
    }
