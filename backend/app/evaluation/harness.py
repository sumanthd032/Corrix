"""The Evaluation Harness, per CORRIX_BUILD_PLAN.md Step 8: runs the
Step 3 baseline and the full pipeline (rule/threshold trigger OR the
novelty-detector trigger, then a real Council convening) across the
complete scenario library, computing precision/recall/false-negative
rate and lead time against the code-level ground truth
(CORRIX_DATA_METHODOLOGY.md §14.1).

The Council is only actually invoked (a real LLM call) when some trigger
path fires at all — for the ~25% of the library that never triggers by
construction (S5's "before" state, every negative control), that's the
correct behavior, not a shortcut: no trigger means no convening, in the
live system as much as here.
"""

import json
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

from app.api.live_evidence import (
    format_permit_text,
    format_process_safety_text,
    format_shift_text,
    format_site_safety_text,
)
from app.council.graph import run_council
from app.detection.anomaly_scorer import AnomalyPoint, score_series
from app.detection.novelty_detector import NoveltyModel, find_first_novelty_trigger
from app.detection.permit_conflict import active_permits_at
from app.detection.trigger import find_first_trigger
from app.schemas import CouncilVerdict, ScenarioConfig, Zone
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    ScenarioOutput,
    load_scenario_config,
    run_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"
TICK_SECONDS = 5.0


@dataclass
class ScenarioEvalResult:
    scenario_id: str
    seed: int
    memory_split: str
    zone_id: str
    is_positive: bool
    incident_threshold_minute: float

    baseline_triggered: bool
    baseline_trigger_minute: float | None
    baseline_lead_time: float | None

    pipeline_triggered: bool
    pipeline_trigger_reason: str | None  # "rule_threshold" | "novelty"
    pipeline_trigger_minute: float | None
    pipeline_lead_time: float | None
    pipeline_verdict_risk_level: str | None
    pipeline_verdict_confidence: float | None
    # Set when a trigger fired but the real Council call itself failed —
    # both providers' free-tier quotas exhausted mid-run, say. Distinct
    # from "no trigger fired": this scenario's pipeline outcome is
    # genuinely unknown, not a confirmed miss, and compute_metrics
    # excludes it from every count rather than silently scoring it as a
    # false negative.
    skipped_reason: str | None = None


def _worker_positions_at(worker_pings, at_time) -> dict[str, str]:
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


def _convene_at_tick(
    config: ScenarioConfig, out: ScenarioOutput, point: AnomalyPoint, tick_index: int
) -> CouncilVerdict:
    at_time = DEFAULT_START_TIME + timedelta(seconds=TICK_SECONDS * tick_index)
    worker_positions = _worker_positions_at(out.worker_pings, at_time)
    raw_evidence = {
        "process_safety_engineer": format_process_safety_text(config, point),
        "permit_control_officer": format_permit_text(config, out.permits, at_time),
        "shift_operations": format_shift_text(out.shifts, config.zone, at_time),
        "site_safety_observer": format_site_safety_text(worker_positions, config.zone),
    }
    return run_council(
        zone_id=config.zone,
        trigger_reason="rule_threshold",
        raw_evidence=raw_evidence,
        scenario_id=config.scenario_id,
        thread_id=f"harness-{config.scenario_id}-{config.seed}-{tick_index}",
    )


