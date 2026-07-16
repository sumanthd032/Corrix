"""Evaluation Harness, per CORRIX_BUILD_PLAN.md Step 8: metrics
computation is tested against synthetic results (fast, deterministic);
`evaluate_scenario` itself is checked against a couple of real scenarios
(makes real Council LLM calls, same as the rest of the Council test
suite already does)."""

from pathlib import Path

from app.detection.novelty_training import fit_novelty_model_from_library
from app.evaluation.harness import ScenarioEvalResult, compute_metrics, evaluate_scenario
from app.simulation.plant_layout import load_plant_layout

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"


def _result(is_positive: bool, triggered: bool, lead_time: float | None = None) -> ScenarioEvalResult:
    return ScenarioEvalResult(
        scenario_id="S1" if is_positive else "N1",
        seed=1,
        memory_split="population",
        zone_id="Z1",
        is_positive=is_positive,
        incident_threshold_minute=80.0,
        baseline_triggered=triggered,
        baseline_trigger_minute=50.0 if triggered else None,
        baseline_lead_time=lead_time,
        pipeline_triggered=triggered,
        pipeline_trigger_reason="rule_threshold" if triggered else None,
        pipeline_trigger_minute=50.0 if triggered else None,
        pipeline_lead_time=lead_time,
        pipeline_verdict_risk_level="HIGH" if triggered else None,
        pipeline_verdict_confidence=0.9 if triggered else None,
    )


def _skipped_result(is_positive: bool) -> ScenarioEvalResult:
    return ScenarioEvalResult(
        scenario_id="S1" if is_positive else "N1",
        seed=2,
        memory_split="population",
        zone_id="Z1",
        is_positive=is_positive,
        incident_threshold_minute=80.0,
        baseline_triggered=True,
        baseline_trigger_minute=50.0,
        baseline_lead_time=30.0,
        pipeline_triggered=False,
        pipeline_trigger_reason=None,
        pipeline_trigger_minute=None,
        pipeline_lead_time=None,
        pipeline_verdict_risk_level=None,
        pipeline_verdict_confidence=None,
        skipped_reason="Council call failed: 429 rate limit",
    )


def test_compute_metrics_perfect_classifier():
    results = [
        _result(True, True, lead_time=20.0),
        _result(True, True, lead_time=10.0),
        _result(False, False),
        _result(False, False),
    ]
    metrics = compute_metrics(results, "pipeline")
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["false_negative_rate"] == 0.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["mean_lead_time_minutes"] == 15.0


def test_compute_metrics_counts_misses_and_false_alarms():
    results = [
        _result(True, True, lead_time=10.0),
        _result(True, False),  # false negative
        _result(False, True),  # false positive
        _result(False, False),
    ]
    metrics = compute_metrics(results, "pipeline")
    assert metrics["true_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["true_negatives"] == 1
    assert metrics["false_negative_rate"] == 0.5
    assert metrics["false_positive_rate"] == 0.5


def test_compute_metrics_excludes_skipped_from_pipeline_but_not_baseline():
    """A scenario where the Council call itself failed (both LLM
    providers' quotas exhausted, say) is genuinely unknown for the
    pipeline, not a confirmed miss — it must not be counted as a false
    negative, but the baseline (no LLM involved) is unaffected."""
    results = [
        _result(True, True, lead_time=10.0),
        _skipped_result(is_positive=True),
    ]
    baseline_metrics = compute_metrics(results, "baseline")
    pipeline_metrics = compute_metrics(results, "pipeline")

    assert baseline_metrics["n_skipped"] == 0
    assert baseline_metrics["n_positive"] == 2
    assert baseline_metrics["true_positives"] == 2

    assert pipeline_metrics["n_skipped"] == 1
    assert pipeline_metrics["n_positive"] == 1
    assert pipeline_metrics["true_positives"] == 1
    assert pipeline_metrics["false_negatives"] == 0


def test_compute_metrics_baseline_vs_pipeline_read_different_fields():
    result = ScenarioEvalResult(
        scenario_id="S1", seed=1, memory_split="population", zone_id="Z1",
        is_positive=True, incident_threshold_minute=80.0,
        baseline_triggered=False, baseline_trigger_minute=None, baseline_lead_time=None,
        pipeline_triggered=True, pipeline_trigger_reason="novelty",
        pipeline_trigger_minute=40.0, pipeline_lead_time=40.0,
        pipeline_verdict_risk_level="HIGH", pipeline_verdict_confidence=0.9,
    )
    baseline_metrics = compute_metrics([result], "baseline")
    pipeline_metrics = compute_metrics([result], "pipeline")
    assert baseline_metrics["recall"] == 0.0
    assert pipeline_metrics["recall"] == 1.0


def test_evaluate_scenario_against_a_real_positive_and_negative():
    model = fit_novelty_model_from_library()
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}

    positive_path = sorted((SCENARIOS_DIR / "s1").glob("*.yaml"))[0]
    positive_result = evaluate_scenario(positive_path, model, zones_by_id)
    assert positive_result.is_positive is True
    assert positive_result.pipeline_triggered is True
    assert positive_result.pipeline_verdict_risk_level in ("HIGH", "CRITICAL")
    assert positive_result.pipeline_lead_time is not None
    assert positive_result.pipeline_lead_time > 0

    negative_path = sorted((SCENARIOS_DIR / "negative").glob("*.yaml"))[0]
    negative_result = evaluate_scenario(negative_path, model, zones_by_id)
    assert negative_result.is_positive is False
    assert negative_result.pipeline_triggered is False


def test_evaluate_scenario_s5_is_a_miss_before_the_memory_loop_exists():
    """S5's whole purpose: neither path fires, no Council convening at
    all, matching a genuine "before the memory loop" false negative."""
    model = fit_novelty_model_from_library()
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
    path = sorted((SCENARIOS_DIR / "s5").glob("*.yaml"))[0]
    result = evaluate_scenario(path, model, zones_by_id)
    assert result.pipeline_triggered is False
    assert result.pipeline_verdict_risk_level is None
