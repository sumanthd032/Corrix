"""Precomputes a scenario's playback: per-minute zone risk and worker
occupancy, reusing the real Step 2 simulator and Step 3 detection code
directly (not the MCP protocol layer, which exists for external/agent
access, not internal orchestration) — one implementation of "what
happened when" serves both the offline detection tests and this live
playback stream.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from app.detection.anomaly_scorer import AnomalyPoint, score_series
from app.detection.novelty_detector import NoveltyModel, find_first_novelty_trigger
from app.detection.permit_conflict import active_permits_at, check_permit_conflict
from app.schemas import RiskLevel, ScenarioConfig
from app.simulation.open_challenge import OpenChallengeParams, assemble_open_challenge_config
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    ScenarioOutput,
    find_scenario_config,
    load_scenario_config,
    run_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_ROOT = REPO_ROOT / "data" / "scenarios"

TICK_SECONDS = 5.0
FRAME_SAMPLE_MINUTES = 1.0
FRAME_SAMPLE_TICKS = int(FRAME_SAMPLE_MINUTES * 60 / TICK_SECONDS)


@dataclass
class PlaybackFrame:
    minute: float
    zone_risk: dict[str, RiskLevel]
    worker_positions: dict[str, str] = field(default_factory=dict)
    should_trigger: bool = False
    risk_level: RiskLevel = "SAFE"


@dataclass
class ScenarioPlayback:
    config: ScenarioConfig
    output: ScenarioOutput
    frames: list[PlaybackFrame]
    trigger_frame_index: int | None
    points: list[AnomalyPoint]
    trigger_tick_index: int | None


def find_default_seed(scenario_id: str) -> int:
    """First `population`-split seed authored for this scenario type —
    the default demo instance, not one hand-picked for a specific run."""
    subdir = SCENARIOS_ROOT / scenario_id.lower()
    for path in sorted(subdir.glob("*.yaml")):
        config = load_scenario_config(path)
        if config.memory_split == "population":
            return config.seed
    raise FileNotFoundError(f"no population-split config found for {scenario_id}")


def _occupancy_at(worker_pings, at_time) -> dict[str, str]:
    latest: dict[str, tuple] = {}
    for ping in worker_pings:
        if ping.timestamp > at_time:
            continue
        current = latest.get(ping.badge_id)
        if current is None or ping.timestamp > current[0]:
            latest[ping.badge_id] = (ping.timestamp, ping.zone_id)
    return {badge_id: zone_id for badge_id, (_, zone_id) in latest.items()}


def _signal_values(out: ScenarioOutput) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def _build_playback(
    config: ScenarioConfig,
    out: ScenarioOutput,
    trigger_tick_predicate,
) -> ScenarioPlayback:
    """Shared frame-building loop for both authored scenarios (rule/
    threshold + permit-conflict trigger) and Open Challenge scenarios
    (novelty trigger only, since they're specifically tuned to evade
    rule/threshold) — `trigger_tick_predicate(tick_index) -> bool`
    decides which tick counts as the trigger point either way."""
    layout = load_plant_layout()
    zone_obj = next(z for z in layout.zones if z.zone_id == config.zone)
    all_zone_ids = [z.zone_id for z in layout.zones]

    points: list[AnomalyPoint] = score_series(_signal_values(out))

    frames: list[PlaybackFrame] = []
    trigger_frame_index: int | None = None
    trigger_tick_index: int | None = None
    for tick_index in range(0, len(points), FRAME_SAMPLE_TICKS):
        point = points[tick_index]
        minute = tick_index * TICK_SECONDS / 60.0
        at_time = DEFAULT_START_TIME + timedelta(minutes=minute)

        should_trigger = trigger_tick_predicate(tick_index, point)

        zone_risk: dict[str, RiskLevel] = {zid: "SAFE" for zid in all_zone_ids}
        zone_risk[config.zone] = point.risk_level

        frame = PlaybackFrame(
            minute=minute,
            zone_risk=zone_risk,
            worker_positions=_occupancy_at(out.worker_pings, at_time),
            should_trigger=should_trigger,
            risk_level=point.risk_level,
        )
        frames.append(frame)
        if should_trigger and trigger_frame_index is None:
            trigger_frame_index = len(frames) - 1
            trigger_tick_index = tick_index

    return ScenarioPlayback(
        config=config,
        output=out,
        frames=frames,
        trigger_frame_index=trigger_frame_index,
        points=points,
        trigger_tick_index=trigger_tick_index,
    )


def precompute_playback(scenario_id: str, seed: int | None = None) -> ScenarioPlayback:
    seed = seed if seed is not None else find_default_seed(scenario_id)
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    config = load_scenario_config(path)
    out = run_scenario(config)

    layout = load_plant_layout()
    zone_obj = next(z for z in layout.zones if z.zone_id == config.zone)

    def predicate(tick_index: int, point: AnomalyPoint) -> bool:
        at_time = DEFAULT_START_TIME + timedelta(seconds=TICK_SECONDS * tick_index)
        active_permits = active_permits_at(out.permits, config.zone, at_time)
        conflict = check_permit_conflict(zone_obj, active_permits, point.risk_level)
        return point.risk_level in ("HIGH", "CRITICAL") or conflict.conflict

    return _build_playback(config, out, predicate)


def precompute_open_challenge_playback(
    params: OpenChallengeParams, seed: int, novelty_model: NoveltyModel
) -> ScenarioPlayback:
    """The Open Challenge's live counterpart to `precompute_playback`:
    the scenario is assembled from parameters instead of loaded from the
    authored library, and the trigger is the novelty path specifically
    (§13.5) — these combinations are tuned to never trip rule/threshold,
    by design, so checking for that here would just never fire."""
    config = assemble_open_challenge_config(params, seed)
    out = run_scenario(config)
    layout = load_plant_layout()
    zone_obj = next(z for z in layout.zones if z.zone_id == config.zone)

    novelty_tick_index = find_first_novelty_trigger(novelty_model, zone_obj, out)

    def predicate(tick_index: int, _point: AnomalyPoint) -> bool:
        return novelty_tick_index is not None and tick_index >= novelty_tick_index

    return _build_playback(config, out, predicate)
