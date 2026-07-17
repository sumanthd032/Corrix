"""Precomputes a scenario's playback: per-minute zone risk and worker
occupancy, reusing the real Step 2 simulator and Step 3 detection code
directly (not the MCP protocol layer, which exists for external/agent
access, not internal orchestration). One implementation of "what
happened when" serves both the offline detection tests and this live
playback stream.

The live trigger check mirrors the Evaluation Harness's own three-path
logic (`app/evaluation/harness.py`): rule/threshold, novelty, and, when
a memory driver is available, retrieval-similarity, picking whichever
fires earliest. This matters beyond symmetry with the harness: S5 is
deliberately built to never trip rule/threshold, so without the
novelty and retrieval paths wired in here too, selecting S5 live would
stream to the end with no trigger at all, no matter how long the
memory loop has been running.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from neo4j import Driver

from app.detection.anomaly_scorer import AnomalyPoint, score_series
from app.detection.novelty_detector import NoveltyModel, find_first_novelty_trigger
from app.detection.retrieval_trigger import RetrievalTriggerResult, find_first_retrieval_trigger
from app.detection.trigger import find_first_trigger
from app.memory.exemplar_store import MemoryExemplar
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
    trigger_reason: str | None = None
    matched_exemplar: MemoryExemplar | None = None


def find_default_seed(scenario_id: str) -> int:
    """First `population`-split seed authored for this scenario type,
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
    pipeline_tick_index: int | None,
    trigger_reason: str | None,
    matched_exemplar: MemoryExemplar | None = None,
) -> ScenarioPlayback:
    """Shared frame-building loop. `pipeline_tick_index` is the single,
    already-decided trigger point (whichever of rule/threshold, novelty,
    or retrieval-similarity fired earliest). Every frame at or past it
    is marked `should_trigger`, matching the same "first tick past the
    trigger" semantics the Open Challenge path already used."""
    layout = load_plant_layout()
    all_zone_ids = [z.zone_id for z in layout.zones]

    points: list[AnomalyPoint] = score_series(_signal_values(out))

    frames: list[PlaybackFrame] = []
    trigger_frame_index: int | None = None
    trigger_tick_index: int | None = None
    for tick_index in range(0, len(points), FRAME_SAMPLE_TICKS):
        point = points[tick_index]
        minute = tick_index * TICK_SECONDS / 60.0
        at_time = DEFAULT_START_TIME + timedelta(minutes=minute)

        should_trigger = pipeline_tick_index is not None and tick_index >= pipeline_tick_index

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
        trigger_reason=trigger_reason if trigger_frame_index is not None else None,
        matched_exemplar=matched_exemplar if trigger_frame_index is not None else None,
    )


def precompute_playback(
    scenario_id: str,
    seed: int | None = None,
    novelty_model: NoveltyModel | None = None,
    memory_driver: Driver | None = None,
) -> ScenarioPlayback:
    """`novelty_model`/`memory_driver`: when supplied, the novelty and
    retrieval-similarity paths are also checked, and the earliest of all
    three candidates wins, the same three-path logic
    `app/evaluation/harness.py` already uses, needed live so a scenario
    like S5 (which never trips rule/threshold by construction) can still
    convene the Council when it should."""
    seed = seed if seed is not None else find_default_seed(scenario_id)
    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    config = load_scenario_config(path)
    out = run_scenario(config)

    layout = load_plant_layout()
    zone_obj = next(z for z in layout.zones if z.zone_id == config.zone)
    values = _signal_values(out)

    rule_trigger = find_first_trigger(zone_obj, values, out.permits, DEFAULT_START_TIME)
    rule_index = rule_trigger.index if rule_trigger else None

    novelty_index = None
    if novelty_model is not None:
        novelty_index = find_first_novelty_trigger(novelty_model, zone_obj, out)

    retrieval_result: RetrievalTriggerResult | None = None
    if novelty_model is not None and memory_driver is not None:
        retrieval_result = find_first_retrieval_trigger(memory_driver, novelty_model, config, out, zone_obj)
    retrieval_index = retrieval_result.tick_index if retrieval_result else None

    candidates = [
        (rule_index, "rule_threshold", None),
        (novelty_index, "novelty", None),
        (retrieval_index, "memory_retrieval", retrieval_result.matched_exemplar if retrieval_result else None),
    ]
    real_candidates = [(idx, reason, exemplar) for idx, reason, exemplar in candidates if idx is not None]

    if real_candidates:
        pipeline_index, pipeline_reason, matched_exemplar = min(real_candidates, key=lambda c: c[0])
    else:
        pipeline_index, pipeline_reason, matched_exemplar = None, None, None

    return _build_playback(config, out, pipeline_index, pipeline_reason, matched_exemplar)


def precompute_open_challenge_playback(
    params: OpenChallengeParams, seed: int, novelty_model: NoveltyModel
) -> ScenarioPlayback:
    """The Open Challenge's live counterpart to `precompute_playback`:
    the scenario is assembled from parameters instead of loaded from the
    authored library, and the trigger is the novelty path specifically
    (§13.5). These combinations are tuned to never trip rule/threshold
    by design, so checking for that here would just never fire."""
    config = assemble_open_challenge_config(params, seed)
    out = run_scenario(config)
    layout = load_plant_layout()
    zone_obj = next(z for z in layout.zones if z.zone_id == config.zone)

    novelty_tick_index = find_first_novelty_trigger(novelty_model, zone_obj, out)

    return _build_playback(config, out, novelty_tick_index, "novelty")