def evaluate_scenario(
    path: Path, novelty_model: NoveltyModel, zones_by_id: dict[str, Zone]
) -> ScenarioEvalResult:
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = zones_by_id[config.zone]
    values = _signal_values(out)
    is_positive = not config.scenario_id.startswith("N")

    baseline_trigger = find_first_trigger(zone, values, out.permits, DEFAULT_START_TIME)
    baseline_minute = baseline_trigger.index * TICK_SECONDS / 60.0 if baseline_trigger else None
    baseline_lead_time = (
        config.ground_truth.incident_threshold_minute - baseline_minute
        if baseline_minute is not None
        else None
    )

    novelty_index = find_first_novelty_trigger(novelty_model, zone, out)
    rule_index = baseline_trigger.index if baseline_trigger else None

    if rule_index is not None and (novelty_index is None or rule_index <= novelty_index):
        pipeline_index, pipeline_reason = rule_index, "rule_threshold"
    elif novelty_index is not None:
        pipeline_index, pipeline_reason = novelty_index, "novelty"
    else:
        pipeline_index, pipeline_reason = None, None

    pipeline_triggered = False
    pipeline_minute = None
    pipeline_lead_time = None
    verdict_risk_level = None
    verdict_confidence = None
    skipped_reason = None

    if pipeline_index is not None:
        points = score_series(values)
        try:
            verdict = _convene_at_tick(config, out, points[pipeline_index], pipeline_index)
        except Exception as exc:  # both LLM providers can raise different real exception types
            skipped_reason = f"Council call failed: {exc}"
        else:
            verdict_risk_level = verdict.risk_level
            verdict_confidence = verdict.confidence
            pipeline_triggered = verdict.risk_level in ("HIGH", "CRITICAL")
            pipeline_minute = pipeline_index * TICK_SECONDS / 60.0
            if pipeline_triggered:
                pipeline_lead_time = config.ground_truth.incident_threshold_minute - pipeline_minute

    return ScenarioEvalResult(
        scenario_id=config.scenario_id,
        seed=config.seed,
        memory_split=config.memory_split,
        zone_id=config.zone,
        is_positive=is_positive,
        incident_threshold_minute=config.ground_truth.incident_threshold_minute,
        baseline_triggered=baseline_trigger is not None,
        baseline_trigger_minute=baseline_minute,
        baseline_lead_time=baseline_lead_time,
        pipeline_triggered=pipeline_triggered,
        pipeline_trigger_reason=pipeline_reason if pipeline_triggered else None,
        pipeline_trigger_minute=pipeline_minute if pipeline_triggered else None,
        pipeline_lead_time=pipeline_lead_time,
        pipeline_verdict_risk_level=verdict_risk_level,
        pipeline_verdict_confidence=verdict_confidence,
        skipped_reason=skipped_reason,
    )


def _all_scenario_paths(scenarios_dir: Path, memory_split: str | None = None) -> list[Path]:
    paths = []
    for subdir in ["s1", "s2", "s3", "s4", "s5", "negative"]:
        for path in sorted((scenarios_dir / subdir).glob("*.yaml")):
            if memory_split is None or load_scenario_config(path).memory_split == memory_split:
                paths.append(path)
    return paths


def run_harness(
    novelty_model: NoveltyModel,
    scenarios_dir: Path = SCENARIOS_DIR,
    memory_split: str | None = None,
) -> list[ScenarioEvalResult]:
    """Runs every config under `scenarios_dir` (optionally filtered to one
    `memory_split`, for the held-out before/after memory-loop comparison)
    through both the baseline and full pipeline."""
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
    return [
        evaluate_scenario(path, novelty_model, zones_by_id)
        for path in _all_scenario_paths(scenarios_dir, memory_split)
    ]


def compute_metrics(results: list[ScenarioEvalResult], pipeline: str) -> dict:
    """`pipeline`: "baseline" or "pipeline" — which of the two triggered/
    lead_time field pairs to score. Scenarios with a `skipped_reason`
    (a real Council-call failure, e.g. both LLM providers' quotas
    exhausted) are excluded from pipeline metrics entirely — genuinely
    unknown isn't the same as a confirmed miss, and folding it in either
    direction would misreport the actual measured rate. The baseline
    never calls an LLM, so it's never affected by this."""
    scored = [r for r in results if pipeline == "baseline" or r.skipped_reason is None]
    n_skipped = len(results) - len(scored)
    positives = [r for r in scored if r.is_positive]
    negatives = [r for r in scored if not r.is_positive]

    def triggered(r: ScenarioEvalResult) -> bool:
        return r.baseline_triggered if pipeline == "baseline" else r.pipeline_triggered

    def lead_time(r: ScenarioEvalResult) -> float | None:
        return r.baseline_lead_time if pipeline == "baseline" else r.pipeline_lead_time

    true_positives = sum(1 for r in positives if triggered(r))
    false_negatives = len(positives) - true_positives
    false_positives = sum(1 for r in negatives if triggered(r))
    true_negatives = len(negatives) - false_positives

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else None
    recall = true_positives / len(positives) if positives else None
    false_negative_rate = false_negatives / len(positives) if positives else None
    false_positive_rate = false_positives / len(negatives) if negatives else None

    lead_times = [lead_time(r) for r in positives if triggered(r) and lead_time(r) is not None]
    mean_lead_time = sum(lead_times) / len(lead_times) if lead_times else None

    return {
        "pipeline": pipeline,
        "n_skipped": n_skipped,
        "n_positive": len(positives),
        "n_negative": len(negatives),
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "precision": precision,
        "recall": recall,
        "false_negative_rate": false_negative_rate,
        "false_positive_rate": false_positive_rate,
        "mean_lead_time_minutes": mean_lead_time,
    }


def results_to_json(results: list[ScenarioEvalResult]) -> str:
    return json.dumps([asdict(r) for r in results], indent=2)
