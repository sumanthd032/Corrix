"""Confidence calibration, per CORRIX_DATA_METHODOLOGY.md §14.2 — tested
against synthetic results, same pattern as the harness's own metrics
tests."""

from app.evaluation.calibration import compute_calibration
from app.evaluation.harness import ScenarioEvalResult


def _result(memory_split: str, is_positive: bool, triggered: bool, confidence: float | None) -> ScenarioEvalResult:
    return ScenarioEvalResult(
        scenario_id="S1" if is_positive else "N1",
        seed=1,
        memory_split=memory_split,
        zone_id="Z1",
        is_positive=is_positive,
        incident_threshold_minute=80.0,
        baseline_triggered=triggered,
        baseline_trigger_minute=50.0 if triggered else None,
        baseline_lead_time=30.0 if triggered else None,
        pipeline_triggered=triggered,
        pipeline_trigger_reason="rule_threshold" if triggered else None,
        pipeline_trigger_minute=50.0 if triggered else None,
        pipeline_lead_time=30.0 if triggered else None,
        pipeline_verdict_risk_level="HIGH" if triggered else "SAFE",
        pipeline_verdict_confidence=confidence,
    )


def test_compute_calibration_excludes_population_split():
    results = [
        _result("population", True, True, 0.95),
        _result("held_out", True, True, 0.85),
    ]
    bins = compute_calibration(results)
    total_n = sum(b.n for b in bins)
    assert total_n == 1


def test_compute_calibration_excludes_verdicts_without_confidence():
    results = [
        _result("held_out", True, False, None),  # never triggered, no Council call
        _result("held_out", True, True, 0.9),
    ]
    bins = compute_calibration(results)
    total_n = sum(b.n for b in bins)
    assert total_n == 1


def test_compute_calibration_bins_and_scores_accuracy_correctly():
    results = [
        # 0.9-1.0 bin: one correct (true positive), one incorrect (false positive)
        _result("held_out", True, True, 0.95),
        _result("held_out", False, True, 0.92),
        # 0.5-0.6 bin: one correct (true negative)
        _result("held_out", False, False, 0.55),
    ]
    bins = compute_calibration(results)
    high_bin = next(b for b in bins if b.bin_low == 0.9)
    assert high_bin.n == 2
    assert high_bin.empirical_accuracy == 0.5

    low_bin = next(b for b in bins if b.bin_low == 0.5)
    assert low_bin.n == 1
    assert low_bin.empirical_accuracy == 1.0


def test_compute_calibration_covers_full_unit_interval_in_bins():
    bins = compute_calibration([])
    assert len(bins) == 10
    assert bins[0].bin_low == 0.0
    assert bins[-1].bin_high == 1.0
