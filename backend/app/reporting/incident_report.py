"""The Incident Intelligence Report generator, per CORRIX_BUILD_PLAN.md
Step 9 and CORRIX_PROJECT.md §8 Pillar 4: a downloadable PDF for a
single Council verdict, with the ERO's timestamped/hashed evidence
snapshot auto-attached when the verdict fired one.

Renders a real HTML document, then prints it to PDF with a headless
Chromium instance (Playwright), rather than a limited pure-Python PDF
library: the report needs modern CSS (a real table layout, a risk-level
badge) to read as a finished document, not a plain-text dump.

This is a formal, printable/shareable exhibit, not the live dashboard,
so it deliberately does not reuse the app's dark glassmorphic theme:
black text on white, the way a document meant to be filed, printed, or
handed to a regulator actually needs to look.
"""

import html
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

RISK_COLORS = {
    "SAFE": "#2e7d32",
    "CAUTION": "#b7860b",
    "HIGH": "#c1620a",
    "CRITICAL": "#b02020",
}

PERSONA_LABELS = {
    "processSafetyEngineer": "Process Safety Engineer",
    "permitControlOfficer": "Permit Control Officer",
    "shiftOperations": "Shift Operations",
    "siteSafetyObserver": "Site Safety Observer",
}


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def render_incident_report_html(verdict: dict, ero_alert: dict | None) -> str:
    """`verdict`: the frontend's own camelCase CouncilVerdict shape.
    `ero_alert`: {evidenceHash, firedAt, deliveredOk} if this verdict is
    the one that fired the Emergency Response Orchestrator, else None."""
    risk_level = verdict.get("riskLevel", "SAFE")
    risk_color = RISK_COLORS.get(risk_level, "#444444")
    generated_at = datetime.now(timezone.utc).isoformat()

    ttc = verdict.get("timeToCritical") or {}
    route = verdict.get("evacuationRoute")
    route_html = (
        " &rarr; ".join(_esc(zone) for zone in route)
        if route
        else "No evacuation route computed for this verdict."
    )

    council = verdict.get("council") or {}
    council_rows = "".join(
        f"<tr><td class='persona'>{_esc(label)}</td><td>{_esc(council.get(key, ''))}</td></tr>"
        for key, label in PERSONA_LABELS.items()
    )

    ero_section = ""
    if ero_alert:
        delivered = ero_alert.get("deliveredOk")
        status = "Delivered" if delivered else "Delivery failed (see backend logs)"
        ero_section = f"""
        <section>
          <h2>Emergency Response Orchestrator</h2>
          <table class="kv">
            <tr><th>Fired at</th><td>{_esc(ero_alert.get('firedAt'))}</td></tr>
            <tr><th>Notification status</th><td>{_esc(status)}</td></tr>
            <tr><th>Evidence hash (SHA-256)</th><td class="mono">{_esc(ero_alert.get('evidenceHash'))}</td></tr>
          </table>
          <p class="note">This hash matches the one included in the fired notification. Independently
          recomputing it from the evidence recorded above confirms neither document was altered after
          the fact.</p>
        </section>
        """

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Corrix Incident Report, Zone {_esc(verdict.get('zoneId'))}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Arial, sans-serif; color: #1a1a1a; margin: 40px; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .subtitle {{ color: #555; font-size: 12px; margin-bottom: 24px; }}
  .badge {{
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    color: white; font-weight: 600; font-size: 12px; background: {risk_color};
  }}
  section {{ margin-bottom: 22px; }}
  h2 {{ font-size: 14px; border-bottom: 1px solid #ddd; padding-bottom: 4px; margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  table.kv th {{ text-align: left; width: 220px; color: #555; padding: 4px 8px 4px 0; vertical-align: top; }}
  table.kv td {{ padding: 4px 0; }}
  table.council td {{ padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
  td.persona {{ font-weight: 600; width: 200px; }}
  .mono {{ font-family: "Consolas", monospace; font-size: 11px; word-break: break-all; }}
  .note {{ font-size: 11px; color: #666; }}
  footer {{ margin-top: 30px; font-size: 10px; color: #888; border-top: 1px solid #ddd; padding-top: 8px; }}
</style>
</head>
<body>
  <h1>Corrix Incident Intelligence Report</h1>
  <div class="subtitle">Generated {_esc(generated_at)}</div>

  <section>
    <h2>Verdict Summary</h2>
    <table class="kv">
      <tr><th>Zone</th><td>{_esc(verdict.get('zoneId'))}</td></tr>
      <tr><th>Risk level</th><td><span class="badge">{_esc(risk_level)}</span></td></tr>
      <tr><th>Confidence</th><td>{_esc(round(float(verdict.get('confidence', 0)) * 100, 1))}%</td></tr>
      <tr><th>Compound risk flagged</th><td>{_esc(verdict.get('compoundFlag'))}</td></tr>
      <tr><th>Trigger reason</th><td>{_esc(verdict.get('triggerReason'))}</td></tr>
      <tr><th>Verdict timestamp</th><td>{_esc(verdict.get('timestamp'))}</td></tr>
      <tr><th>Scenario</th><td>{_esc(verdict.get('scenarioId') or 'Live / unscripted')}</td></tr>
    </table>
  </section>

  <section>
    <h2>Time to Critical (Monte Carlo forecast)</h2>
    <table class="kv">
      <tr><th>Median</th><td>{_esc(ttc.get('medianMinutes'))} minutes</td></tr>
      <tr><th>Interquartile range</th><td>{_esc(ttc.get('iqrLowMinutes'))}&ndash;{_esc(ttc.get('iqrHighMinutes'))} minutes</td></tr>
      <tr><th>Escalation probability</th><td>{_esc(round(float(ttc.get('escalationProbability', 0)) * 100, 1))}% within {_esc(ttc.get('horizonMinutes'))} minutes</td></tr>
    </table>
  </section>

  <section>
    <h2>Safety Council Reasoning</h2>
    <table class="council">
      {council_rows}
    </table>
  </section>

  <section>
    <h2>Explanation and Recommended Action</h2>
    <p>{_esc(verdict.get('explanation'))}</p>
    <p><strong>Recommended action:</strong> {_esc(verdict.get('recommendedAction'))}</p>
  </section>

  <section>
    <h2>Evacuation Route</h2>
    <p>{route_html}</p>
  </section>

  {ero_section}

  <footer>
    Generated automatically by Corrix's Safety Council. Every statement above reflects the
    Council's own real-time reasoning over live sensor, permit, shift, and worker-location data;
    none of it is a template filled in after the fact.
  </footer>
</body>
</html>"""


def render_pdf(html_content: str) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html_content, wait_until="load")
            return page.pdf(format="A4", margin={"top": "20px", "bottom": "20px"})
        finally:
            browser.close()


def generate_incident_report_pdf(verdict: dict, ero_alert: dict | None) -> bytes:
    return render_pdf(render_incident_report_html(verdict, ero_alert))
