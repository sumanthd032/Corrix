"""The authored scenario library (S1-S4, 5 seeds each, plus matched
negative controls): Step 2's Definition of Done, checked across every
file, not just one example.
"""

from pathlib import Path

import pytest

from app.simulation.scenario_engine import load_scenario_config, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

POSITIVE_DIRS = ["s1", "s2", "s3", "s4"]
POSITIVE_PATHS = sorted(
    p for d in POSITIVE_DIRS for p in (SCENARIOS_DIR / d).glob("*.yaml")
)
NEGATIVE_PATHS = sorted((SCENARIOS_DIR / "negative").glob("*.yaml"))


def test_five_seed_variants_per_positive_scenario_type():
    for d in POSITIVE_DIRS:
        files = list((SCENARIOS_DIR / d).glob("*.yaml"))
        assert len(files) == 5, f"{d} should have 5 seed variants, found {len(files)}"


def test_negative_controls_match_positive_volume():
    assert len(NEGATIVE_PATHS) == len(POSITIVE_PATHS) == 20


@pytest.mark.parametrize("path", POSITIVE_PATHS + NEGATIVE_PATHS, ids=lambda p: p.stem)
def test_every_config_loads_and_runs_deterministically(path):
    config = load_scenario_config(path)
    out1 = run_scenario(config)
    out2 = run_scenario(config)
    assert [r.compliance_score for r in out1.compliance_readings] == [
        r.compliance_score for r in out2.compliance_readings
    ]
    assert [r.concentration for r in out1.gas_readings] == [
        r.concentration for r in out2.gas_readings
    ]
    assert [p.permit_id for p in out1.permits] == [p.permit_id for p in out2.permits]


@pytest.mark.parametrize("path", POSITIVE_PATHS, ids=lambda p: p.stem)
def test_every_positive_scenario_carries_a_valid_memory_split(path):
    config = load_scenario_config(path)
    assert config.memory_split in ("population", "held_out")


@pytest.mark.parametrize("path", NEGATIVE_PATHS, ids=lambda p: p.stem)
def test_negative_controls_have_baseline_signal_but_no_source_term(path):
    """Negative controls run the identical gas generator with S(t)=0 (a=0),
    per §12.4 — baseline + noise only, not an empty stream. No compliance
    signal, since that's tied to a lifting/casting permit context negative
    controls don't have."""
    config = load_scenario_config(path)
    assert config.signals.gas is not None
    assert config.signals.gas.a == 0.0
    assert config.signals.compliance is None
    out = run_scenario(config)
    assert len(out.gas_readings) > 0
    assert out.compliance_readings == []
    # background traffic still exists — a negative control isn't an empty plant
    assert len(out.permits) > 0
    assert len(out.worker_pings) > 0


@pytest.mark.parametrize("path", (SCENARIOS_DIR / "s1").glob("*.yaml"), ids=lambda p: p.stem)
def test_s1_worker_shows_up_in_scripted_permit_zone(path):
    out = run_scenario(load_scenario_config(path))
    scripted_permit = next(p for p in out.permits if p.permit_id.startswith("P-SCRIPT"))
    scripted_ping = next(e for e in out.worker_pings if e.badge_id == "W-0142")
    assert scripted_ping.zone_id == scripted_permit.zone_id
    assert scripted_permit.start_time <= scripted_ping.timestamp <= scripted_permit.end_time


def test_s3_gas_signal_trends_upward_matching_ramp_shape():
    path = next((SCENARIOS_DIR / "s3").glob("*.yaml"))
    out = run_scenario(load_scenario_config(path))
    concentrations = [r.concentration for r in out.gas_readings]
    early_avg = sum(concentrations[:20]) / 20
    late_avg = sum(concentrations[-20:]) / 20
    assert late_avg > early_avg


def test_s4_gas_signal_peaks_then_decays_matching_step_decay_shape():
    path = next((SCENARIOS_DIR / "s4").glob("*.yaml"))
    out = run_scenario(load_scenario_config(path))
    concentrations = [r.concentration for r in out.gas_readings]
    peak = max(concentrations)
    end_avg = sum(concentrations[-20:]) / 20
    assert peak > concentrations[0]
    assert end_avg < peak


def test_s2_gas_signal_has_plateau_then_secondary_rise():
    path = next((SCENARIOS_DIR / "s2").glob("*.yaml"))
    out = run_scenario(load_scenario_config(path))
    dt_per_min = 60 / 5
    mid_plateau = out.gas_readings[int(55 * dt_per_min)].concentration
    final = out.gas_readings[-1].concentration
    assert final > mid_plateau
