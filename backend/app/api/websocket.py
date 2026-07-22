"""The live scenario WebSocket: streams a precomputed playback at a
watchable rate, and, when the trigger point is reached, actually
convenes the real Safety Council (Step 4's LangGraph), pausing at the
same interrupt_before=["chair"] checkpoint used for the Safety Officer
Override so a demo user can genuinely intervene, not a simulated pause.

Protocol (JSON messages over one WebSocket connection):

Client -> server:
  {"type": "start", "scenario_id": "S1"}   start/restart authored playback
  {"type": "open_challenge"}               draw and play a random curated
                                            Open Challenge combination (§13.5)
  {"type": "override", "note": "..."}      submit an override note
                                            while stage == "deliberating"
  {"type": "reconsider", "note": "..."}    once a verdict exists, ask the
                                            Chair to rule again over the same
                                            four agents' evidence with a new
                                            note; valid at any point after a
                                            verdict, including after
                                            playback_complete, and any number
                                            of times

Server -> client:
  {"type": "tick", "minute": ..., "zoneRisk": {...}, "workers": {...}}
  {"type": "open_challenge_drawn", "label": "..."}   which combination was drawn
  {"type": "council_convening"}
  {"type": "deliberating", "council": {...four evidence texts...}}
  {"type": "verdict", "verdict": {...camelCase CouncilVerdict...}}
  {"type": "ero_fired", "zoneId": ..., "deliveredOk": bool, "evidenceHash": "..."}
  {"type": "council_error", "message": "..."}   convening failed unexpectedly;
                                                 playback continues past it
  {"type": "reconsidering"}                sent right before the Chair
                                            re-rules on a "reconsider" request
  {"type": "playback_complete"}
"""

import asyncio
import logging
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from fastapi import WebSocket, WebSocketDisconnect

import random

from app.api.live_evidence import (
    format_permit_text,
    format_process_safety_text,
    format_shift_text,
    format_site_safety_text,
)
from app.api.live_scenario import (
    ScenarioPlayback,
    precompute_open_challenge_playback,
    precompute_playback,
)
from app.council.chair import synthesize
from app.council.graph import apply_safety_officer_override, build_council_graph
from app.detection.anomaly_scorer import calibrate_baseline
from app.detection.evacuation_routing import find_evacuation_route
from app.detection.novelty_training import get_cached_novelty_model
from app.detection.risk_propagation import predict_risk_propagation
from app.detection.time_to_critical import forecast_time_to_critical
from app.emergency.orchestrator import fire_emergency_response
from app.memory.exemplar_store import get_shared_driver
from app.regulatory.retrieval import find_regulatory_grounding
from app.schemas import (
    CouncilVerdict,
    GasSignalConfig,
    PlantLayout,
    RegulatoryCitation,
    RiskLevel,
    RiskPropagationZone,
)
from app.simulation.open_challenge import CURATED_COMBINATIONS
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import DEFAULT_START_TIME
from app.state.live_risk_state import update_zone_risk_state

logger = logging.getLogger(__name__)

PLAYBACK_FRAME_SECONDS = 0.35
OVERRIDE_WINDOW_SECONDS = 8.0


def _verdict_to_camel(v: CouncilVerdict) -> dict:
    return {
        "zoneId": v.zone_id,
        "scenarioId": v.scenario_id,
        "triggerReason": v.trigger_reason,
        "timestamp": v.timestamp.isoformat(),
        "council": {
            "processSafetyEngineer": v.council.process_safety_engineer,
            "permitControlOfficer": v.council.permit_control_officer,
            "shiftOperations": v.council.shift_operations,
            "siteSafetyObserver": v.council.site_safety_observer,
        },
        "riskLevel": v.risk_level,
        "confidence": v.confidence,
        "compoundFlag": v.compound_flag,
        "timeToCritical": {
            "medianMinutes": v.time_to_critical.median_minutes,
            "iqrLowMinutes": v.time_to_critical.iqr_low_minutes,
            "iqrHighMinutes": v.time_to_critical.iqr_high_minutes,
            "escalationProbability": v.time_to_critical.escalation_probability,
            "horizonMinutes": v.time_to_critical.horizon_minutes,
        },
        "explanation": v.explanation,
        "recommendedAction": v.recommended_action,
        "evacuationRoute": v.evacuation_route,
        "regulatoryCitations": [
            {
                "framework": c.framework,
                "sourceDocument": c.source_document,
                "sectionNumber": c.section_number,
                "sectionTitle": c.section_title,
                "isSupplementary": c.is_supplementary,
            }
            for c in (v.regulatory_citations or [])
        ]
        or None,
        "riskPropagation": [
            {"zoneId": p.zone_id, "hops": p.hops, "score": p.score}
            for p in (v.risk_propagation or [])
        ]
        or None,
    }


