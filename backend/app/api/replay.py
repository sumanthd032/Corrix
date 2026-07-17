"""Serves precomputed Counterfactual Replay timelines to the frontend's
scrubber UI. A REST fetch, not a WebSocket stream: scrubbing needs
random access to any minute instantly, which fits a single fully-
computed array far better than a live-paced stream (`websocket.py`
already owns that pattern for the actual live playback).
"""

from fastapi import APIRouter, HTTPException

from app.api.counterfactual import build_replay_timeline

router = APIRouter()

_VALID_SCENARIOS = {"S1", "S2", "S3", "S4"}


@router.get("/api/replay/{scenario_id}")
def get_replay_timeline(scenario_id: str) -> dict:
    scenario_id = scenario_id.upper()
    if scenario_id not in _VALID_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"No replay available for {scenario_id}")

    timeline = build_replay_timeline(scenario_id)
    return {
        "scenarioId": timeline.scenario_id,
        "seed": timeline.seed,
        "zoneId": timeline.zone_id,
        "corrixFirstEscalationMinute": timeline.corrix_first_escalation_minute,
        "legacyFirstEscalationMinute": timeline.legacy_first_escalation_minute,
        "frames": [
            {
                "minute": f.minute,
                "corrixRiskLevel": f.corrix_risk_level,
                "legacyRiskLevel": f.legacy_risk_level,
            }
            for f in timeline.frames
        ],
    }
