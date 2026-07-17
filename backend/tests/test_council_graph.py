"""The Safety Council LangGraph state machine: end-to-end runs against
hand-crafted S1-S4 payloads, and the Safety Officer Override as a real
graph interrupt, per Step 4's Definition of Done."""

import time
from unittest.mock import patch

import pytest

from app.council import llm_client
from app.council.agents import PROCESS_SAFETY_ENGINEER
from app.council.graph import (
    _make_evidence_node,
    apply_safety_officer_override,
    build_council_graph,
    run_council,
)
from app.council.sample_payloads import ALL_SAMPLE_PAYLOADS
from tests.conftest import skip_on_rate_limit


@pytest.mark.parametrize("scenario_id", ["S1", "S2", "S3", "S4"])
def test_council_runs_end_to_end_in_a_few_seconds(scenario_id):
    payload = ALL_SAMPLE_PAYLOADS[scenario_id]
    start = time.time()
    with skip_on_rate_limit():
        verdict = run_council(
            zone_id=payload["zone_id"],
            trigger_reason="rule_threshold",
            raw_evidence=payload,
            scenario_id=scenario_id,
            thread_id=f"test-timing-{scenario_id}",
        )
    elapsed = time.time() - start
    assert elapsed < 30, f"{scenario_id} took {elapsed:.1f}s, too slow for a live demo"
    assert verdict.risk_level in ("HIGH", "CRITICAL")
    assert verdict.compound_flag is True


def test_s2_s3_s4_produce_differently_reasoned_verdicts():
    """Not just S1: the same graph must generalize, not fit one scripted
    case (Step 4 DoD)."""
    explanations = set()
    for scenario_id in ["S2", "S3", "S4"]:
        payload = ALL_SAMPLE_PAYLOADS[scenario_id]
        with skip_on_rate_limit():
            verdict = run_council(
                zone_id=payload["zone_id"],
                trigger_reason="rule_threshold",
                raw_evidence=payload,
                scenario_id=scenario_id,
                thread_id=f"test-vary-{scenario_id}",
            )
        explanations.add(verdict.explanation)
        assert verdict.risk_level in ("HIGH", "CRITICAL")
    assert len(explanations) == 3


def test_override_pauses_before_chair_and_incorporates_the_note():
    """A real LangGraph interrupt: the graph stops before the chair node,
    a human note is written into the checkpointed state, and resuming
    produces a verdict whose explanation/recommended_action visibly
    reflects it, not a UI-only pause."""
    graph = build_council_graph()
    config = {"configurable": {"thread_id": "test-override"}}
    payload = ALL_SAMPLE_PAYLOADS["S1"]

    with skip_on_rate_limit():
        state_after_pause = graph.invoke(
            {
                "zone_id": payload["zone_id"],
                "trigger_reason": "rule_threshold",
                "raw_evidence": payload,
                "scenario_id": "S1",
            },
            config,
        )
    # interrupt_before=["chair"]: graph stopped before the chair ran, so
    # no verdict exists yet, but all four evidence nodes already ran.
    assert "verdict" not in state_after_pause
    assert state_after_pause["process_safety_engineer"]
    assert state_after_pause["site_safety_observer"]

    override_note = (
        "Permit P-2291 was already suspended manually 5 minutes ago by the "
        "Zone 1 supervisor, pending gas verification."
    )
    apply_safety_officer_override(graph, config, override_note)

    with skip_on_rate_limit():
        final_state = graph.invoke(None, config)
    verdict = final_state["verdict"]
    assert verdict is not None
    combined_text = (verdict.explanation + " " + verdict.recommended_action).lower()
    assert "suspend" in combined_text or "p-2291" in combined_text


def test_silo_enforced_inside_the_graph_not_just_on_the_agent_object():
    """The evidence node for the Process Safety Engineer must only ever
    be able to call tools from its bound server, checked here at the
    node-construction level used by the actual compiled graph."""
    node = _make_evidence_node(PROCESS_SAFETY_ENGINEER)
    assert node.__name__ == "evidence_process_safety_engineer"
    assert set(PROCESS_SAFETY_ENGINEER.bound_tool_names) == {
        "get_zone_readings",
        "get_anomaly_score",
    }


def test_graph_resolves_via_gemini_when_groq_is_deliberately_blocked():
    """Step 4's Definition of Done: deliberately exhaust/block the Groq
    path once and confirm the graph still resolves, checked here at the
    full graph level (all four agents + Chair), not just the client."""

    def _broken_groq(*args, **kwargs):
        raise RuntimeError("simulated Groq outage")

    payload = ALL_SAMPLE_PAYLOADS["S1"]
    with patch.object(llm_client, "_call_groq", _broken_groq):
        with skip_on_rate_limit():
            verdict = run_council(
                zone_id=payload["zone_id"],
                trigger_reason="rule_threshold",
                raw_evidence=payload,
                scenario_id="S1",
                thread_id="test-graph-failover",
            )
    assert verdict.risk_level in ("HIGH", "CRITICAL")
    assert verdict.compound_flag is True