@dataclass
class TimeToCriticalInputs:
    """The Monte Carlo forecaster's inputs (Step 8 of CORRIX_BUILD_PLAN.md),
    bundled so `_run_council` can stay source-agnostic: whoever assembles
    this (today, only `_convene_council`) already has the full signal
    series needed to calibrate `baseline_mean`/`baseline_std` itself."""

    gas_config: GasSignalConfig
    current_value: float
    elapsed_minutes: float
    baseline_mean: float
    baseline_std: float
    seed: int


@dataclass
class ConveningContext:
    """Everything a later post-verdict `reconsider` needs to ask the Chair
    to rule again without re-querying the four evidence agents: their
    original data hasn't changed, only a human's instruction is new.
    Built by `_run_council` once a verdict has been delivered, and
    replaced wholesale (via `dataclasses.replace`, not mutated) by
    `_reconsider` after each reconsideration, so a second reconsideration
    builds on the most recent verdict, not the original one."""

    zone_id: str
    trigger_reason: str
    scenario_id: str | None
    raw_evidence: dict[str, str]
    memory_context: str | None
    layout: PlantLayout
    zone_risk: dict[str, RiskLevel] | None
    worker_positions: dict[str, str] | None
    time_to_critical: TimeToCriticalInputs | None
    last_verdict: CouncilVerdict


async def _enrich_and_deliver_verdict(
    websocket: WebSocket,
    verdict: CouncilVerdict,
    *,
    trigger_reason: str,
    raw_evidence: dict[str, str],
    layout: PlantLayout,
    zone_risk: dict[str, RiskLevel] | None,
    worker_positions: dict[str, str] | None,
    time_to_critical: TimeToCriticalInputs | None,
    previous_risk_level: RiskLevel | None,
) -> CouncilVerdict:
    """Attaches the Monte Carlo forecast, evacuation route, risk
    propagation, and regulatory grounding to a freshly synthesized
    verdict, persists it, and delivers it over `websocket`. Shared by a
    fresh convening (`_run_council`) and a Chair-only reconsideration
    (`_reconsider`), so this logic is never duplicated between them.

    `previous_risk_level` guards the Emergency Response Orchestrator
    against firing twice for the same incident: it only fires when this
    verdict is newly CRITICAL, not when it was already CRITICAL before
    (a fresh convening always passes `None` here, so it fires exactly as
    before; a reconsideration passes the prior verdict's risk level)."""
    if time_to_critical is not None:
        verdict.time_to_critical = await asyncio.to_thread(
            forecast_time_to_critical,
            current_value=time_to_critical.current_value,
            elapsed_minutes=time_to_critical.elapsed_minutes,
            gas_config=time_to_critical.gas_config,
            baseline_mean=time_to_critical.baseline_mean,
            baseline_std=time_to_critical.baseline_std,
            seed=time_to_critical.seed,
        )

    if verdict.risk_level in ("HIGH", "CRITICAL"):
        if zone_risk is not None:
            route = find_evacuation_route(layout, zone_risk, verdict.zone_id)
            if route is not None:
                verdict.evacuation_route = route.path
        # Where the compound risk could spread next if it isn't contained.
        propagation = predict_risk_propagation(layout, verdict.zone_id)
        if propagation:
            verdict.risk_propagation = [
                RiskPropagationZone(zone_id=p.zone_id, hops=p.hops, score=p.score)
                for p in propagation
            ]

    # Ground the verdict in the regulation most relevant to what the four
    # agents actually reported. Never fatal to a convening: a lookup
    # failure just leaves the verdict without a cited clause.
    try:
        situation = f"{raw_evidence['process_safety_engineer']} {raw_evidence['permit_control_officer']}"
        citations = await asyncio.to_thread(
            find_regulatory_grounding, get_shared_driver(), situation
        )
        if citations:
            verdict.regulatory_citations = [
                RegulatoryCitation(
                    framework=c["framework"],
                    source_document=c["source_document"],
                    section_number=c["section_number"],
                    section_title=c["section_title"],
                    is_supplementary=c["is_supplementary"],
                )
                for c in citations
            ]
    except Exception as exc:
        logger.warning("regulatory grounding lookup failed: %s", exc)

    await asyncio.to_thread(
        update_zone_risk_state,
        get_shared_driver(),
        zone_id=verdict.zone_id,
        risk_level=verdict.risk_level,
        confidence=verdict.confidence,
        compound_flag=verdict.compound_flag,
        trigger_reason=trigger_reason,
        explanation=verdict.explanation,
        recommended_action=verdict.recommended_action,
        scenario_id=verdict.scenario_id,
    )

    await websocket.send_json({"type": "verdict", "verdict": _verdict_to_camel(verdict)})

    if verdict.risk_level == "CRITICAL" and previous_risk_level != "CRITICAL":
        worker_badge_ids = [
            badge_id for badge_id, badge_zone_id in (worker_positions or {}).items()
            if badge_zone_id == verdict.zone_id
        ]
        try:
            alert = await asyncio.to_thread(
                fire_emergency_response, verdict, worker_badge_ids, get_shared_driver()
            )
            await websocket.send_json(
                {
                    "type": "ero_fired",
                    "zoneId": alert.zone_id,
                    "deliveredOk": alert.delivery_error is None,
                    "evidenceHash": alert.evidence_hash,
                    "firedAt": alert.fired_at,
                }
            )
        except Exception as exc:
            # The verdict has already been delivered to the client above; a
            # transient failure here (a Neo4j hiccup writing the incident
            # alert, say, genuinely seen during this project's own testing)
            # must not take down the connection after that.
            logger.error("ERO firing failed unexpectedly: %s", exc)
            await websocket.send_json(
                {
                    "type": "ero_fired",
                    "zoneId": verdict.zone_id,
                    "deliveredOk": False,
                    "evidenceHash": "unavailable",
                    "firedAt": datetime.now(timezone.utc).isoformat(),
                }
            )

    return verdict


