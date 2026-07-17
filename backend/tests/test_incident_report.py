"""The Incident Intelligence Report generator, per CORRIX_BUILD_PLAN.md
Step 9: a real PDF, rendered by a real headless-Chromium pass over a
real HTML document, not a stub. Verified both at the render-function
level and through the actual FastAPI endpoint the frontend's "Incident
Report" button calls."""

from fastapi.testclient import TestClient

from app.main import app
from app.reporting.incident_report import generate_incident_report_pdf, render_incident_report_html

SAMPLE_VERDICT = {
    "zoneId": "Z2",
    "scenarioId": "S2",
    "triggerReason": "rule_threshold",
    "timestamp": "2026-07-17T12:00:00+00:00",
    "council": {
        "processSafetyEngineer": "Confined-space gas concentration is elevated.",
        "permitControlOfficer": "An active confined-space entry permit is in effect.",
        "shiftOperations": "No changeover in progress.",
        "siteSafetyObserver": "One worker confirmed present.",
    },
    "riskLevel": "HIGH",
    "confidence": 0.81,
    "compoundFlag": True,
    "timeToCritical": {
        "medianMinutes": 22.0,
        "iqrLowMinutes": 15.0,
        "iqrHighMinutes": 30.0,
        "escalationProbability": 0.4,
        "horizonMinutes": 60.0,
    },
    "explanation": "A compound risk in Zone 2: elevated gas & an active confined-space permit.",
    "recommendedAction": "Withdraw personnel pending re-verification.",
    "evacuationRoute": ["Z2", "Z3", "Z4"],
}


def test_render_incident_report_html_includes_key_fields():
    rendered = render_incident_report_html(SAMPLE_VERDICT, ero_alert=None)
    assert "Z2" in rendered
    assert "HIGH" in rendered
    assert "confined-space entry permit" in rendered
    assert "Z2" in rendered and "Z3" in rendered and "Z4" in rendered


def test_render_incident_report_html_escapes_special_characters():
    verdict = dict(SAMPLE_VERDICT, explanation="Zone <Z2> risk & permit conflict")
    rendered = render_incident_report_html(verdict, ero_alert=None)
    assert "<Z2>" not in rendered
    assert "&lt;Z2&gt;" in rendered


def test_render_incident_report_html_attaches_ero_evidence_hash():
    ero_alert = {"evidenceHash": "abc123", "firedAt": "2026-07-17T12:00:05+00:00", "deliveredOk": True}
    rendered = render_incident_report_html(SAMPLE_VERDICT, ero_alert=ero_alert)
    assert "abc123" in rendered
    assert "Delivered" in rendered


def test_generate_incident_report_pdf_produces_a_real_pdf():
    pdf_bytes = generate_incident_report_pdf(SAMPLE_VERDICT, ero_alert=None)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_incident_report_endpoint_returns_a_downloadable_pdf():
    client = TestClient(app)
    response = client.post("/api/incident-report", json={"verdict": SAMPLE_VERDICT, "eroAlert": None})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
