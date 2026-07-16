"""The Safety Council LangGraph state machine, per CORRIX_PROJECT.md §6.1
and CORRIX_BUILD_PLAN.md Step 4: four evidence agents run (conceptually
in parallel — each depends only on the initial state, not on each
other), converge into the Chair, which is the only node that sees all
four structured outputs.

The Safety Officer Override (§6.5) is a real LangGraph interrupt, not a
UI-only pause: the graph is compiled with `interrupt_before=["chair"]`
and a checkpointer, so it genuinely stops execution after the four
evidence nodes and before the Chair runs. A human note is written into
the checkpointed state, and resuming re-invokes the graph from that
checkpoint — the Chair then sees the note as part of its input, not as
a cosmetic addition bolted on after the verdict already exists.
"""

from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.council.agents import (
    PERMIT_CONTROL_OFFICER,
    PROCESS_SAFETY_ENGINEER,
    SHIFT_OPERATIONS,
    SITE_SAFETY_OBSERVER,
    EvidenceAgent,
)
from app.council.chair import synthesize
from app.schemas import CouncilEvidence, CouncilVerdict, TriggerReason


class CouncilState(TypedDict, total=False):
    zone_id: str
    scenario_id: Optional[str]
    trigger_reason: TriggerReason
    raw_evidence: dict[str, str]
    process_safety_engineer: str
    permit_control_officer: str
    shift_operations: str
    site_safety_observer: str
    override_note: Optional[str]
    memory_context: Optional[str]
    verdict: CouncilVerdict


def _make_evidence_node(agent: EvidenceAgent):
    def node(state: CouncilState) -> dict:
        evidence_text = state["raw_evidence"][agent.persona_key]
        response = agent.run(evidence_text)
        return {agent.persona_key: response.text}

    node.__name__ = f"evidence_{agent.persona_key}"
    return node


def _chair_node(state: CouncilState) -> dict:
    evidence = CouncilEvidence(
        process_safety_engineer=state["process_safety_engineer"],
        permit_control_officer=state["permit_control_officer"],
        shift_operations=state["shift_operations"],
        site_safety_observer=state["site_safety_observer"],
    )
    verdict = synthesize(
        zone_id=state["zone_id"],
        trigger_reason=state["trigger_reason"],
        evidence=evidence,
        scenario_id=state.get("scenario_id"),
        override_note=state.get("override_note"),
        memory_context=state.get("memory_context"),
    )
    return {"verdict": verdict}


def build_council_graph():
    """Compiled with a checkpointer and interrupt_before=["chair"] so the
    Safety Officer Override is a real graph pause, not simulated."""
    builder = StateGraph(CouncilState)

    builder.add_node("process_safety_engineer", _make_evidence_node(PROCESS_SAFETY_ENGINEER))
    builder.add_node("permit_control_officer", _make_evidence_node(PERMIT_CONTROL_OFFICER))
    builder.add_node("shift_operations", _make_evidence_node(SHIFT_OPERATIONS))
    builder.add_node("site_safety_observer", _make_evidence_node(SITE_SAFETY_OBSERVER))
    builder.add_node("chair", _chair_node)

    for evidence_node in [
        "process_safety_engineer",
        "permit_control_officer",
        "shift_operations",
        "site_safety_observer",
    ]:
        builder.add_edge(START, evidence_node)
        builder.add_edge(evidence_node, "chair")

    builder.add_edge("chair", END)

    return builder.compile(checkpointer=MemorySaver(), interrupt_before=["chair"])


def run_council(
    zone_id: str,
    trigger_reason: TriggerReason,
    raw_evidence: dict[str, str],
    scenario_id: str | None = None,
    thread_id: str = "default",
    memory_context: str | None = None,
) -> CouncilVerdict:
    """Run the Council to completion (no override) — convenience wrapper
    for the common case."""
    graph = build_council_graph()
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(
        {
            "zone_id": zone_id,
            "trigger_reason": trigger_reason,
            "raw_evidence": raw_evidence,
            "scenario_id": scenario_id,
            "memory_context": memory_context,
        },
        config,
    )
    # graph paused before "chair" (interrupt_before) — resume to completion
    final_state = graph.invoke(None, config)
    return final_state["verdict"]


def apply_safety_officer_override(graph, config: dict, note: str):
    """Write a human Safety Officer's note into the paused graph's
    checkpointed state, so the Chair sees it when the graph resumes. Must
    be called while the graph is paused at `interrupt_before=["chair"]`
    (i.e. after the first `graph.invoke(...)` call, before the resuming
    `graph.invoke(None, config)`).

    `as_node` is required because the four evidence nodes update state in
    the same parallel superstep, which makes LangGraph's automatic
    "which node does this update belong to" inference ambiguous — any
    valid node name works here, it's bookkeeping, not a claim about which
    node produced the human's input.
    """
    graph.update_state(config, {"override_note": note}, as_node="site_safety_observer")
