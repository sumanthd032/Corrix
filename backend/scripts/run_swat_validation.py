"""Runs the SWaT external-validation comparison for real, per
CORRIX_DATA_METHODOLOGY.md §15.2, and writes the comparison table to
data/evaluation/, a runnable script, not a hand-typed table.

Requires the real SWaT dataset's normal+attack merged CSV (only the
Normal-labeled rows are used) at data/swat/merged.csv, a real, access-
restricted dataset from iTrust SUTD, provided by the user rather than
downloaded automatically (see CLAUDE.md section 3 on external assets).

Run from backend/: python scripts/run_swat_validation.py
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.swat_validation import (  # noqa: E402
    fit_our_simulator_reference,
    fit_swat_reference_tags,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SWAT_CSV_PATH = REPO_ROOT / "data" / "swat" / "merged.csv"
RESULTS_DIR = REPO_ROOT / "data" / "evaluation"


def main() -> None:
    if not SWAT_CSV_PATH.exists():
        raise SystemExit(
            f"SWaT dataset not found at {SWAT_CSV_PATH}. This is a real, "
            "access-restricted dataset that must be provided manually."
        )

    print(f"Fitting AR(1) models to real SWaT normal-operation tags from {SWAT_CSV_PATH}...")
    swat_fits = fit_swat_reference_tags(str(SWAT_CSV_PATH))

    print("Fitting the identical AR(1) model to our own simulator's output...")
    our_fits = fit_our_simulator_reference()

    swat_ratios = [f.noise_to_signal_ratio for f in swat_fits]
    our_ratios = [f.noise_to_signal_ratio for f in our_fits]
    swat_range = (min(swat_ratios), max(swat_ratios))
    our_range = (min(our_ratios), max(our_ratios))
    ours_within_swat_range = all(swat_range[0] <= r <= swat_range[1] for r in our_ratios)

    table = {
        "swat_tags": [asdict(f) for f in swat_fits],
        "our_simulator_configs": [asdict(f) for f in our_fits],
        "swat_noise_to_signal_range": swat_range,
        "our_noise_to_signal_range": our_range,
        "our_noise_to_signal_falls_within_swat_range": ours_within_swat_range,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "swat_validation.json").write_text(json.dumps(table, indent=2), encoding="utf-8")

    print("\nSWaT reference tags (real, normal-operation only):")
    for f in swat_fits:
        print(
            f"  {f.tag}: n={f.n_samples}, k'={f.mean_reversion_rate:.4f}/min, "
            f"noise/signal={f.noise_to_signal_ratio:.4f}, "
            f"skew={f.residual_skew:.2f}, kurtosis={f.residual_kurtosis:.1f}"
        )

    print("\nOur simulator (same AR(1) fit applied to real simulated output):")
    for f in our_fits:
        print(
            f"  {f.tag}: k'={f.mean_reversion_rate:.4f}/min, "
            f"noise/signal={f.noise_to_signal_ratio:.4f}, "
            f"skew={f.residual_skew:.2f}, kurtosis={f.residual_kurtosis:.1f}"
        )

    print(f"\nSWaT noise-to-signal ratio range: {swat_range[0]:.4f} - {swat_range[1]:.4f}")
    print(f"Our noise-to-signal ratio range: {our_range[0]:.4f} - {our_range[1]:.4f}")
    print(f"Our ratios fall within SWaT's observed range: {ours_within_swat_range}")
    print(
        "\nReal, disclosed difference (not hidden): SWaT's residual kurtosis is "
        "extremely high (hundreds to hundreds of thousands) compared to our "
        "simulator's near-zero kurtosis; real industrial sensors show heavy-"
        "tailed spikes (likely actuator switching events), while our OU process "
        "produces genuinely Gaussian noise. This validates the noise-to-signal "
        "scale, not the tail shape, a limitation worth stating plainly, per "
        "CORRIX_DATA_METHODOLOGY.md section 15.3."
    )
    print(f"\nResults written to {RESULTS_DIR / 'swat_validation.json'}")


if __name__ == "__main__":
    main()
