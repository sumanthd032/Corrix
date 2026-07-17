"""Monte Carlo Time-to-Critical forecasting, per
CORRIX_DATA_METHODOLOGY.md §3.6: replaces Step 4's LLM-estimated stub
with a real rollout reusing the exact same `step()` function the OU gas
simulator itself uses (Section 3.2), not a fresh implementation.

Scoped to gas-based zones (S2/S3/S4-style) only, matching the doc's own
literal description ("the same calibrated (k, C_baseline, sigma) for
that zone"); S1's compliance signal is a single Bernoulli lapse event,
not an OU process, so this specific mechanism doesn't apply to it; the
Chair's LLM-estimated placeholder remains S1's time-to-critical for now,
a real and honest scope limit, not something quietly assumed away.
"""

from dataclasses import dataclass

import numpy as np

from app.detection.anomaly_scorer import HIGH_Z
from app.schemas import TimeToCriticalForecast
from app.schemas.scenario import GasSignalConfig
from app.simulation.gas_process import source_term, step

DEFAULT_N_PATHS = 200
DEFAULT_HORIZON_MINUTES = 60
DEFAULT_DT_MINUTES = 1.0


@dataclass
class _RolloutResult:
    escalation_probability: float
    median_minutes: float
    iqr_low_minutes: float
    iqr_high_minutes: float


def _roll_forward_paths(
    current_value: float,
    elapsed_minutes: float,
    gas_config: GasSignalConfig,
    baseline_mean: float,
    baseline_std: float,
    seed: int,
    n_paths: int,
    horizon_minutes: int,
    dt_minutes: float,
) -> _RolloutResult:
    rng = np.random.default_rng(seed)
    n_steps = int(horizon_minutes / dt_minutes)
    crossing_times: list[float] = []

    for _ in range(n_paths):
        concentration = current_value
        crossed_at: float | None = None
        for step_index in range(1, n_steps + 1):
            t_minute = elapsed_minutes + step_index * dt_minutes
            s_t = source_term(t_minute, gas_config)
            concentration = step(
                concentration, gas_config.k, gas_config.C_baseline, s_t, gas_config.sigma,
                dt_minutes, rng,
            )
            z = (concentration - baseline_mean) / baseline_std
            if abs(z) >= HIGH_Z:
                crossed_at = step_index * dt_minutes
                break
        if crossed_at is not None:
            crossing_times.append(crossed_at)

    escalation_probability = len(crossing_times) / n_paths
    if crossing_times:
        median = float(np.median(crossing_times))
        iqr_low = float(np.percentile(crossing_times, 25))
        iqr_high = float(np.percentile(crossing_times, 75))
    else:
        # No path crossed within the horizon at all, so report the horizon
        # itself rather than fabricating a number the rollout never
        # actually produced.
        median = float(horizon_minutes)
        iqr_low = float(horizon_minutes)
        iqr_high = float(horizon_minutes)

    return _RolloutResult(escalation_probability, median, iqr_low, iqr_high)


def forecast_time_to_critical(
    current_value: float,
    elapsed_minutes: float,
    gas_config: GasSignalConfig,
    baseline_mean: float,
    baseline_std: float,
    seed: int,
    n_paths: int = DEFAULT_N_PATHS,
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
    dt_minutes: float = DEFAULT_DT_MINUTES,
) -> TimeToCriticalForecast:
    """N independent stochastic rollouts from the currently observed
    state, using the zone's own calibrated OU parameters and the same
    baseline the live z-score trigger scores against: median +
    interquartile crossing time, not a point estimate, per §3.6."""
    result = _roll_forward_paths(
        current_value, elapsed_minutes, gas_config, baseline_mean, baseline_std,
        seed, n_paths, horizon_minutes, dt_minutes,
    )
    return TimeToCriticalForecast(
        median_minutes=result.median_minutes,
        iqr_low_minutes=result.iqr_low_minutes,
        iqr_high_minutes=result.iqr_high_minutes,
        escalation_probability=result.escalation_probability,
        horizon_minutes=horizon_minutes,
    )
