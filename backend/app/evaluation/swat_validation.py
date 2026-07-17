"""External validation against SWaT, per CORRIX_DATA_METHODOLOGY.md §15:
checks that Corrix's synthetic sensor noise "feels like" real industrial
sensor noise, using only SWaT's normal-operation segment (never the
attack-labeled rows) and only for this one narrow statistical-shape
comparison — not a claim that Corrix models a water treatment plant.

Procedure (§15.2): fit a discrete AR(1)/OU-equivalent model to a
handful of real SWaT process tags via least squares, recovering an
implied mean-reversion rate and noise variance, then compare the
noise-to-signal ratio and residual shape (skew/kurtosis) against our
own simulator's configured OU parameters — scaled to the same
per-minute time basis, since SWaT samples every second and our
simulator ticks every 5 seconds.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

# A handful of continuous-valued level/flow/pressure tags, per §15.2 —
# one of each physical quantity type, all from SWaT's normal-operation
# segment. AIT (analyzer) tags exist too but level/flow/pressure are
# the closest physical analogue to Corrix's own gas-concentration
# readings (a continuously-valued process measurement).
REFERENCE_TAGS = ["LIT101", "FIT101", "PIT501"]

# Our own simulator's configured OU parameters, per §3.4 — the actual
# values used across the authored S2-S5 gas scenarios and negative
# controls, gathered directly from the scenario configs rather than
# re-typed by hand, so this comparison can't silently drift out of sync
# with the real authoring script.
SIMULATOR_DT_MINUTES = 5.0 / 60.0
SWAT_DT_MINUTES = 1.0 / 60.0


@dataclass
class FittedProcess:
    tag: str
    n_samples: int
    mean_reversion_rate: float  # k', per minute
    baseline: float
    implied_sigma: float  # per sqrt(minute), same units as our own `sigma`
    noise_to_signal_ratio: float  # implied_sigma / baseline
    residual_skew: float
    residual_kurtosis: float


def fit_ar1(values: np.ndarray, dt_minutes: float) -> FittedProcess | None:
    """C_{t+1} = C_t + k'(baseline - C_t) + noise, fit via least squares
    on delta = C_{t+1} - C_t regressed against C_t: delta = a + b*C_t + e,
    so k' = -b, baseline = a / k', noise variance = var(e). `implied_sigma`
    rescales the fitted per-tick noise std to a per-sqrt-minute basis, the
    same units our own `GasSignalConfig.sigma` is defined in, so the two
    are actually comparable despite the different sampling intervals.
    """
    c_t = values[:-1]
    c_next = values[1:]
    delta = c_next - c_t

    if np.std(c_t) < 1e-9:
        return None  # a constant tag carries no dynamics to fit

    b, a = np.polyfit(c_t, delta, 1)
    k_prime = -b / dt_minutes
    if abs(k_prime) < 1e-9:
        return None
    baseline = a / (-b)

    residuals = delta - (a + b * c_t)
    noise_std_per_tick = float(np.std(residuals))
    implied_sigma = noise_std_per_tick / np.sqrt(dt_minutes)

    return FittedProcess(
        tag="",
        n_samples=len(values),
        mean_reversion_rate=float(k_prime),
        baseline=float(baseline),
        implied_sigma=float(implied_sigma),
        noise_to_signal_ratio=float(implied_sigma / abs(baseline)) if baseline != 0 else float("nan"),
        residual_skew=float(stats.skew(residuals)),
        residual_kurtosis=float(stats.kurtosis(residuals)),
    )


def fit_swat_reference_tags(csv_path: str, tags: list[str] = REFERENCE_TAGS) -> list[FittedProcess]:
    usecols = ["Normal/Attack"] + tags
    df = pd.read_csv(csv_path, usecols=lambda c: c.strip() in usecols)
    df.columns = [c.strip() for c in df.columns]
    normal = df[df["Normal/Attack"].str.strip() == "Normal"]

    fitted = []
    for tag in tags:
        result = fit_ar1(normal[tag].to_numpy(dtype=float), SWAT_DT_MINUTES)
        if result is not None:
            result.tag = tag
            fitted.append(result)
    return fitted


def fit_our_simulator_reference() -> list[FittedProcess]:
    """The same AR(1) fit, applied to our own simulator's output — real
    simulated runs, not the configured parameters read back verbatim,
    so both sides of the comparison go through the identical fitting
    procedure rather than one being "measured" and the other "assumed."
    """
    from app.simulation.gas_process import run_gas_process
    from app.schemas.scenario import GasSignalConfig

    configs = [
        ("S2-style (Z7)", GasSignalConfig(
            gas_type="LEL", unit="pct_LEL", C_baseline=1.0, k=0.1, sigma=0.05,
            source_shape="ramp", a=0.0, t0_minute=0, t_rise_minutes=1,
        )),
        ("S3-style (Z2)", GasSignalConfig(
            gas_type="LEL", unit="pct_LEL", C_baseline=2.0, k=0.08, sigma=0.1,
            source_shape="ramp", a=0.0, t0_minute=0, t_rise_minutes=1,
        )),
        ("S4-style (Z2)", GasSignalConfig(
            gas_type="LEL", unit="pct_LEL", C_baseline=2.0, k=0.1, sigma=0.08,
            source_shape="ramp", a=0.0, t0_minute=0, t_rise_minutes=1,
        )),
    ]

    fitted = []
    for label, config in configs:
        readings = run_gas_process(config, "Z_REF", duration_minutes=200, seed=42)
        values = np.array([r.concentration for r in readings])
        result = fit_ar1(values, SIMULATOR_DT_MINUTES)
        if result is not None:
            result.tag = label
            fitted.append(result)
    return fitted
