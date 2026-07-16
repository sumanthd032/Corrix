"""Ornstein-Uhlenbeck gas-concentration simulator, per
CORRIX_DATA_METHODOLOGY.md §3. Used for S2/S3/S4 — NOT for S1, which uses
the structurally separate procedural-compliance model (compliance_process.py).

`step()` is deliberately standalone and reused, unmodified, as the engine
behind the Monte Carlo Time-to-Critical forecaster in Step 8 — one
implementation serves both the offline simulator and the live forecaster.
"""

import math
from datetime import datetime, timedelta

import numpy as np

from app.schemas import GasSensorReading, GasType
from app.schemas.scenario import GasSignalConfig


def step(
    C_t: float,
    k: float,
    C_baseline: float,
    S_t: float,
    sigma: float,
    dt: float,
    rng: np.random.Generator,
) -> float:
    """Euler-Maruyama step for dC(t) = k(C_baseline - C(t))dt + S(t)dt + sigma*dW(t).

    Concentration can't go negative. `dt` is in minutes, matching the
    per-minute rate constants k/sigma in the scenario config.
    """
    drift = k * (C_baseline - C_t) * dt
    source = S_t * dt
    noise = sigma * math.sqrt(dt) * rng.normal(0, 1)
    return max(0.0, C_t + drift + source + noise)


def ramp_source(t_minute: float, a: float, t0: float, t_rise: float) -> float:
    """Steady accumulation (§3.3) — used for S3."""
    if t_minute < t0:
        return 0.0
    return a * min(1.0, (t_minute - t0) / t_rise)


def step_decay_source(t_minute: float, a: float, t0: float, tau: float) -> float:
    """Sudden release, slow dissipation (§3.3) — used for S4."""
    if t_minute < t0:
        return 0.0
    return a * math.exp(-(t_minute - t0) / tau)


def ramp_with_plateau_source(
    t_minute: float,
    a: float,
    t0: float,
    t_rise: float,
    secondary_trigger: float | None,
    secondary_rise: float | None,
    secondary_magnitude: float | None,
) -> float:
    """Accumulation that stabilizes, then a secondary compounding ramp
    (§3.3) — used for S2, where personnel entry / changeover-driven
    inattention is what pushes an already-plateaued reading critical."""
    primary = 0.0 if t_minute < t0 else a * min(1.0, (t_minute - t0) / t_rise)
    secondary = 0.0
    if (
        secondary_trigger is not None
        and secondary_rise is not None
        and secondary_magnitude is not None
        and t_minute >= secondary_trigger
    ):
        secondary = secondary_magnitude * min(
            1.0, (t_minute - secondary_trigger) / secondary_rise
        )
    return primary + secondary


def source_term(t_minute: float, config: GasSignalConfig) -> float:
    if config.source_shape == "ramp":
        return ramp_source(t_minute, config.a, config.t0_minute, config.t_rise_minutes)
    if config.source_shape == "step_decay":
        return step_decay_source(t_minute, config.a, config.t0_minute, config.tau_minutes)
    if config.source_shape == "ramp_with_plateau":
        return ramp_with_plateau_source(
            t_minute,
            config.a,
            config.t0_minute,
            config.t_rise_minutes,
            config.secondary_trigger_minute,
            config.secondary_rise_minutes,
            config.secondary_magnitude,
        )
    raise ValueError(f"unknown source shape: {config.source_shape}")


def run_gas_process(
    config: GasSignalConfig,
    zone_id: str,
    duration_minutes: int,
    seed: int,
    dt_seconds: float = 5.0,
    start_time: datetime | None = None,
) -> list[GasSensorReading]:
    """Deterministic, seeded run of the OU process over `duration_minutes`,
    ticking every `dt_seconds` (default: realistic gas-detector polling
    cadence, §3.2). Same config + seed reproduces bit-for-bit identically."""
    rng = np.random.default_rng(seed)
    dt_minutes = dt_seconds / 60.0
    n_steps = int(duration_minutes * 60 / dt_seconds)
    start_time = start_time or datetime(2026, 7, 19, 10, 0, 0)

    readings: list[GasSensorReading] = []
    C = config.C_baseline
    for i in range(n_steps + 1):
        t_minute = i * dt_minutes
        S_t = source_term(t_minute, config)
        if i > 0:
            C = step(C, config.k, config.C_baseline, S_t, config.sigma, dt_minutes, rng)
        readings.append(
            GasSensorReading(
                zone_id=zone_id,
                gas_type=GasType(config.gas_type),
                concentration=round(C, 4),
                unit=config.unit,
                timestamp=start_time + timedelta(minutes=t_minute),
            )
        )
    return readings