async def _run_council(
    websocket: WebSocket,
    incoming: "asyncio.Queue[dict]",
    zone_id: str,
    trigger_reason: str,
    raw_evidence: dict[str, str],
    scenario_id: str | None,
    memory_context: str | None,
    *,
    layout: PlantLayout | None = None,
    zone_risk: dict[str, RiskLevel] | None = None,
    worker_positions: dict[str, str] | None = None,
    time_to_critical: TimeToCriticalInputs | None = None,
) -> ConveningContext:
    """Runs the Safety Council to a verdict and streams every stage over
    `websocket`. Per CORRIX_REAL_DATA_BUILD_PLAN.md Step 7, this is the
    single function both the synthetic scenario path (`_convene_council`,
    below) and the live-factory path
    (`app/api/live_factory_websocket.py`, Step 8) call, so no Council/
    detection/regulatory logic is ever duplicated between them.

    `layout`, `zone_risk`, `worker_positions`, and `time_to_critical` are
    all optional: they drive the evacuation route, risk propagation, the
    Monte Carlo forecast, and the ERO's worker-badge list, none of which
    a caller without scenario-shaped data can necessarily supply yet.
    Omitting one just skips that additive feature for this convening,
    rather than forcing a caller to fabricate scenario-only inputs.
    `layout` defaults to the static demo layout, matching every existing
    call site's behavior unchanged.

    Returns a `ConveningContext` so the caller can later ask the Chair to
    reconsider this same convening (`_reconsider`, below) without
    re-querying the four evidence agents."""
    await websocket.send_json({"type": "council_convening"})

    resolved_layout = layout or load_plant_layout()

    graph = build_council_graph()
    graph_config = {"configurable": {"thread_id": f"live-{id(websocket)}-{time.time()}"}}

    state_after_pause = await asyncio.to_thread(
        graph.invoke,
        {
            "zone_id": zone_id,
            "trigger_reason": trigger_reason,
            "raw_evidence": raw_evidence,
            "scenario_id": scenario_id,
            "memory_context": memory_context,
        },
        graph_config,
    )

    await websocket.send_json(
        {
            "type": "deliberating",
            "council": {
                "processSafetyEngineer": state_after_pause["process_safety_engineer"],
                "permitControlOfficer": state_after_pause["permit_control_officer"],
                "shiftOperations": state_after_pause["shift_operations"],
                "siteSafetyObserver": state_after_pause["site_safety_observer"],
            },
        }
    )

    note: str | None = None
    try:
        msg = await asyncio.wait_for(incoming.get(), timeout=OVERRIDE_WINDOW_SECONDS)
        if msg.get("type") == "override":
            note = msg.get("note")
        else:
            await incoming.put(msg)  # not for us, let the outer loop see it
    except asyncio.TimeoutError:
        pass

    if note:
        await asyncio.to_thread(apply_safety_officer_override, graph, graph_config, note)

    final_state = await asyncio.to_thread(graph.invoke, None, graph_config)
    verdict: CouncilVerdict = final_state["verdict"]

    verdict = await _enrich_and_deliver_verdict(
        websocket,
        verdict,
        trigger_reason=trigger_reason,
        raw_evidence=raw_evidence,
        layout=resolved_layout,
        zone_risk=zone_risk,
        worker_positions=worker_positions,
        time_to_critical=time_to_critical,
        previous_risk_level=None,
    )

    return ConveningContext(
        zone_id=zone_id,
        trigger_reason=trigger_reason,
        scenario_id=scenario_id,
        raw_evidence=raw_evidence,
        memory_context=memory_context,
        layout=resolved_layout,
        zone_risk=zone_risk,
        worker_positions=worker_positions,
        time_to_critical=time_to_critical,
        last_verdict=verdict,
    )


