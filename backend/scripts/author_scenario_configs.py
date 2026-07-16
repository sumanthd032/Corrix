"""Authoring tool that emits the versioned scenario config YAML files under
data/scenarios/. Per CORRIX_DATA_METHODOLOGY.md §16 (Reproducibility),
the YAML files themselves are the source of truth going forward — this
script is a one-time (or re-run-when-parameters-change) authoring
convenience, not something the running application depends on.

Run from backend/: python scripts/author_scenario_configs.py
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.scenario import (  # noqa: E402
    ComplianceSignalConfig,
    CVEventInjectionConfig,
    GasSignalConfig,
    PermitInjectionConfig,
    ScenarioConfig,
    ScenarioGroundTruth,
    ScenarioSignals,
    ShiftInjectionConfig,
    WorkerLocationInjectionConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"

# Per §12.5: a fixed majority of seed variants per scenario type populate
# the self-improving memory loop's exemplar index ("population"); the
# remainder are held out and never contribute exemplars, only measured
# against them. 3 population : 2 held_out per scenario type, matching the
# doc's own worked example.
SEED_SPLIT = ["population", "population", "population", "held_out", "held_out"]


def write_config(config: ScenarioConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def author_s1() -> None:
    base_seed = 20260714
    for i, split in enumerate(SEED_SPLIT):
        seed = base_seed + i
        config = ScenarioConfig(
            scenario_id="S1",
            name="Anchor case — ladle moisture/entrapped-gas compound risk",
            seed=seed,
            memory_split=split,
            duration_minutes=90,
            zone="Z1",
            signals=ScenarioSignals(
                compliance=ComplianceSignalConfig(
                    Q_baseline=0.92,
                    degradation_step=0.35,
                    lapse_coupling="shift_changeover_proximity",
                ),
                permit=PermitInjectionConfig(
                    type="lifting_operation",
                    inject_at_minute=20,
                    linked_checklist_id="CHK-0410",
                ),
                shift=ShiftInjectionConfig(changeover_at_minute=68),
                worker_location=WorkerLocationInjectionConfig(
                    badge_id="W-0142", zone_entry_at_minute=55
                ),
                cv_event=CVEventInjectionConfig(inject_at_minute=55, detection="person"),
            ),
            ground_truth=ScenarioGroundTruth(
                compound_risk_window_start_minute=60,
                incident_threshold_minute=82,
            ),
        )
        write_config(config, SCENARIOS_DIR / "s1" / f"seed_{seed}.yaml")


def author_s2() -> None:
    base_seed = 20260720
    for i, split in enumerate(SEED_SPLIT):
        seed = base_seed + i
        config = ScenarioConfig(
            scenario_id="S2",
            name="Confined space entry during abnormal process conditions",
            seed=seed,
            memory_split=split,
            duration_minutes=110,
            zone="Z7",
            signals=ScenarioSignals(
                gas=GasSignalConfig(
                    gas_type="LEL",
                    unit="pct_LEL",
                    C_baseline=1.0,
                    k=0.1,
                    sigma=0.05,
                    source_shape="ramp_with_plateau",
                    a=0.1 * (7.0 - 1.0),
                    t0_minute=10,
                    t_rise_minutes=25,
                    C_plateau=7.0,
                    secondary_trigger_minute=70,
                    secondary_rise_minutes=15,
                    secondary_magnitude=0.1 * (14.0 - 7.0),
                ),
                permit=PermitInjectionConfig(
                    type="confined_space_entry", inject_at_minute=15
                ),
                shift=ShiftInjectionConfig(changeover_at_minute=75),
                worker_location=WorkerLocationInjectionConfig(
                    badge_id="W-0210", zone_entry_at_minute=68
                ),
                cv_event=CVEventInjectionConfig(inject_at_minute=68, detection="person"),
            ),
            ground_truth=ScenarioGroundTruth(
                compound_risk_window_start_minute=65,
                incident_threshold_minute=92,
            ),
        )
        write_config(config, SCENARIOS_DIR / "s2" / f"seed_{seed}.yaml")


def author_s3() -> None:
    base_seed = 20260730
    for i, split in enumerate(SEED_SPLIT):
        seed = base_seed + i
        config = ScenarioConfig(
            scenario_id="S3",
            name="Maintenance activity co-occurring with gas accumulation",
            seed=seed,
            memory_split=split,
            duration_minutes=100,
            zone="Z2",
            signals=ScenarioSignals(
                gas=GasSignalConfig(
                    gas_type="LEL",
                    unit="pct_LEL",
                    C_baseline=2.0,
                    k=0.08,
                    sigma=0.1,
                    source_shape="ramp",
                    a=0.08 * (13.0 - 2.0),
                    t0_minute=15,
                    t_rise_minutes=70,
                ),
                permit=PermitInjectionConfig(type="cold_work", inject_at_minute=10),
                shift=ShiftInjectionConfig(changeover_at_minute=80),
                worker_location=WorkerLocationInjectionConfig(
                    badge_id="W-0305", zone_entry_at_minute=12
                ),
                cv_event=CVEventInjectionConfig(inject_at_minute=12, detection="person"),
            ),
            ground_truth=ScenarioGroundTruth(
                compound_risk_window_start_minute=40,
                incident_threshold_minute=82,
            ),
        )
        write_config(config, SCENARIOS_DIR / "s3" / f"seed_{seed}.yaml")


def author_s4() -> None:
    base_seed = 20260740
    for i, split in enumerate(SEED_SPLIT):
        seed = base_seed + i
        config = ScenarioConfig(
            scenario_id="S4",
            name="Hot-work permit near elevated, rising gas readings",
            seed=seed,
            memory_split=split,
            duration_minutes=70,
            zone="Z2",
            signals=ScenarioSignals(
                gas=GasSignalConfig(
                    gas_type="LEL",
                    unit="pct_LEL",
                    C_baseline=2.0,
                    k=0.1,
                    sigma=0.08,
                    source_shape="step_decay",
                    a=2.8,
                    t0_minute=30,
                    tau_minutes=8,
                ),
                permit=PermitInjectionConfig(type="hot_work", inject_at_minute=20),
                shift=ShiftInjectionConfig(changeover_at_minute=50),
                worker_location=WorkerLocationInjectionConfig(
                    badge_id="W-0417", zone_entry_at_minute=25
                ),
                cv_event=CVEventInjectionConfig(inject_at_minute=25, detection="person"),
            ),
            ground_truth=ScenarioGroundTruth(
                compound_risk_window_start_minute=30,
                incident_threshold_minute=38,
            ),
        )
        write_config(config, SCENARIOS_DIR / "s4" / f"seed_{seed}.yaml")


ZONE_HAZARD_CLASS = {
    "Z1": "high", "Z2": "high", "Z3": "medium", "Z4": "low",
    "Z5": "medium", "Z6": "medium", "Z7": "high", "Z8": "low",
}
NEGATIVE_CONTROL_BASELINE_BY_HAZARD = {"high": 2.0, "medium": 1.5, "low": 0.5}


def author_negative_controls() -> None:
    """Matched volume to the 20 positive instances above (§12.4): identical
    generators, S(t) = 0 for the entire run (i.e. the gas OU process still
    runs — baseline + noise only, no source term — a=0.0 realizes "S(t)=0"
    exactly per the §3.1 formula), p_lapse(t) left at its normal low
    background rate. Every zone still gets a real gas reading series, not
    an empty stream — needed for the anomaly scorer (Step 3) and the
    Evaluation Harness (Step 8) to measure a false-positive rate against
    an actual signal, not an absence of one.

    Ground truth is a sentinel here, not a real threshold: both fields are
    set to `duration_minutes` (the run never reaches a scripted incident),
    documented in data/scenarios/README.md.
    """
    zones = ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7", "Z8"]
    base_seed = 90000
    duration_minutes = 90
    for i in range(20):
        seed = base_seed + i
        zone = zones[i % len(zones)]
        split = "population" if i % 5 < 3 else "held_out"
        baseline = NEGATIVE_CONTROL_BASELINE_BY_HAZARD[ZONE_HAZARD_CLASS[zone]]
        config = ScenarioConfig(
            scenario_id=f"N{i + 1}",
            name=f"Negative control {i + 1} — normal operating day, zone {zone}",
            seed=seed,
            memory_split=split,
            duration_minutes=duration_minutes,
            zone=zone,
            signals=ScenarioSignals(
                gas=GasSignalConfig(
                    gas_type="LEL",
                    unit="pct_LEL",
                    C_baseline=baseline,
                    k=0.08,
                    sigma=0.1,
                    source_shape="ramp",
                    a=0.0,
                    t0_minute=0,
                    t_rise_minutes=1,
                )
            ),
            ground_truth=ScenarioGroundTruth(
                compound_risk_window_start_minute=duration_minutes,
                incident_threshold_minute=duration_minutes,
            ),
        )
        write_config(config, SCENARIOS_DIR / "negative" / f"n{i + 1:02d}.yaml")


def main() -> None:
    author_s1()
    author_s2()
    author_s3()
    author_s4()
    author_negative_controls()
    print("Authored 20 positive scenario configs (S1-S4, 5 seeds each) and "
          "20 matched negative-control configs.")


if __name__ == "__main__":
    main()
