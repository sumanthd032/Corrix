"""The live scenario WebSocket: streams a precomputed playback at a
watchable rate, and — when the trigger point is reached — actually
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

Server -> client:
  {"type": "tick", "minute": ..., "zoneRisk": {...}, "workers": {...}}
  {"type": "open_challenge_drawn", "label": "..."}   which combination was drawn
  {"type": "council_convening"}
  {"type": "deliberating", "council": {...four evidence texts...}}
  {"type": "verdict", "verdict": {...camelCase CouncilVerdict...}}
  {"type": "playback_complete"}
"""

import asyncio
import time
from datetime import timedelta

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
from app.council.graph import apply_safety_officer_override, build_council_graph
from app.detection.anomaly_scorer import calibrate_baseline
from app.detection.evacuation_routing import find_evacuation_route
from app.detection.novelty_training import fit_novelty_model_from_library
from app.detection.time_to_critical import forecast_time_to_critical
from app.schemas import CouncilVerdict
from app.simulation.open_challenge import CURATED_COMBINATIONS
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import DEFAULT_START_TIME

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
    }


async def _convene_council(
    websocket: WebSocket,
    incoming: "asyncio.Queue[dict]",
    playback: ScenarioPlayback,
    trigger_reason: str = "rule_threshold",
) -> None:
    await websocket.send_json({"type": "council_convening"})

    config = playback.config
    out = playback.output
    point = playback.points[playback.trigger_tick_index]
    frame = playback.frames[playback.trigger_frame_index]
    at_time = DEFAULT_START_TIME + timedelta(minutes=frame.minute)

    raw_evidence = {
        "process_safety_engineer": format_process_safety_text(config, point),
        "permit_control_officer": format_permit_text(config, out.permits, at_time),
        "shift_operations": format_shift_text(out.shifts, config.zone, at_time),
        "site_safety_observer": format_site_safety_text(frame.worker_positions, config.zone),
    }

    graph = build_council_graph()
    graph_config = {"configurable": {"thread_id": f"live-{id(websocket)}-{time.time()}"}}

    state_after_pause = await asyncio.to_thread(
        graph.invoke,
        {
            "zone_id": config.zone,
            "trigger_reason": trigger_reason,
            "raw_evidence": raw_evidence,
            "scenario_id": config.scenario_id,
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
            await incoming.put(msg)  # not for us — let the outer loop see it
    except asyncio.TimeoutError:
        pass

    if note:
        await asyncio.to_thread(apply_safety_officer_override, graph, graph_config, note)

    final_state = await asyncio.to_thread(graph.invoke, None, graph_config)
    verdict: CouncilVerdict = final_state["verdict"]

    if config.signals.gas is not None:
        signal_values = [r.concentration for r in out.gas_readings]
        baseline_mean, baseline_std = calibrate_baseline(signal_values)
        verdict.time_to_critical = await asyncio.to_thread(
            forecast_time_to_critical,
            current_value=point.value,
            elapsed_minutes=frame.minute,
            gas_config=config.signals.gas,
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            seed=config.seed,
        )

    if verdict.risk_level in ("HIGH", "CRITICAL"):
        layout = load_plant_layout()
        route = find_evacuation_route(layout, frame.zone_risk, verdict.zone_id)
        if route is not None:
            verdict.evacuation_route = route.path

    await websocket.send_json({"type": "verdict", "verdict": _verdict_to_camel(verdict)})


async def _stream_playback(
    websocket: WebSocket,
    incoming: "asyncio.Queue[dict]",
    playback: ScenarioPlayback,
    trigger_reason: str = "rule_threshold",
) -> dict | None:
    """Returns a requeued client message if playback was interrupted by
    one (e.g. a new "start"), else None when playback completed."""
    for i, frame in enumerate(playback.frames):
        try:
            msg = incoming.get_nowait()
            if msg.get("type") in ("start", "open_challenge", "__disconnect__"):
                return msg
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
            await _convene_council(websocket, incoming, playback, trigger_reason=trigger_reason)

    await websocket.send_json({"type": "playback_complete"})
    return None


async def _run_playback(
    websocket: WebSocket, incoming: "asyncio.Queue[dict]", scenario_id: str
) -> dict | None:
    playback = await asyncio.to_thread(precompute_playback, scenario_id)
    return await _stream_playback(websocket, incoming, playback, trigger_reason="rule_threshold")


async def _run_open_challenge(websocket: WebSocket, incoming: "asyncio.Queue[dict]") -> dict | None:
    """Draws one of the curated Open Challenge combinations at random and
    streams it exactly like an authored scenario — the only difference
    is the trigger is the novelty path, since these are tuned to evade
    rule/threshold by construction (§13.5)."""
    params = random.choice(CURATED_COMBINATIONS)
    seed = random.randint(80000, 89999)
    novelty_model = await asyncio.to_thread(fit_novelty_model_from_library)
    playback = await asyncio.to_thread(
        precompute_open_challenge_playback, params, seed, novelty_model
    )
    await websocket.send_json({"type": "open_challenge_drawn", "label": params.label})
    return await _stream_playback(websocket, incoming, playback, trigger_reason="novelty")


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
