"""Rolling z-score anomaly scorer: correctness and Step 3's Definition of
Done, checked against the actual scenario library, not synthetic
examples alone — a first naive implementation passed unit tests but had
a 100% false-positive rate on real negative controls, so this suite
checks the whole library explicitly."""

from pathlib import Path

import pytest

from app.detection.anomaly_scorer import classify_z_score, max_risk_level, score_series
from app.simulation.scenario_engine import load_scenario_config, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
POSITIVE_DIRS = ["s1", "s2", "s3", "s4"]


def _signal_values(out) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def test_classify_z_score_thresholds():
    assert classify_z_score(0.5) == "SAFE"
    assert classify_z_score(6.5) == "CAUTION"
    assert classify_z_score(-6.5) == "CAUTION"
    assert classify_z_score(25) == "HIGH"
    assert classify_z_score(60) == "CRITICAL"


def test_flat_signal_scores_safe():
    points = score_series([2.0] * 200)
    assert all(p.risk_level == "SAFE" for p in points)


@pytest.mark.parametrize(
    "path",
    [p for d in POSITIVE_DIRS for p in sorted((SCENARIOS_DIR / d).glob("*.yaml"))],
    ids=lambda p: p.stem,
)
def test_every_positive_scenario_reaches_high_or_critical(path):
    """Step 3's Definition of Done: running S1-S4 through the anomaly
    scorer alone produces a HIGH/CRITICAL flag at some point in each run."""
    out = run_scenario(load_scenario_config(path))
    points = score_series(_signal_values(out))
    assert max_risk_level(points) in ("HIGH", "CRITICAL")


@pytest.mark.parametrize(
    "path", sorted((SCENARIOS_DIR / "negative").glob("*.yaml")), ids=lambda p: p.stem
)
def test_negative_controls_never_flag_high_or_critical(path):
    out = run_scenario(load_scenario_config(path))
    points = score_series(_signal_values(out))
    assert max_risk_level(points) not in ("HIGH", "CRITICAL")
