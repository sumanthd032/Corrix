"""The Open Challenge, per CORRIX_DATA_METHODOLOGY.md §13.5: checks the
trigger mechanism (novelty wins before rule/threshold, for every curated
combination) against the real detection pipeline — no LLM calls needed
for this part, so it runs in every test suite pass regardless of API
quota. The actual Council-convening verdict for each combination is
verified separately by `scripts/validate_open_challenge.py`, which does
make real LLM calls and is run manually before a demo, not on every
test run.
"""

import pytest

from app.detection.novelty_detector import find_first_novelty_trigger
from app.detection.novelty_training import fit_novelty_model_from_library
from app.detection.trigger import find_first_trigger
from app.simulation.open_challenge import CURATED_COMBINATIONS, assemble_open_challenge_config
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import DEFAULT_START_TIME, run_scenario

_ZONES_BY_ID = {z.zone_id: z for z in load_plant_layout().zones}


@pytest.fixture(scope="module")
def novelty_model():
    return fit_novelty_model_from_library()


def test_at_least_five_curated_combinations_exist():
    assert len(CURATED_COMBINATIONS) >= 5


def test_no_combination_reuses_an_authored_scenario_zone():
    """S1-S5's gas-based scenarios live in Z1, Z2, and Z7 — every
    curated Open Challenge combination lives elsewhere, so a real
    trigger here can't be mistaken for a relabeled authored scenario."""
    authored_gas_zones = {"Z1", "Z2", "Z7"}
    for params in CURATED_COMBINATIONS:
        assert params.zone not in authored_gas_zones


@pytest.mark.parametrize("index", range(5))
def test_curated_combination_triggers_via_novelty_not_rule_threshold(novelty_model, index):
    params = CURATED_COMBINATIONS[index]
    config = assemble_open_challenge_config(params, seed=80000 + index)
    out = run_scenario(config)
    zone = _ZONES_BY_ID[config.zone]
    values = [r.concentration for r in out.gas_readings]

    rule_trigger = find_first_trigger(zone, values, out.permits, DEFAULT_START_TIME)
    novelty_index = find_first_novelty_trigger(novelty_model, zone, out)

    assert novelty_index is not None, f"{params.label} never triggered via novelty"
    if rule_trigger is not None:
        assert novelty_index < rule_trigger.index, (
            f"{params.label}: rule/threshold ({rule_trigger.index}) fired before or with "
            f"novelty ({novelty_index}) — this combination doesn't prove the novelty path"
        )


def test_assemble_open_challenge_config_is_deterministic():
    params = CURATED_COMBINATIONS[0]
    config1 = assemble_open_challenge_config(params, seed=99999)
    config2 = assemble_open_challenge_config(params, seed=99999)
    out1 = run_scenario(config1)
    out2 = run_scenario(config2)
    assert [r.concentration for r in out1.gas_readings] == [r.concentration for r in out2.gas_readings]
