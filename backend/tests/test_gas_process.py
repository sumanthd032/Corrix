"""Gas OU-process simulator: determinism and shape-correctness checks,
per CORRIX_DATA_METHODOLOGY.md §3 and the Step 2 Definition of Done."""

import numpy as np

from app.schemas.scenario import GasSignalConfig
from app.simulation.gas_process import (
    ramp_source,
    run_gas_process,
    step,
    step_decay_source,
)


def test_step_is_deterministic_given_same_rng_state():
    rng_a = np.random.default_rng(7)
    rng_b = np.random.default_rng(7)
    c_a = step(2.0, k=0.1, C_baseline=2.0, S_t=0.0, sigma=0.05, dt=1 / 12, rng=rng_a)
    c_b = step(2.0, k=0.1, C_baseline=2.0, S_t=0.0, sigma=0.05, dt=1 / 12, rng=rng_b)
    assert c_a == c_b


def test_step_concentration_never_negative():
    rng = np.random.default_rng(1)
    c = 0.0
    for _ in range(1000):
        c = step(c, k=0.5, C_baseline=0.0, S_t=0.0, sigma=5.0, dt=1 / 12, rng=rng)
        assert c >= 0.0


def test_ramp_source_shape():
    assert ramp_source(5, a=10, t0=10, t_rise=20) == 0.0
    assert ramp_source(20, a=10, t0=10, t_rise=20) == 5.0
    assert ramp_source(40, a=10, t0=10, t_rise=20) == 10.0


def test_step_decay_source_shape():
    assert step_decay_source(5, a=10, t0=10, tau=5) == 0.0
    peak = step_decay_source(10, a=10, t0=10, tau=5)
    later = step_decay_source(20, a=10, t0=10, tau=5)
    assert peak == 10.0
    assert later < peak


def test_run_gas_process_is_deterministic():
    cfg = GasSignalConfig(
        gas_type="LEL", C_baseline=2.0, k=0.08, sigma=0.1,
        source_shape="ramp", a=0.08 * (15 - 2), t0_minute=10, t_rise_minutes=60,
    )
    r1 = run_gas_process(cfg, "Z2", duration_minutes=90, seed=42)
    r2 = run_gas_process(cfg, "Z2", duration_minutes=90, seed=42)
    assert [x.concentration for x in r1] == [x.concentration for x in r2]


def test_run_gas_process_different_seed_diverges():
    cfg = GasSignalConfig(
        gas_type="LEL", C_baseline=2.0, k=0.08, sigma=0.1,
        source_shape="ramp", a=0.08 * (15 - 2), t0_minute=10, t_rise_minutes=60,
    )
    r1 = run_gas_process(cfg, "Z2", duration_minutes=90, seed=1)
    r2 = run_gas_process(cfg, "Z2", duration_minutes=90, seed=2)
    assert [x.concentration for x in r1] != [x.concentration for x in r2]


def test_ramp_shape_rises_toward_target():
    target = 15.0
    cfg = GasSignalConfig(
        gas_type="LEL", C_baseline=2.0, k=0.08, sigma=0.05,
        source_shape="ramp", a=0.08 * (target - 2.0), t0_minute=10, t_rise_minutes=60,
    )
    r = run_gas_process(cfg, "Z2", duration_minutes=90, seed=3)
    early = r[0].concentration
    late_avg = sum(x.concentration for x in r[-20:]) / 20
    assert early < late_avg
    assert abs(late_avg - target) < 2.0


def test_step_decay_shape_peaks_then_decays():
    cfg = GasSignalConfig(
        gas_type="LEL", C_baseline=2.0, k=0.15, sigma=0.05,
        source_shape="step_decay", a=3.0, t0_minute=10, tau_minutes=4,
    )
    r = run_gas_process(cfg, "Z2", duration_minutes=60, seed=4)
    values = [x.concentration for x in r]
    peak = max(values)
    peak_idx = values.index(peak)
    end_avg = sum(values[-20:]) / 20
    assert peak > values[0]
    assert end_avg < peak
    # peak should occur reasonably close to the injection, not at the very end
    assert peak_idx < len(values) - 100


def test_ramp_with_plateau_shape_has_two_stages():
    cfg = GasSignalConfig(
        gas_type="LEL", C_baseline=2.0, k=0.1, sigma=0.03,
        source_shape="ramp_with_plateau", a=0.1 * (8 - 2), t0_minute=5, t_rise_minutes=25,
        C_plateau=8.0, secondary_trigger_minute=60,
        secondary_rise_minutes=10, secondary_magnitude=0.1 * (14 - 8),
    )
    r = run_gas_process(cfg, "Z1_confined_test", duration_minutes=90, seed=5)
    dt_per_min = 60 / 5  # ticks per minute at dt=5s
    plateau_reading = r[int(45 * dt_per_min)].concentration
    final_reading = r[-1].concentration
    assert abs(plateau_reading - 8.0) < 1.5
    assert final_reading > plateau_reading
