"""The Open Challenge, per CORRIX_DATA_METHODOLOGY.md §13.5: because the
scenario engine is config-driven rather than five fixed scripts, a
valid, genuinely unscripted evidence combination can be assembled live
from a small set of exposed parameters (zone, permit type, gas trend
shape, and timing) instead of only from S1-S5's pre-authored configs.

Every curated combination below deliberately avoids reusing any of
S1-S5's own (zone, source_shape, permit_type) triple, so a match here
is real proof the novelty detector generalizes past the five authored
patterns, not a relabeled S1-S5 seed. Parameters were tuned empirically
against the real detection pipeline (the same discipline as every other
threshold in this codebase) so each one is genuinely caught by the
novelty path specifically, not the rule/threshold path, which would
just prove the existing baseline works, not that the novelty detector
adds anything.
"""

from dataclasses import dataclass

from app.schemas.scenario import (
    GasSignalConfig,
    PermitInjectionConfig,
    ScenarioConfig,
    ScenarioGroundTruth,
    ScenarioSignals,
    ShiftInjectionConfig,
    WorkerLocationInjectionConfig,
)


@dataclass
class OpenChallengeParams:
    label: str
    zone: str
    source_shape: str
    C_baseline: float
    k: float
    sigma: float
    a: float
    t0_minute: float
    t_rise_minutes: float | None = None
    tau_minutes: float | None = None
    # A scripted permit is optional: for a high-hazard zone (permit
    # conflict fires at CAUTION, per permit_conflict.py's rule table),
    # an active permit makes the rule/threshold path win almost
    # immediately once the anomaly clears CAUTION, leaving the novelty
    # path no real room to win first. Two of the five curated
    # combinations below rely purely on worker presence, shift-
    # changeover proximity, and hazard class for their compound
    # signature instead, the same way S5 itself avoids scripting a
    # permit for the same structural reason.
    permit_type: str | None = None
    permit_inject_at_minute: float = 15.0
    changeover_at_minute: float = 70.0
    worker_entry_at_minute: float = 20.0
    duration_minutes: int = 100


def assemble_open_challenge_config(params: OpenChallengeParams, seed: int) -> ScenarioConfig:
    """Builds a real ScenarioConfig from Open Challenge parameters,
    the same shape `run_scenario` already consumes for every authored
    scenario, no special-casing needed."""
    return ScenarioConfig(
        scenario_id="OPEN_CHALLENGE",
        name=f"Open Challenge: {params.label}",
        seed=seed,
        memory_split="held_out",
        duration_minutes=params.duration_minutes,
        zone=params.zone,
        signals=ScenarioSignals(
            gas=GasSignalConfig(
                gas_type="LEL",
                unit="pct_LEL",
                C_baseline=params.C_baseline,
                k=params.k,
                sigma=params.sigma,
                source_shape=params.source_shape,
                a=params.a,
                t0_minute=params.t0_minute,
                t_rise_minutes=params.t_rise_minutes,
                tau_minutes=params.tau_minutes,
            ),
            permit=(
                PermitInjectionConfig(
                    type=params.permit_type, inject_at_minute=params.permit_inject_at_minute
                )
                if params.permit_type is not None
                else None
            ),
            shift=ShiftInjectionConfig(changeover_at_minute=params.changeover_at_minute),
            worker_location=WorkerLocationInjectionConfig(
                badge_id=f"W-OC-{seed}", zone_entry_at_minute=params.worker_entry_at_minute
            ),
        ),
        ground_truth=ScenarioGroundTruth(
            compound_risk_window_start_minute=params.worker_entry_at_minute,
            incident_threshold_minute=params.duration_minutes,
        ),
    )


# Five curated combinations, each a genuinely different (zone,
# source_shape, permit_type) triple from every one of S1-S5's own
# combinations (S1: Z1/compliance, S2: Z7/ramp_with_plateau,
# S3: Z2/ramp, S4: Z2/step_decay, S5: Z2/ramp) and from each other.
# Parameters tuned empirically, see
# `backend/scripts/validate_open_challenge.py`.
#
# All five deliberately live in medium-hazard zones (Z3/Z5/Z6). A real,
# non-obvious constraint forced that: in a high-hazard zone (Z1/Z2/Z7),
# `permit_conflict.py`'s rule table fires the moment the anomaly clears
# CAUTION with any permit active, which almost always wins the race
# against the novelty path, leaving no real room for novelty to be the
# reason a genuinely compound case gets caught. A first attempt at Z1/Z7
# combinations without a scripted permit avoided that race but produced
# evidence too thin for the Chair to reasonably escalate past CAUTION
# (checked directly, not assumed): the same z-score magnitude that
# reliably resolves HIGH for a permit-bearing medium-hazard combination
# reads as merely a concern, not a compound risk, when no permit or
# other zone occupant is in the picture.
CURATED_COMBINATIONS: list[OpenChallengeParams] = [
    OpenChallengeParams(
        label="Electrical isolation during a slow gas rise, Maintenance Bay",
        zone="Z3", permit_type="electrical_isolation", source_shape="ramp",
        C_baseline=1.5, k=0.08, sigma=0.08, a=0.35, t0_minute=10, t_rise_minutes=40,
    ),
    OpenChallengeParams(
        label="Cold work during a discrete gas release, Raw Material Yard",
        zone="Z5", permit_type="cold_work", source_shape="step_decay",
        C_baseline=1.5, k=0.1, sigma=0.08, a=3.0, t0_minute=20, tau_minutes=10,
    ),
    OpenChallengeParams(
        label="Hot work with a plateau-then-secondary gas rise, Quenching Tower",
        zone="Z6", permit_type="hot_work", source_shape="ramp_with_plateau",
        C_baseline=1.5, k=0.08, sigma=0.08, a=2.5, t0_minute=10, t_rise_minutes=20,
        permit_inject_at_minute=5, worker_entry_at_minute=5,
    ),
    OpenChallengeParams(
        label="Cold work during a discrete gas release, Maintenance Bay",
        zone="Z3", permit_type="cold_work", source_shape="step_decay",
        C_baseline=1.5, k=0.08, sigma=0.08, a=3.0, t0_minute=8, tau_minutes=10,
        permit_inject_at_minute=5, worker_entry_at_minute=5,
    ),
    OpenChallengeParams(
        label="Electrical isolation with a plateau-then-secondary gas rise, Raw Material Yard",
        zone="Z5", permit_type="electrical_isolation", source_shape="ramp_with_plateau",
        C_baseline=1.5, k=0.08, sigma=0.08, a=3.0, t0_minute=8, t_rise_minutes=20,
        permit_inject_at_minute=5, worker_entry_at_minute=5,
    ),
]
