"""SWaT external validation, per CORRIX_DATA_METHODOLOGY.md §15. The
AR(1) fitting procedure itself is tested against synthetic data with a
known ground-truth mean-reversion rate and noise level (fast,
deterministic, no dataset needed); the real SWaT comparison is tested
conditionally, since the dataset is a real, access-restricted file
(data/swat/merged.csv) provided by the user, not committed to the repo.
"""

from pathlib import Path

import numpy as np
import pytest

from app.evaluation.swat_validation import (
    fit_ar1,
    fit_our_simulator_reference,
    fit_swat_reference_tags,
)

SWAT_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "swat" / "merged.csv"


def test_fit_ar1_recovers_known_parameters_from_synthetic_data():
    """Simulate a known OU process (k'=0.2/min, baseline=10, sigma=0.5)
    and confirm the fit recovers parameters close to the ground truth."""
    rng = np.random.default_rng(42)
    dt = 1.0
    k_prime = 0.2
    baseline = 10.0
    sigma = 0.5
    n = 5000

    values = np.empty(n)
    values[0] = baseline
    for i in range(1, n):
        drift = k_prime * (baseline - values[i - 1]) * dt
        noise = sigma * np.sqrt(dt) * rng.normal()
        values[i] = values[i - 1] + drift + noise

    result = fit_ar1(values, dt_minutes=dt)
    assert result is not None
    assert result.mean_reversion_rate == pytest.approx(k_prime, rel=0.3)
    assert result.baseline == pytest.approx(baseline, rel=0.1)
    assert result.implied_sigma == pytest.approx(sigma, rel=0.2)


def test_fit_ar1_returns_none_for_a_constant_series():
    values = np.full(100, 5.0)
    assert fit_ar1(values, dt_minutes=1.0) is None


def test_fit_our_simulator_reference_produces_real_fits():
    fits = fit_our_simulator_reference()
    assert len(fits) == 3
    for f in fits:
        assert f.n_samples > 0
        assert f.implied_sigma > 0


@pytest.mark.skipif(not SWAT_CSV_PATH.exists(), reason="Real SWaT dataset not present locally")
def test_swat_reference_tags_fit_against_the_real_dataset():
    fits = fit_swat_reference_tags(str(SWAT_CSV_PATH))
    assert len(fits) == 3
    for f in fits:
        assert f.n_samples > 1_000_000  # SWaT's real normal-operation segment is large
        assert f.implied_sigma > 0


@pytest.mark.skipif(not SWAT_CSV_PATH.exists(), reason="Real SWaT dataset not present locally")
def test_our_noise_to_signal_ratio_falls_within_swats_observed_range():
    """The actual claim CORRIX_DATA_METHODOLOGY.md section 15.2 asks for:
    our synthetic noise-to-signal ratio should sit within the range a
    real industrial control system exhibits during normal operation."""
    swat_fits = fit_swat_reference_tags(str(SWAT_CSV_PATH))
    our_fits = fit_our_simulator_reference()

    swat_ratios = [f.noise_to_signal_ratio for f in swat_fits]
    swat_low, swat_high = min(swat_ratios), max(swat_ratios)

    for f in our_fits:
        assert swat_low <= f.noise_to_signal_ratio <= swat_high, (
            f"{f.tag}'s noise-to-signal ratio {f.noise_to_signal_ratio:.4f} falls "
            f"outside SWaT's observed range [{swat_low:.4f}, {swat_high:.4f}]"
        )
