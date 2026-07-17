"""The self-improving memory loop's before/after proof, per
CORRIX_PROJECT.md §6.3 and CORRIX_DATA_METHODOLOGY.md §12.5: the
false-negative-rate change is only a real generalization result if it's
measured on cases the memory loop never saw. So this script runs the
held-out subset through the harness twice, once before any exemplar
exists, once after population-split misses have been stored, and keeps
both result files rather than just the delta.

Three phases (before / population / after) mean up to ~60 real Council
convenings back to back, each firing up to 4 concurrent evidence-agent
calls plus a Chair call. That reliably bursts past Groq's free-tier TPM
budget partway through a run; left unhandled, a single scenario's
Council call blocking on the Groq SDK's own long retry-after honoring
(observed: 50+ seconds per call) turned one run of this script into a
90-minute wall-clock wait, and an unrelated transient Neo4j hiccup
during exemplar storage once killed the whole process with nothing
saved. Both are now handled: `app/council/llm_client.py` bounds Groq's
own retry and fails over to Gemini quickly instead of stalling, and this
script itself checkpoints after every scenario (`memory_loop_checkpoint.
json` in data/evaluation/) so an interruption, of any kind, resumes
instead of restarting the whole experiment from scratch.

Tuning (optional, via .env, see app/config.py):
  LLM_MAX_CONCURRENT_REQUESTS   default 8
  GROQ_MAX_CONSECUTIVE_429S     default 2
  GROQ_RETRY_BACKOFF_CAP_SECONDS default 10.0
  MEMORY_LOOP_SCENARIO_DELAY_SECONDS  default 0.0, extra pacing between
                                       scenarios if a free-tier budget
                                       still needs more headroom

Run from backend/: python scripts/run_memory_loop_experiment.py
Start over instead of resuming: python scripts/run_memory_loop_experiment.py --fresh
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neo4j import GraphDatabase  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.detection.anomaly_scorer import score_series  # noqa: E402
from app.detection.joint_evidence import build_joint_evidence_series  # noqa: E402
from app.detection.novelty_training import fit_novelty_model_from_library  # noqa: E402
from app.detection.retrieval_trigger import describe_evidence_snapshot  # noqa: E402
from app.evaluation.harness import (  # noqa: E402
    SCENARIOS_DIR,
    ScenarioEvalResult,
    _all_scenario_paths,
    compute_metrics,
    evaluate_scenario,
)
from app.memory.exemplar_store import (  # noqa: E402
    ensure_memory_schema,
    store_exemplar,
    wipe_all_exemplars,
)
from app.simulation.plant_layout import load_plant_layout  # noqa: E402
from app.simulation.scenario_engine import (  # noqa: E402
    DEFAULT_START_TIME,
    load_scenario_config,
    run_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "data" / "evaluation"
CHECKPOINT_PATH = RESULTS_DIR / "memory_loop_checkpoint.json"


def _signal_values(out) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def _scenario_key(scenario_id: str, seed: int) -> str:
    return f"{scenario_id}-{seed}"


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {"phases": {}, "exemplars_stored": []}


def _write_checkpoint(checkpoint: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")


def _failed_result(config, reason: str) -> ScenarioEvalResult:
    """A scenario whose evaluation itself raised (not a Council-call
    failure, `evaluate_scenario` already turns that into `skipped_reason`
    on its own): still record it, so the run's progress count and
    checkpoint stay honest, but exclude it from every metric exactly like
    a Council-call skip does."""
    return ScenarioEvalResult(
        scenario_id=config.scenario_id,
        seed=config.seed,
        memory_split=config.memory_split,
        zone_id=config.zone,
        is_positive=not config.scenario_id.startswith("N"),
        incident_threshold_minute=config.ground_truth.incident_threshold_minute,
        baseline_triggered=False,
        baseline_trigger_minute=None,
        baseline_lead_time=None,
        pipeline_triggered=False,
        pipeline_trigger_reason=None,
        pipeline_trigger_minute=None,
        pipeline_lead_time=None,
        pipeline_verdict_risk_level=None,
        pipeline_verdict_confidence=None,
        skipped_reason=reason,
    )


def _run_phase(
    phase_name: str,
    paths: list[Path],
    novelty_model,
    memory_driver,
    checkpoint: dict,
    scenario_delay: float,
) -> list[ScenarioEvalResult]:
    phase_checkpoint: dict = checkpoint["phases"].setdefault(phase_name, {})
    results: list[ScenarioEvalResult] = []
    total = len(paths)
    n_resumed = n_ok = n_failed = 0
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}

    for i, path in enumerate(paths, start=1):
        config = load_scenario_config(path)
        key = _scenario_key(config.scenario_id, config.seed)

        if key in phase_checkpoint:
            results.append(ScenarioEvalResult(**phase_checkpoint[key]))
            n_resumed += 1
            print(f"[{phase_name}] {key} ({i}/{total}) resumed from checkpoint")
            continue

        try:
            result = evaluate_scenario(path, novelty_model, zones_by_id, memory_driver=memory_driver)
            n_ok += 1
        except Exception as exc:
            result = _failed_result(config, f"scenario evaluation raised: {exc}")
            n_failed += 1

        results.append(result)
        phase_checkpoint[key] = asdict(result)
        _write_checkpoint(checkpoint)

        status = (
            "skipped" if result.skipped_reason
            else "triggered" if result.pipeline_triggered
            else "no-trigger"
        )
        print(
            f"[{phase_name}] {key} ({i}/{total}) -> {status} "
            f"| completed={n_ok} resumed={n_resumed} failed={n_failed}"
        )
        if scenario_delay > 0:
            time.sleep(scenario_delay)

    return results


def _store_population_misses_as_exemplars(driver, population_results, checkpoint: dict) -> int:
    """Every population-split false negative (a genuine positive scenario
    the full pipeline still missed) becomes a stored exemplar: the
    evidence at its ground-truth compound-risk window, tagged with the
    verdict that should have been reached and why. Each store is
    checkpointed by exemplar_id so a Neo4j hiccup partway through doesn't
    lose exemplars already written, and a resumed run doesn't redo them."""
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
    already_stored = set(checkpoint["exemplars_stored"])
    stored = 0
    misses = [r for r in population_results if r.is_positive and not r.pipeline_triggered]
    total = len(misses)

    for i, result in enumerate(misses, start=1):
        exemplar_id = _scenario_key(result.scenario_id, result.seed)
        if exemplar_id in already_stored:
            stored += 1
            print(f"[exemplar] {exemplar_id} ({i}/{total}) already stored, skipping")
            continue
        try:
            path = SCENARIOS_DIR / result.scenario_id.lower() / f"seed_{result.seed}.yaml"
            config = load_scenario_config(path)
            out = run_scenario(config)
            zone = zones_by_id[config.zone]
            vectors = build_joint_evidence_series(zone, out)

            window_minute = config.ground_truth.compound_risk_window_start_minute
            tick_index = min(int(window_minute * 60 / 5), len(vectors) - 1)
            at_time = DEFAULT_START_TIME + timedelta(minutes=window_minute)
            points = score_series(_signal_values(out))
            worker_positions = {
                ping.badge_id: ping.zone_id for ping in out.worker_pings if ping.timestamp <= at_time
            }
            evidence_text = describe_evidence_snapshot(config, out, points[tick_index], worker_positions, at_time)

            store_exemplar(
                driver,
                exemplar_id=exemplar_id,
                scenario_id=config.scenario_id,
                seed=config.seed,
                zone_id=config.zone,
                joint_evidence_vector=vectors[tick_index],
                evidence_text=evidence_text,
                correct_risk_level="HIGH",
                why=(
                    f"A population-split Evaluation Harness run missed this genuine "
                    f"compound risk ({config.name}); neither the rule/threshold trigger "
                    f"nor the novelty detector caught it."
                ),
            )
            already_stored.add(exemplar_id)
            checkpoint["exemplars_stored"] = sorted(already_stored)
            _write_checkpoint(checkpoint)
            stored += 1
            print(f"[exemplar] {exemplar_id} ({i}/{total}) stored")
        except Exception as exc:
            print(f"[exemplar] {exemplar_id} ({i}/{total}) FAILED to store: {exc}")

    return stored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fresh", action="store_true",
        help="Ignore any existing checkpoint and start the experiment over.",
    )
    args = parser.parse_args()

    if args.fresh and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        print(f"--fresh: removed existing checkpoint at {CHECKPOINT_PATH}")

    is_resuming = CHECKPOINT_PATH.exists()
    checkpoint = _load_checkpoint()
    scenario_delay = float(os.environ.get("MEMORY_LOOP_SCENARIO_DELAY_SECONDS", "0"))

    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    ensure_memory_schema(driver)

    print("Fitting novelty detector from population negative controls...")
    novelty_model = fit_novelty_model_from_library()

    if is_resuming:
        print(f"Resuming from checkpoint at {CHECKPOINT_PATH}")
    else:
        print("Wiping any existing exemplars for a clean experiment...")
        wipe_all_exemplars(driver)

    print("\n--- BEFORE: held-out subset, no exemplars stored yet ---")
    before_paths = _all_scenario_paths(SCENARIOS_DIR, memory_split="held_out")
    before_results = _run_phase("before", before_paths, novelty_model, None, checkpoint, scenario_delay)
    before_metrics = compute_metrics(before_results, "pipeline")
    print(json.dumps(before_metrics, indent=2))

    print("\nRunning the population subset once to find real misses to store...")
    population_paths = _all_scenario_paths(SCENARIOS_DIR, memory_split="population")
    population_results = _run_phase("population", population_paths, novelty_model, None, checkpoint, scenario_delay)
    n_stored = _store_population_misses_as_exemplars(driver, population_results, checkpoint)
    print(f"Stored {n_stored} population-split miss(es) as exemplars.")

    print("\n--- AFTER: held-out subset, with the memory-loop retrieval trigger active ---")
    after_results = _run_phase("after", before_paths, novelty_model, driver, checkpoint, scenario_delay)
    after_metrics = compute_metrics(after_results, "pipeline")
    print(json.dumps(after_metrics, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "memory_loop_before_results.json").write_text(
        json.dumps([asdict(r) for r in before_results], indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "memory_loop_after_results.json").write_text(
        json.dumps([asdict(r) for r in after_results], indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "memory_loop_metrics.json").write_text(
        json.dumps(
            {
                "before": before_metrics,
                "after": after_metrics,
                "n_exemplars_stored": n_stored,
                "false_negative_rate_change": (
                    after_metrics["false_negative_rate"] - before_metrics["false_negative_rate"]
                    if before_metrics["false_negative_rate"] is not None
                    and after_metrics["false_negative_rate"] is not None
                    else None
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"\nHeld-out false-negative rate: {before_metrics['false_negative_rate']} -> "
        f"{after_metrics['false_negative_rate']}"
    )
    print(f"Results written to {RESULTS_DIR}")
    CHECKPOINT_PATH.unlink()
    print("Experiment completed successfully; checkpoint cleared.")
    driver.close()


if __name__ == "__main__":
    main()
