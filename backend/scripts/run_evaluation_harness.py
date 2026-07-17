"""Runs the Evaluation Harness across the full scenario library and
writes real result files, per CORRIX_BUILD_PLAN.md Step 8's Definition
of Done: "Evaluation Report tab shows real, computed numbers (not
placeholders)."

Makes real Council LLM calls (one per scenario where some trigger path
fires; see `app/evaluation/harness.py`'s module docstring for why that
isn't a shortcut). Run from backend/: python scripts/run_evaluation_harness.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.detection.novelty_training import fit_novelty_model_from_library  # noqa: E402
from app.evaluation.harness import compute_metrics, results_to_json, run_harness  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "data" / "evaluation"


def main() -> None:
    print("Fitting novelty detector from population negative controls...")
    model = fit_novelty_model_from_library()

    print("Running the full scenario library through baseline + pipeline...")
    results = run_harness(model)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "full_library_results.json").write_text(results_to_json(results), encoding="utf-8")

    baseline_metrics = compute_metrics(results, "baseline")
    pipeline_metrics = compute_metrics(results, "pipeline")
    (RESULTS_DIR / "full_library_metrics.json").write_text(
        json.dumps({"baseline": baseline_metrics, "pipeline": pipeline_metrics}, indent=2),
        encoding="utf-8",
    )

    print(f"\n{len(results)} scenario instances evaluated.")
    print("\nBaseline (Step 3 rule/threshold only):")
    print(json.dumps(baseline_metrics, indent=2))
    print("\nFull pipeline (rule/threshold + novelty, real Council convening):")
    print(json.dumps(pipeline_metrics, indent=2))
    print(f"\nResults written to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
