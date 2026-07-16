"""The self-improving memory loop's before/after proof, per
CORRIX_PROJECT.md §6.3 and CORRIX_DATA_METHODOLOGY.md §12.5: the
false-negative-rate change is only a real generalization result if it's
measured on cases the memory loop never saw — so this script runs the
held-out subset through the harness twice, once before any exemplar
exists, once after population-split misses have been stored, and keeps
both result files rather than just the delta.

Run from backend/: python scripts/run_memory_loop_experiment.py
"""

import json
import sys
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
    compute_metrics,
    results_to_json,
    run_harness,
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


def _store_population_misses_as_exemplars(driver, population_results, zones_by_id) -> int:
    """Every population-split false negative (a genuine positive
    scenario the full pipeline still missed) becomes a stored exemplar —
    the evidence at its ground-truth compound-risk window, tagged with
    the verdict that should have been reached and why."""
    stored = 0
    for result in population_results:
        if not (result.is_positive and not result.pipeline_triggered):
            continue
        path = SCENARIOS_DIR / result.scenario_id.lower() / f"seed_{result.seed}.yaml"
        config = load_scenario_config(path)
        out = run_scenario(config)
        zone = zones_by_id[config.zone]
        vectors = build_joint_evidence_series(zone, out)

        window_minute = config.ground_truth.compound_risk_window_start_minute
        tick_index = min(int(window_minute * 60 / 5), len(vectors) - 1)
        at_time = DEFAULT_START_TIME + timedelta(minutes=window_minute)
        points = score_series([r.concentration for r in out.gas_readings])
        worker_positions = {
            ping.badge_id: ping.zone_id for ping in out.worker_pings if ping.timestamp <= at_time
        }
        evidence_text = describe_evidence_snapshot(config, out, points[tick_index], worker_positions, at_time)

        store_exemplar(
            driver,
            exemplar_id=f"{config.scenario_id}-{config.seed}",
            scenario_id=config.scenario_id,
            seed=config.seed,
            zone_id=config.zone,
            joint_evidence_vector=vectors[tick_index],
            evidence_text=evidence_text,
            correct_risk_level="HIGH",
            why=(
                f"A population-split Evaluation Harness run missed this genuine "
                f"compound risk ({config.name}) — neither the rule/threshold trigger "
                f"nor the novelty detector caught it."
            ),
        )
        stored += 1
    return stored


def main() -> None:
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    ensure_memory_schema(driver)
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}

    print("Fitting novelty detector from population negative controls...")
    novelty_model = fit_novelty_model_from_library()

    print("Wiping any existing exemplars for a clean experiment...")
    wipe_all_exemplars(driver)

    print("\n--- BEFORE: held-out subset, no exemplars stored yet ---")
    before_results = run_harness(novelty_model, memory_split="held_out")
    before_metrics = compute_metrics(before_results, "pipeline")
    print(json.dumps(before_metrics, indent=2))

    print("\nRunning the population subset once to find real misses to store...")
    population_results = run_harness(novelty_model, memory_split="population")
    n_stored = _store_population_misses_as_exemplars(driver, population_results, zones_by_id)
    print(f"Stored {n_stored} population-split miss(es) as exemplars.")

    print("\n--- AFTER: held-out subset, with the memory-loop retrieval trigger active ---")
    after_results = run_harness(novelty_model, memory_split="held_out", memory_driver=driver)
    after_metrics = compute_metrics(after_results, "pipeline")
    print(json.dumps(after_metrics, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "memory_loop_before_results.json").write_text(
        results_to_json(before_results), encoding="utf-8"
    )
    (RESULTS_DIR / "memory_loop_after_results.json").write_text(
        results_to_json(after_results), encoding="utf-8"
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
    driver.close()


if __name__ == "__main__":
    main()
