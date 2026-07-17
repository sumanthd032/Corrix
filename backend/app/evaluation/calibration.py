"""Confidence calibration reporting, per CORRIX_DATA_METHODOLOGY.md
§14.2: buckets every verdict the Evaluation Harness actually produced,
computed only on the held-out subset (§12.5, the same discipline the
self-improving memory loop's before/after comparison uses), by its
stated confidence, and checks whether that confidence means anything
against real ground truth.
"""

from dataclasses import dataclass

from app.evaluation.harness import ScenarioEvalResult

DEFAULT_BIN_WIDTH = 0.1


@dataclass
class CalibrationBin:
    bin_low: float
    bin_high: float
    n: int
    mean_predicted_confidence: float | None
    empirical_accuracy: float | None


def compute_calibration(
    results: list[ScenarioEvalResult], bin_width: float = DEFAULT_BIN_WIDTH
) -> list[CalibrationBin]:
    """A verdict "matches ground truth" exactly when its triggered/not-
    triggered call agrees with whether the scenario is actually positive,
    the same true/false-positive/negative distinction
    `compute_metrics` already uses, not a separate notion of correctness.
    """
    scored = [
        r
        for r in results
        if r.memory_split == "held_out" and r.pipeline_verdict_confidence is not None
    ]

    n_bins = round(1.0 / bin_width)
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        lo = round(i * bin_width, 2)
        hi = round(lo + bin_width, 2)
        in_bin = [
            r
            for r in scored
            if lo <= r.pipeline_verdict_confidence < hi
            or (hi >= 1.0 and r.pipeline_verdict_confidence == 1.0)
        ]
        if not in_bin:
            bins.append(CalibrationBin(lo, hi, 0, None, None))
            continue

        correct = sum(1 for r in in_bin if r.is_positive == r.pipeline_triggered)
        mean_confidence = sum(r.pipeline_verdict_confidence for r in in_bin) / len(in_bin)
        bins.append(
            CalibrationBin(
                bin_low=lo,
                bin_high=hi,
                n=len(in_bin),
                mean_predicted_confidence=mean_confidence,
                empirical_accuracy=correct / len(in_bin),
            )
        )
    return bins
