"""Chair-only post-verdict reconsideration (`app.api.websocket._reconsider`):
deterministic, LLM-free unit tests isolating the Emergency Response
Orchestrator double-fire guard, since coercing a real LLM into a specific
risk_level twice would be flaky rather than a real correctness check."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.api import websocket
from app.api.websocket import ConveningContext, _reconsider
from app.schemas import CouncilEvidence, CouncilVerdict, TimeToCriticalForecast
from app.schemas.zone import HazardClass, PlantLayout, Zone

ZONE_ID = "Z1"


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, msg: dict) -> None:
        self.sent.append(msg)


def _layout() -> PlantLayout:
    return PlantLayout(
        zones=[
            Zone(
                zone_id=ZONE_ID,
                name="Test Zone",
                hazard_class=HazardClass.HIGH,
                primary_role="casting",
                is_confined_space=False,
                is_assembly_point=False,
            )
        ],
        adjacency=[],
    )


def _verdict(risk_level: str, explanation: str = "original explanation") -> CouncilVerdict:
    return CouncilVerdict(
        zone_id=ZONE_ID,
        scenario_id=None,
        trigger_reason="rule_threshold",
        timestamp=datetime.now(timezone.utc),
        council=CouncilEvidence(
            process_safety_engineer="nominal readings",
            permit_control_officer="no active permits",
            shift_operations="mid-shift, no changeover imminent",
            site_safety_observer="no workers detected",
        ),
        risk_level=risk_level,
        confidence=0.9,
        compound_flag=True,
        time_to_critical=TimeToCriticalForecast(
            median_minutes=10.0,
            iqr_low_minutes=5.0,
            iqr_high_minutes=20.0,
            escalation_probability=0.5,
            horizon_minutes=60,
        ),
        explanation=explanation,
        recommended_action="original action",
    )


def _context(risk_level: str) -> ConveningContext:
    verdict = _verdict(risk_level)
    return ConveningContext(
        zone_id=ZONE_ID,
        trigger_reason="rule_threshold",
        scenario_id=None,
        raw_evidence={
            "process_safety_engineer": "nominal readings",
            "permit_control_officer": "no active permits",
        },
        memory_context=None,
        layout=_layout(),
        zone_risk={ZONE_ID: risk_level},
        worker_positions={},
        time_to_critical=None,
        last_verdict=verdict,
    )


def test_reconsider_does_not_refire_ero_when_already_critical():
    """Reconsidering a verdict that was already CRITICAL, and still is,
    must not send a second emergency notification for the same
    incident."""
    context = _context("CRITICAL")
    new_verdict = _verdict("CRITICAL", explanation="reconsidered, still critical")
    ws = _FakeWebSocket()

    with (
        patch.object(websocket, "synthesize", return_value=new_verdict),
        patch.object(websocket, "get_shared_driver", return_value=None),
        patch.object(websocket, "update_zone_risk_state"),
        patch.object(websocket, "find_regulatory_grounding", return_value=[]),
        patch.object(websocket, "fire_emergency_response") as mock_fire,
    ):
        result = asyncio.run(_reconsider(ws, context, "a clarifying note"))

    mock_fire.assert_not_called()
    sent_types = [m["type"] for m in ws.sent]
    assert sent_types == ["reconsidering", "verdict"]
    assert result.last_verdict.risk_level == "CRITICAL"
    assert result.last_verdict.explanation == "reconsidered, still critical"


def test_reconsider_fires_ero_on_fresh_escalation_to_critical():
    """A reconsideration that newly escalates a verdict into CRITICAL
    (it was HIGH before) is a genuine new emergency and must still fire
    the Emergency Response Orchestrator."""
    context = _context("HIGH")
    new_verdict = _verdict("CRITICAL", explanation="reconsidered, now critical")
    ws = _FakeWebSocket()
    fake_alert = SimpleNamespace(
        zone_id=ZONE_ID,
        delivery_error=None,
        evidence_hash="test-hash",
        fired_at="2026-01-01T00:00:00+00:00",
    )

    with (
        patch.object(websocket, "synthesize", return_value=new_verdict),
        patch.object(websocket, "get_shared_driver", return_value=None),
        patch.object(websocket, "update_zone_risk_state"),
        patch.object(websocket, "find_regulatory_grounding", return_value=[]),
        patch.object(websocket, "fire_emergency_response", return_value=fake_alert) as mock_fire,
    ):
        result = asyncio.run(_reconsider(ws, context, "a clarifying note"))

    mock_fire.assert_called_once()
    sent_types = [m["type"] for m in ws.sent]
    assert sent_types == ["reconsidering", "verdict", "ero_fired"]
    assert result.last_verdict.risk_level == "CRITICAL"


def test_reconsider_reuses_the_original_four_agents_evidence():
    """The whole point of a Chair-only reconsideration: the four agents'
    evidence passed to `synthesize` must be exactly what the previous
    verdict already carried, not re-gathered."""
    context = _context("SAFE")
    new_verdict = _verdict("CAUTION", explanation="reconsidered")
    ws = _FakeWebSocket()

    with (
        patch.object(websocket, "synthesize", return_value=new_verdict) as mock_synthesize,
        patch.object(websocket, "get_shared_driver", return_value=None),
        patch.object(websocket, "update_zone_risk_state"),
        patch.object(websocket, "find_regulatory_grounding", return_value=[]),
        patch.object(websocket, "fire_emergency_response"),
    ):
        asyncio.run(_reconsider(ws, context, "a clarifying note"))

    mock_synthesize.assert_called_once_with(
        zone_id=ZONE_ID,
        trigger_reason="rule_threshold",
        evidence=context.last_verdict.council,
        scenario_id=None,
        override_note="a clarifying note",
        memory_context=None,
    )
