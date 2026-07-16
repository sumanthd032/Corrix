"""The live scenario WebSocket: streams a precomputed playback at a
watchable rate, and — when the trigger point is reached — actually
convenes the real Safety Council (Step 4's LangGraph), pausing at the
same interrupt_before=["chair"] checkpoint used for the Safety Officer
Override so a demo user can genuinely intervene, not a simulated pause.

Protocol (JSON messages over one WebSocket connection):

Client -> server:
  {"type": "start", "scenario_id": "S1"}   start/restart playback
  {"type": "override", "note": "..."}      submit an override note
                                            while stage == "deliberating"

Server -> client:
  {"type": "tick", "minute": ..., "zoneRisk": {...}, "workers": {...}}
  {"type": "council_convening"}
  {"type": "deliberating", "council": {...four evidence texts...}}
  {"type": "verdict", "verdict": {...camelCase CouncilVerdict...}}
  {"type": "playback_complete"}
"""

import asyncio
import time
from datetime import timedelta

from fastapi import WebSocket, WebSocketDisconnect

from app.api.live_evidence import (
    format_permit_text,
    format_process_safety_text,
    format_shift_text,
    format_site_safety_text,
)
from app.api.live_scenario import ScenarioPlayback, precompute_playback
from app.council.graph import apply_safety_officer_override, build_council_graph
from app.schemas import CouncilVerdict
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
    }


async def _convene_council(
    websocket: WebSocket, incoming: "asyncio.Queue[dict]", playback: ScenarioPlayback
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
            "trigger_reason": "rule_threshold",
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
    await websocket.send_json({"type": "verdict", "verdict": _verdict_to_camel(verdict)})


async def _run_playback(
    websocket: WebSocket, incoming: "asyncio.Queue[dict]", scenario_id: str
) -> dict | None:
    """Returns a requeued client message if playback was interrupted by
    one (e.g. a new "start"), else None when playback completed."""
    playback = await asyncio.to_thread(precompute_playback, scenario_id)

    for i, frame in enumerate(playback.frames):
        try:
            msg = incoming.get_nowait()
            if msg.get("type") in ("start", "__disconnect__"):
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
            await _convene_council(websocket, incoming, playback)

    await websocket.send_json({"type": "playback_complete"})
    return None


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
            if msg.get("type") == "__disconnect__":
                break
            if msg.get("type") != "start":
                continue
            scenario_id = msg.get("scenario_id", "S1")
            pending = await _run_playback(websocket, incoming, scenario_id)
    finally:
        receiver_task.cancel()
