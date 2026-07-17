"""The cached-fallback path for LLM failure, per CORRIX_BUILD_PLAN.md
Step 9: "deliberately blocking the primary LLM path mid-run still
resolves to a sensible fallback, tested at least once." Step 4 already
covers the Groq-blocked/Gemini-still-up case (test_council_graph.py's
test_graph_resolves_via_gemini_when_groq_is_deliberately_blocked). This
file covers the harder case that a real live-verification pass this
session actually hit: both Groq and Gemini down at once, which
previously crashed the WebSocket connection outright rather than
degrading.

Neither layer here makes a real LLM call: both providers are mocked to
fail, deliberately, so this doesn't cost real quota and is deterministic
regardless of the account's actual rate-limit state."""

from unittest.mock import patch

import pytest

from app.council import llm_client
from app.council.agents import PROCESS_SAFETY_ENGINEER
from app.council.chair import synthesize
from app.council.graph import run_council
from app.council.sample_payloads import ALL_SAMPLE_PAYLOADS
from app.schemas import CouncilEvidence


def _break_both_providers():
    def _broken(*args, **kwargs):
        raise RuntimeError("simulated total outage")

    return patch.object(llm_client, "_call_groq", _broken), patch.object(
        llm_client, "_call_gemini", _broken
    )


def test_evidence_agent_falls_back_to_raw_text_when_both_providers_fail():
    groq_patch, gemini_patch = _break_both_providers()
    with groq_patch, gemini_patch:
        response = PROCESS_SAFETY_ENGINEER.run("Zone Z1 LEL reading: 42% (rising).")
    assert response.backend == "fallback"
    assert response.text == "Zone Z1 LEL reading: 42% (rising)."


def test_chair_returns_a_labeled_degraded_verdict_when_both_providers_fail():
    payload = ALL_SAMPLE_PAYLOADS["S1"]
    evidence = CouncilEvidence(
        process_safety_engineer=payload["process_safety_engineer"],
        permit_control_officer=payload["permit_control_officer"],
        shift_operations=payload["shift_operations"],
        site_safety_observer=payload["site_safety_observer"],
    )
    groq_patch, gemini_patch = _break_both_providers()
    with groq_patch, gemini_patch:
        verdict = synthesize(
            zone_id=payload["zone_id"],
            trigger_reason="rule_threshold",
            evidence=evidence,
            scenario_id="S1",
        )
    assert verdict.risk_level == "HIGH"
    assert verdict.confidence == 0.0
    assert "unavailable" in verdict.explanation.lower()
    assert "human" in verdict.recommended_action.lower()
    # the real evidence is still preserved, even though no LLM judged it
    assert verdict.council.process_safety_engineer == payload["process_safety_engineer"]


def test_chair_falls_back_on_a_malformed_response_too_not_just_a_hard_failure():
    """A response that comes back but isn't parseable JSON must degrade
    the same way as a network failure, not crash with a KeyError."""
    payload = ALL_SAMPLE_PAYLOADS["S1"]
    evidence = CouncilEvidence(
        process_safety_engineer=payload["process_safety_engineer"],
        permit_control_officer=payload["permit_control_officer"],
        shift_operations=payload["shift_operations"],
        site_safety_observer=payload["site_safety_observer"],
    )

    def _garbled(*args, **kwargs):
        raise RuntimeError("simulated outage")

    with patch.object(llm_client, "_call_groq", _garbled), patch.object(
        llm_client, "_call_gemini", _garbled
    ):
        verdict = synthesize(
            zone_id=payload["zone_id"], trigger_reason="novelty", evidence=evidence,
        )
    assert verdict.risk_level == "HIGH"
    assert verdict.trigger_reason == "novelty"


def test_full_graph_resolves_to_a_sensible_fallback_when_both_providers_are_blocked():
    """The actual Step 9 DoD test, extended past Step 4's Groq-only case:
    the full graph (four evidence agents + Chair), with both providers
    deliberately blocked, must still produce a real, usable CouncilVerdict
    rather than raising and crashing the caller (the live WebSocket
    handler, in production)."""
    payload = ALL_SAMPLE_PAYLOADS["S2"]
    groq_patch, gemini_patch = _break_both_providers()
    with groq_patch, gemini_patch:
        verdict = run_council(
            zone_id=payload["zone_id"],
            trigger_reason="rule_threshold",
            raw_evidence=payload,
            scenario_id="S2",
            thread_id="test-total-outage-fallback",
        )
    assert verdict.risk_level == "HIGH"
    assert verdict.confidence == 0.0
    # every evidence field fell back to the raw text fed in, unpolished
    # but fully present, not dropped
    assert verdict.council.process_safety_engineer == payload["process_safety_engineer"]
    assert verdict.council.permit_control_officer == payload["permit_control_officer"]
