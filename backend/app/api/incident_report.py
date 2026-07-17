"""Serves the Incident Intelligence Report as a downloadable PDF, per
CORRIX_BUILD_PLAN.md Step 9: one-click reporting for whichever verdict
is currently on screen, live or mock, not tied to a server-side history
lookup, so the "Incident Report" button in the top bar works the same
way regardless of connection mode.
"""

from fastapi import APIRouter, Response

from app.reporting.incident_report import generate_incident_report_pdf

router = APIRouter()


@router.post("/api/incident-report")
def post_incident_report(body: dict) -> Response:
    verdict = body.get("verdict") or {}
    ero_alert = body.get("eroAlert")
    pdf_bytes = generate_incident_report_pdf(verdict, ero_alert)
    zone_id = verdict.get("zoneId", "unknown")
    filename = f"corrix-incident-report-{zone_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