async def _reconsider(
    websocket: WebSocket, context: ConveningContext, note: str
) -> ConveningContext:
    """Chair-only reconsideration: the four agents' original evidence
    (`context.last_verdict.council`) is reused unchanged, since the
    sensor/permit/shift/observation data it describes hasn't moved.
    `chair.synthesize` is a plain function, not a graph node, so this
    calls it directly rather than re-invoking the LangGraph checkpointer.

    `synthesize` never raises (it self-degrades to a fallback verdict on
    any failure), so only `_enrich_and_deliver_verdict` below needs a
    caller-side try/except, matching the convention already used around
    a fresh convening."""
    await websocket.send_json({"type": "reconsidering"})

    previous_risk_level = context.last_verdict.risk_level

    verdict = await asyncio.to_thread(
        synthesize,
        zone_id=context.zone_id,
        trigger_reason=context.trigger_reason,
        evidence=context.last_verdict.council,
        scenario_id=context.scenario_id,
        override_note=note,
        memory_context=context.memory_context,
    )

    verdict = await _enrich_and_deliver_verdict(
        websocket,
        verdict,
        trigger_reason=context.trigger_reason,
        raw_evidence=context.raw_evidence,
        layout=context.layout,
        zone_risk=context.zone_risk,
        worker_positions=context.worker_positions,
        time_to_critical=context.time_to_critical,
        previous_risk_level=previous_risk_level,
    )

    return replace(context, last_verdict=verdict)


async def _convene_council(
    websocket: WebSocket,
    incoming: "asyncio.Queue[dict]",
    playback: ScenarioPlayback,
) -> ConveningContext:
    """Unpacks a scenario `ScenarioPlayback` into the values `_run_council`
    needs, then delegates to it. This is the only place scenario-specific
    shapes (`ScenarioConfig`, `ScenarioOutput`, `PlaybackFrame`) get
    unpacked; `_run_council` itself never sees them."""
    config = playback.config
    out = playback.output
    point = playback.points[playback.trigger_tick_index]
    frame = playback.frames[playback.trigger_frame_index]
    at_time = DEFAULT_START_TIME + timedelta(minutes=frame.minute)
    trigger_reason = playback.trigger_reason or "rule_threshold"

    raw_evidence = {
        "process_safety_engineer": format_process_safety_text(config, point),
        "permit_control_officer": format_permit_text(config, out.permits, at_time),
        "shift_operations": format_shift_text(out.shifts, config.zone, at_time),
        "site_safety_observer": format_site_safety_text(frame.worker_positions, config.zone),
    }

    memory_context = None
    if trigger_reason == "memory_retrieval" and playback.matched_exemplar is not None:
        exemplar = playback.matched_exemplar
        memory_context = (
            f"Historical case: {exemplar.evidence_text} The correct verdict was "
            f"{exemplar.correct_risk_level}. {exemplar.why}"
        )

    time_to_critical_inputs = None
    if config.signals.gas is not None:
        signal_values = [r.concentration for r in out.gas_readings]
        baseline_mean, baseline_std = calibrate_baseline(signal_values)
        time_to_critical_inputs = TimeToCriticalInputs(
            gas_config=config.signals.gas,
            current_value=point.value,
            elapsed_minutes=frame.minute,
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            seed=config.seed,
        )

    return await _run_council(
        websocket,
        incoming,
        zone_id=config.zone,
        trigger_reason=trigger_reason,
        raw_evidence=raw_evidence,
        scenario_id=config.scenario_id,
        memory_context=memory_context,
        zone_risk=frame.zone_risk,
        worker_positions=frame.worker_positions,
        time_to_critical=time_to_critical_inputs,
    )


