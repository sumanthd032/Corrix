"""Rolling z-score anomaly scorer, per CORRIX_BUILD_PLAN.md Step 3.

The cheap, explainable first pass: no LLM, no fusion across data sources
— just "is this zone's own signal statistically unusual relative to its
own established baseline." This is deliberately reused for two purposes
(build once): (a) the event trigger that convenes the Safety Council
(Step 4), and (b) the Evaluation Harness's baseline comparison (Step 8).

Works on a plain list of floats so it applies identically to gas
readings (§3) and the S1 compliance signal (§4) — the anomaly scorer
doesn't care which physical process produced the number, only whether
it's a statistical outlier against the zone's normal operating range.

Design note — why a calibrated baseline, not a naive trailing window:
a first implementation computed each point's z-score against a rolling
window of the immediately preceding readings. Checked against the full
scenario library (Step 2), this produced a 100% false-positive rate on
negative controls: an OU process's own mean-reversion makes it strongly
autocorrelated, so a short trailing window's mean/std reflects the
process's local smoothness, not its true normal-operating spread — any
ordinary reading looks "anomalous" against a window that's artificially
tight because neighboring points are highly correlated with each other.
Calibrating mean/std once, from an initial baseline period before any
scripted event can plausibly have started (§12.1's earliest `t0_minute`
across the library is 10 minutes), and scoring every subsequent reading
— including new streaming readings — against that fixed reference
cleanly separates the two: checked empirically, negative controls topped
out at |z| ~= 12, positive scenarios' gas signals started at |z| ~= 84.
"""

import math
from dataclasses import dataclass

from app.schemas import RiskLevel

# z-score cutoffs, in standard deviations from the calibrated baseline.
# Not a physical/regulatory threshold (those live in the gas/compliance
# models themselves) — this is the detection layer's own statistical
# convention, chosen with a wide margin against the empirical negative-
# control ceiling (~12) and positive-scenario floor (~84) found when
# checking this scorer against the full Step 2 scenario library.
CAUTION_Z = 6.0
HIGH_Z = 20.0
CRITICAL_Z = 50.0

# Ticks used to calibrate the baseline mean/std, before scoring begins.
# 100 ticks * 5s = ~8.3 minutes — comfortably before the earliest
# scripted event onset (`t0_minute`) across the authored scenario
# library, so the baseline never absorbs part of the injected signal.
DEFAULT_BASELINE_TICKS = 100


@dataclass
class AnomalyPoint:
    index: int
    value: float
    z_score: float
    risk_level: RiskLevel


def classify_z_score(z: float) -> RiskLevel:
    abs_z = abs(z)
    if abs_z >= CRITICAL_Z:
        return "CRITICAL"
    if abs_z >= HIGH_Z:
        return "HIGH"
    if abs_z >= CAUTION_Z:
        return "CAUTION"
    return "SAFE"


def baseline_calibrated_zscore(
    values: list[float], baseline_ticks: int = DEFAULT_BASELINE_TICKS
) -> list[float]:
    """Calibrate mean/std once from the first `baseline_ticks` readings,
    then score every reading (including the baseline period itself)
    against that fixed reference. A near-zero baseline std (e.g. S1's
    compliance signal, flat until a single scripted lapse) is floored so a
    real deviation still produces a large-but-finite score rather than a
    division blow-up.
    """
    n = min(baseline_ticks, len(values))
    baseline = values[:n]
    mean = sum(baseline) / len(baseline)
    variance = sum((v - mean) ** 2 for v in baseline) / len(baseline)
    std = math.sqrt(variance)
    if std < 1e-6:
        std = 1e-6
    z_cap = 1000.0
    return [max(-z_cap, min(z_cap, (v - mean) / std)) for v in values]


def score_series(
    values: list[float], baseline_ticks: int = DEFAULT_BASELINE_TICKS
) -> list[AnomalyPoint]:
    z_scores = baseline_calibrated_zscore(values, baseline_ticks)
    return [
        AnomalyPoint(index=i, value=v, z_score=z, risk_level=classify_z_score(z))
        for i, (v, z) in enumerate(zip(values, z_scores))
    ]


def max_risk_level(points: list[AnomalyPoint]) -> RiskLevel:
    order = {"SAFE": 0, "CAUTION": 1, "HIGH": 2, "CRITICAL": 3}
    return max((p.risk_level for p in points), key=lambda r: order[r], default="SAFE")
