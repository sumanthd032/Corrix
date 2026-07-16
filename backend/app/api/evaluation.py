"""Serves the Evaluation Harness's real, precomputed results to the
frontend's Evaluation Report tab. Reads the JSON files
`scripts/run_evaluation_harness.py` writes to `data/evaluation/` —
deliberately not a live recompute-on-every-request: the harness makes
real Council LLM calls across the whole scenario library, expensive and
slow enough that it belongs in an offline batch step, not a page load.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.evaluation.calibration import compute_calibration
from app.evaluation.harness import ScenarioEvalResult

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_PATH = REPO_ROOT / "data" / "evaluation" / "full_library_results.json"
METRICS_PATH = REPO_ROOT / "data" / "evaluation" / "full_library_metrics.json"

router = APIRouter()


def _bin_to_camel(b) -> dict:
    return {
        "binLow": b.bin_low,
        "binHigh": b.bin_high,
        "n": b.n,
        "meanPredictedConfidence": b.mean_predicted_confidence,
        "empiricalAccuracy": b.empirical_accuracy,
    }


def _metrics_to_camel(m: dict) -> dict:
    return {
        "pipeline": m["pipeline"],
        "nSkipped": m["n_skipped"],
        "nPositive": m["n_positive"],
        "nNegative": m["n_negative"],
        "truePositives": m["true_positives"],
        "falseNegatives": m["false_negatives"],
        "falsePositives": m["false_positives"],
        "trueNegatives": m["true_negatives"],
        "precision": m["precision"],
        "recall": m["recall"],
        "falseNegativeRate": m["false_negative_rate"],
        "falsePositiveRate": m["false_positive_rate"],
        "meanLeadTimeMinutes": m["mean_lead_time_minutes"],
    }


@router.get("/api/evaluation/report")
def get_evaluation_report() -> dict:
    if not RESULTS_PATH.exists() or not METRICS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Evaluation Harness has not been run yet — run "
            "backend/scripts/run_evaluation_harness.py first.",
        )

    raw_results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results = [ScenarioEvalResult(**r) for r in raw_results]
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    calibration_bins = compute_calibration(results)

    generated_at = datetime.fromtimestamp(
        RESULTS_PATH.stat().st_mtime, tz=timezone.utc
    ).isoformat()

    return {
        "generatedAt": generated_at,
        "baseline": _metrics_to_camel(metrics["baseline"]),
        "pipeline": _metrics_to_camel(metrics["pipeline"]),
        "calibrationBins": [_bin_to_camel(b) for b in calibration_bins],
        "scenarioResults": [asdict(r) for r in results],
    }