async def _stream_playback(
    websocket: WebSocket,
    incoming: "asyncio.Queue[dict]",
    playback: ScenarioPlayback,
) -> dict:
    """Streams ticks, convenes the Council at the trigger frame, then
    (unlike before) keeps running past `playback_complete` in an idle
    wait, since a verdict may still be on screen for the officer to
    reconsider. Only returns once a "start"/"open_challenge"/
    "__disconnect__" message truly ends this playback's lifetime; a
    "reconsider" never does."""
    context: ConveningContext | None = None

    async def handle_reconsider(note: str) -> None:
        nonlocal context
        try:
            context = await _reconsider(websocket, context, note)
        except Exception as exc:
            logger.error("Council reconsideration failed unexpectedly: %s", exc)
            await websocket.send_json(
                {
                    "type": "council_error",
                    "message": "The Safety Council could not complete its reconsideration.",
                }
            )

    for i, frame in enumerate(playback.frames):
        try:
            msg = incoming.get_nowait()
            msg_type = msg.get("type")
            if msg_type in ("start", "open_challenge", "__disconnect__"):
                return msg
            elif msg_type == "reconsider":
                if context is not None:
                    await handle_reconsider(msg.get("note", ""))
                # else: no verdict yet for this playback; a stray note has
                # nothing to attach to, so it's dropped, not requeued to
                # attach itself to a later, unrelated verdict.
            else:
                await incoming.put(msg)
        except asyncio.QueueEmpty:
            pass

        await websocket.send_json(
            {
                "type": "tick",
                "minute": frame.minute,
                "zoneRisk": frame.zone_risk,
                "workers": frame.worker_positions,
            }
        )
        await asyncio.sleep(PLAYBACK_FRAME_SECONDS)

        if i == playback.trigger_frame_index:
            try:
                context = await _convene_council(websocket, incoming, playback)
            except Exception as exc:
                # Both evidence-agent and Chair failures already degrade to a
                # fallback (app/council/agents.py, app/council/chair.py)
                # rather than raising; anything that still reaches here is
                # genuinely unexpected, and a live demo crashing outright is
                # a worse outcome than one convening being visibly reported
                # as failed while the rest of the connection keeps working.
                logger.error("Council convening failed unexpectedly: %s", exc)
                await websocket.send_json(
                    {
                        "type": "council_error",
                        "message": "The Safety Council could not complete its deliberation.",
                    }
                )

    await websocket.send_json({"type": "playback_complete"})

    while True:
        msg = await incoming.get()
        msg_type = msg.get("type")
        if msg_type in ("start", "open_challenge", "__disconnect__"):
            return msg
        if msg_type == "reconsider" and context is not None:
            await handle_reconsider(msg.get("note", ""))
        # else: no verdict yet for this playback, or an unrecognized
        # message type -- a harmless no-op.


async def _run_playback(
    websocket: WebSocket, incoming: "asyncio.Queue[dict]", scenario_id: str
) -> dict:
    novelty_model = await asyncio.to_thread(get_cached_novelty_model)
    memory_driver = get_shared_driver()
    playback = await asyncio.to_thread(
        precompute_playback, scenario_id, None, novelty_model, memory_driver
    )
    return await _stream_playback(websocket, incoming, playback)


async def _run_open_challenge(websocket: WebSocket, incoming: "asyncio.Queue[dict]") -> dict:
    """Draws one of the curated Open Challenge combinations at random and
    streams it exactly like an authored scenario. The only difference
    is the trigger is the novelty path, since these are tuned to evade
    rule/threshold by construction (§13.5)."""
    params = random.choice(CURATED_COMBINATIONS)
    seed = random.randint(80000, 89999)
    novelty_model = await asyncio.to_thread(get_cached_novelty_model)
    playback = await asyncio.to_thread(
        precompute_open_challenge_playback, params, seed, novelty_model
    )
    await websocket.send_json({"type": "open_challenge_drawn", "label": params.label})
    return await _stream_playback(websocket, incoming, playback)


async def scenario_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    incoming: "asyncio.Queue[dict]" = asyncio.Queue()

    async def receiver() -> None:
        try:
            while True:
                msg = await websocket.receive_json()
                await incoming.put(msg)
        except WebSocketDisconnect:
            await incoming.put({"type": "__disconnect__"})

    receiver_task = asyncio.create_task(receiver())

    try:
        pending: dict | None = None
        while True:
            msg = pending if pending is not None else await incoming.get()
            pending = None
            msg_type = msg.get("type")
            if msg_type == "__disconnect__":
                break
            if msg_type == "start":
                pending = await _run_playback(websocket, incoming, msg.get("scenario_id", "S1"))
            elif msg_type == "open_challenge":
                pending = await _run_open_challenge(websocket, incoming)
    finally:
        receiver_task.cancel()
