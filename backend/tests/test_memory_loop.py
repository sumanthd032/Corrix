"""The self-improving memory loop, per CORRIX_PROJECT.md §6.3: real
Neo4j storage and retrieval, checked against the actual scenario
library rather than synthetic vectors.

A real, honest finding shapes several of these tests: no Mahalanobis
distance threshold perfectly separates a genuine S5 near-miss recurrence
from ordinary negative-control noise (see `retrieval_trigger.py`'s
module docstring): four specific negative controls (n01, n09, n10,
n17) sit closer to the stored exemplar than the weaker of the two
genuine held-out matches does. Rather than pick a "safe" negative
control at random and hope it doesn't happen to be one of those four,
the disclosed false positives are tested for explicitly, alongside a
genuinely safe one, so this limitation stays visible rather than
accidentally passing by omission.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from neo4j import GraphDatabase

from app.config import get_settings
from app.detection.anomaly_scorer import score_series
from app.detection.joint_evidence import build_joint_evidence_series
from app.detection.novelty_training import fit_novelty_model_from_library
from app.detection.retrieval_trigger import (
    describe_evidence_snapshot,
    find_first_retrieval_trigger,
)
from app.memory.exemplar_store import ensure_memory_schema, store_exemplar, wipe_all_exemplars
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import DEFAULT_START_TIME, load_scenario_config, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
_ZONES_BY_ID = {z.zone_id: z for z in load_plant_layout().zones}


@pytest.fixture(scope="module")
def driver():
    settings = get_settings()
    d = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    ensure_memory_schema(d)
    yield d
    d.close()


@pytest.fixture(scope="module")
def novelty_model():
    return fit_novelty_model_from_library()


@pytest.fixture
def clean_exemplars(driver):
    wipe_all_exemplars(driver)
    yield
    wipe_all_exemplars(driver)


def _store_s5_population_exemplar(driver, seed_file="seed_90500.yaml"):
    path = SCENARIOS_DIR / "s5" / seed_file
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = _ZONES_BY_ID[config.zone]
    vectors = build_joint_evidence_series(zone, out)

    window_minute = config.ground_truth.compound_risk_window_start_minute
    tick_index = int(window_minute * 60 / 5)
    at_time = DEFAULT_START_TIME + timedelta(minutes=window_minute)
    points = score_series([r.concentration for r in out.gas_readings])
    text = describe_evidence_snapshot(
        config, out, points[tick_index],
        {ping.badge_id: ping.zone_id for ping in out.worker_pings if ping.timestamp <= at_time},
        at_time,
    )
    return store_exemplar(
        driver,
        exemplar_id=f"test-{config.scenario_id}-{config.seed}",
        scenario_id=config.scenario_id,
        seed=config.seed,
        zone_id=config.zone,
        joint_evidence_vector=vectors[tick_index],
        evidence_text=text,
        correct_risk_level="HIGH",
        why="Silent sensor drift matching a historical near-miss pattern",
    )


def test_store_and_retrieve_exemplar_round_trips(driver, clean_exemplars):
    exemplar = _store_s5_population_exemplar(driver)
    from app.memory.exemplar_store import get_all_exemplars

    stored = get_all_exemplars(driver)
    assert len(stored) == 1
    assert stored[0].exemplar_id == exemplar.exemplar_id


def test_held_out_s5_seeds_match_the_stored_population_exemplar(driver, novelty_model, clean_exemplars):
    _store_s5_population_exemplar(driver)
    for seed_file in ["seed_90504.yaml", "seed_90510.yaml"]:
        path = SCENARIOS_DIR / "s5" / seed_file
        config = load_scenario_config(path)
        out = run_scenario(config)
        zone = _ZONES_BY_ID[config.zone]
        result = find_first_retrieval_trigger(driver, novelty_model, config, out, zone)
        assert result is not None, f"{seed_file} never matched the stored exemplar"


def test_a_genuinely_unrelated_negative_control_never_matches(driver, novelty_model, clean_exemplars):
    _store_s5_population_exemplar(driver)
    path = SCENARIOS_DIR / "negative" / "n02.yaml"
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = _ZONES_BY_ID[config.zone]
    result = find_first_retrieval_trigger(driver, novelty_model, config, out, zone)
    assert result is None


def test_disclosed_false_positive_rate_on_specific_negative_controls(driver, novelty_model, clean_exemplars):
    """Not a bug to hide: these four negative controls' own noise
    genuinely sits closer to the stored exemplar than a real match does,
    at the calibrated threshold. Documented and tested explicitly rather
    than silently passing because a random sample happened to avoid them."""
    _store_s5_population_exemplar(driver)
    for stem in ["n01", "n09", "n10", "n17"]:
        path = SCENARIOS_DIR / "negative" / f"{stem}.yaml"
        config = load_scenario_config(path)
        out = run_scenario(config)
        zone = _ZONES_BY_ID[config.zone]
        result = find_first_retrieval_trigger(driver, novelty_model, config, out, zone)
        assert result is not None, f"{stem} was expected to be a known false positive"


def test_no_stored_exemplars_means_no_retrieval_trigger(driver, novelty_model, clean_exemplars):
    path = SCENARIOS_DIR / "s5" / "seed_90504.yaml"
    config = load_scenario_config(path)
    out = run_scenario(config)
    zone = _ZONES_BY_ID[config.zone]
    result = find_first_retrieval_trigger(driver, novelty_model, config, out, zone)
    assert result is None
