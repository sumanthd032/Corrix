"""Joint-evidence novelty detector, per CORRIX_DATA_METHODOLOGY.md §13.
A second, independent trigger path alongside the Step 3 rule/threshold
trigger: catches a compound-risk combination nobody scripted, including
the five authored scenario types, by scoring how statistically unusual
the *joint* evidence state is against a reference distribution of normal
plant days — rather than checking any one signal against its own
threshold.

Per §13.3: the simplest model that actually separates known-positive
scenarios from negative controls in a quick offline check is the right
choice, not the most elaborate one — a Mahalanobis distance against a
fitted multivariate Gaussian, not an autoencoder.
"""

from dataclasses import dataclass

import numpy as np

from app.detection.joint_evidence import build_joint_evidence_series
from app.schemas import Zone
from app.simulation.scenario_engine import ScenarioOutput


@dataclass
class NoveltyModel:
    mean: np.ndarray
    inv_cov: np.ndarray
    threshold: float

    def score(self, vector: list[float]) -> float:
        x = np.asarray(vector, dtype=float)
        delta = x - self.mean
        return float(np.sqrt(max(0.0, delta @ self.inv_cov @ delta.T)))

    def is_novel(self, vector: list[float]) -> bool:
        return self.score(vector) >= self.threshold


def fit_novelty_model(
    training_vectors: list[list[float]], percentile: float = 99.0
) -> NoveltyModel:
    """Fit a multivariate Gaussian over `training_vectors` (every tick of
    every `memory_split: population` negative-control run, per §13.2) and
    calibrate a threshold as the given percentile of the *training set's
    own* scores (§13.3's "calibrated via the same negative-control set") —
    an empirical calibration rather than a fixed chi-square critical value,
    since the features are a mix of a heavy-tailed z-score and near-binary
    indicators, not a clean multivariate normal.
    """
    data = np.asarray(training_vectors, dtype=float)
    mean = data.mean(axis=0)
    cov = np.cov(data, rowvar=False)
    # A near-constant feature makes the covariance matrix singular and
    # needs regularizing before inverting — but a single tiny ridge
    # constant across every dimension is the wrong fix here, checked
    # empirically rather than assumed correct: negative controls' short
    # windows never actually reach a shift changeover, so the
    # changeover-proximity feature has essentially zero variance in this
    # training set specifically (not because it's an unimportant
    # feature — S1-S4 all deliberately script events near changeover).
    # A universal 1e-6 ridge treats that near-zero variance as the *real*
    # expected variance, so any genuine changeover proximity elsewhere
    # produces a Mahalanobis contribution large enough to swamp every
    # other feature — turning a joint-evidence detector into a
    # single-feature one. Flooring each feature's own variance at a
    # sensible minimum (rather than adding one constant to all of them)
    # keeps a near-constant feature from dominating the distance while
    # leaving genuinely well-observed feature variances untouched.
    variance_floor = 0.05
    diag_idx = np.arange(cov.shape[0])
    deficits = variance_floor - cov[diag_idx, diag_idx]
    cov[diag_idx, diag_idx] += np.maximum(0.0, deficits)
    inv_cov = np.linalg.pinv(cov)

    model = NoveltyModel(mean=mean, inv_cov=inv_cov, threshold=0.0)
    training_scores = [model.score(list(row)) for row in data]
    threshold = float(np.percentile(training_scores, percentile))
    return NoveltyModel(mean=mean, inv_cov=inv_cov, threshold=threshold)


def find_first_novelty_trigger(model: NoveltyModel, zone: Zone, out: ScenarioOutput) -> int | None:
    """The novelty-detector counterpart to `trigger.find_first_trigger`
    (§13.4's second, independent trigger path): the index of the first
    tick whose joint-evidence vector clears the calibrated threshold, or
    None if it never does."""
    vectors = build_joint_evidence_series(zone, out)
    for i, vector in enumerate(vectors):
        if model.is_novel(vector):
            return i
    return None
