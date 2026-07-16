"""Counterfactual Replay, per CORRIX_BUILD_PLAN.md Step 8: a deterministic
"legacy/siloed" path alongside the live Corrix path, over the same
scenario timeline, so a synchronized scrubber can show exactly what a
traditional single-signal monitoring system would have shown instead.

The legacy path is real, not a strawman: it's the same z-score anomaly
scorer Step 3 already validated (`classify_z_score`), applied with no
awareness of permit state, worker presence, or shift timing at all —
precisely what a siloed sensor-only system looks like. The Corrix path
is the same trigger condition the live system actually uses (anomaly OR
permit conflict). Both are computed from the identical simulated data;
the only difference is how much of it each "system" is allowed to see.
"""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from app.detection.anomaly_scorer import AnomalyPoint, classify_z_score, score_series
from app.detection.permit_conflict import active_permits_at, check_permit_conflict
from app.schemas import RiskLevel, Zone
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    find_scenario_config,
    load_scenario_config,
    run_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_ROOT = REPO_ROOT / "data" / "scenarios"

TICK_SECONDS = 5.0
FRAME_SAMPLE_TICKS = int(60 / TICK_SECONDS)


@dataclass
class ReplayFrame:
    minute: float
    corrix_risk_level: RiskLevel
    legacy_risk_level: RiskLevel


@dataclass
class ReplayTimeline:
    scenario_id: str
    seed: int
    zone_id: str
    frames: list[ReplayFrame]
    corrix_first_escalation_minute: float | None
    legacy_first_escalation_minute: float | None


def _signal_values(out) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def _first_escalation_minute(frames: list[ReplayFrame], attr: str) -> float | None:
    for frame in frames:
        if getattr(frame, attr) in ("HIGH", "CRITICAL"):
            return frame.minute
    return None


def build_replay_timeline(scenario_id: str, seed: int | None = None) -> ReplayTimeline:
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
    if seed is None:
        # first available seed for this scenario type, any split — the
        # replay is illustrative, not an evaluation-harness measurement
        subdir = SCENARIOS_ROOT / scenario_id.lower()
        path = sorted(subdir.glob("*.yaml"))[0]
    else:
        path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone: Zone = zones_by_id[config.zone]

    values = _signal_values(out)
    points: list[AnomalyPoint] = score_series(values)

    frames: list[ReplayFrame] = []
    for tick_index in range(0, len(points), FRAME_SAMPLE_TICKS):
        point = points[tick_index]
        minute = tick_index * TICK_SECONDS / 60.0
        at_time = DEFAULT_START_TIME + timedelta(minutes=minute)

        legacy_risk_level = classify_z_score(point.z_score)

        active_permits = active_permits_at(out.permits, config.zone, at_time)
        conflict = check_permit_conflict(zone, active_permits, point.risk_level)
        # A permit conflict is a real compound escalation even when the
        # raw anomaly alone is only SAFE/CAUTION — the same OR-condition
        # `trigger.py` already uses, translated into a displayable risk
        # level rather than a bare trigger boolean. Shown as HIGH (a
        # conflict is a real, actionable escalation), not CRITICAL,
        # since only the raw anomaly score reaching CRITICAL should ever
        # display as CRITICAL.
        corrix_risk_level: RiskLevel = point.risk_level
        if conflict.conflict and point.risk_level not in ("HIGH", "CRITICAL"):
            corrix_risk_level = "HIGH"

        frames.append(
            ReplayFrame(
                minute=minute,
                corrix_risk_level=corrix_risk_level,
                legacy_risk_level=legacy_risk_level,
            )
        )

    return ReplayTimeline(
        scenario_id=config.scenario_id,
        seed=config.seed,
        zone_id=config.zone,
        frames=frames,
        corrix_first_escalation_minute=_first_escalation_minute(frames, "corrix_risk_level"),
        legacy_first_escalation_minute=_first_escalation_minute(frames, "legacy_risk_level"),
    )
