"""Joint-evidence novelty detector, per CORRIX_DATA_METHODOLOGY.md §13:
fit on population-split negative controls, checked against the real
scenario library rather than synthetic examples, same discipline as
Step 3's anomaly-scorer calibration.
"""

from pathlib import Path

import pytest

from app.detection.joint_evidence import build_joint_evidence_series
from app.detection.novelty_detector import find_first_novelty_trigger, fit_novelty_model
from app.detection.novelty_training import (
    collect_population_negative_control_vectors,
    fit_novelty_model_from_library,
)
from app.detection.trigger import find_first_trigger
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import DEFAULT_START_TIME, load_scenario_config, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
_ZONES_BY_ID = {z.zone_id: z for z in load_plant_layout().zones}


@pytest.fixture(scope="module")
def model():
    return fit_novelty_model_from_library()


def test_training_set_is_nonempty_and_fixed_length():
    vectors = collect_population_negative_control_vectors()
    assert len(vectors) > 1000
    assert all(len(v) == 5 for v in vectors)


@pytest.mark.parametrize(
    "scenario_dir", ["s1", "s2", "s3", "s4"], ids=lambda d: d
)
def test_every_known_positive_scenario_is_flagged_novel(model, scenario_dir):
    """The novelty path should independently agree with the rule/threshold
    path on S1-S4. This is not the point of the feature (they're already caught),
    but a sanity check that the model responds to real compound risk."""
    for path in sorted((SCENARIOS_DIR / scenario_dir).glob("*.yaml")):
        config = load_scenario_config(path)
        out = run_scenario(config)
        zone = _ZONES_BY_ID[config.zone]
        idx = find_first_novelty_trigger(model, zone, out)
        assert idx is not None, f"{path.stem} was never flagged novel"


@pytest.mark.parametrize("path", sorted((SCENARIOS_DIR / "s5").glob("*.yaml")), ids=lambda p: p.stem)
def test_s5_is_a_genuine_miss_for_both_independent_trigger_paths(model, path):
    """S5's entire purpose (§12.3): unsolvable by the rule/threshold path
    *and* the novelty path, by construction, for every seed actually
    shipped. Only the third path (retrieval-similarity, once the memory
    loop exists) should ever catch it."""
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = _ZONES_BY_ID[config.zone]
    values = [r.concentration for r in out.gas_readings]

    rule_trigger = find_first_trigger(zone, values, out.permits, DEFAULT_START_TIME)
    novelty_trigger = find_first_novelty_trigger(model, zone, out)

    assert rule_trigger is None, f"{path.stem} tripped the rule/threshold path"
    assert novelty_trigger is None, f"{path.stem} tripped the novelty path"


def test_fit_novelty_model_calibrates_threshold_from_training_percentile():
    vectors = collect_population_negative_control_vectors()
    model_99 = fit_novelty_model(vectors, percentile=99.0)
    model_50 = fit_novelty_model(vectors, percentile=50.0)
    assert model_99.threshold > model_50.threshold


def test_build_joint_evidence_series_length_matches_signal_series():
    path = next((SCENARIOS_DIR / "s3").glob("*.yaml"))
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = _ZONES_BY_ID[config.zone]
    vectors = build_joint_evidence_series(zone, out)
    assert len(vectors) == len(out.gas_readings)
