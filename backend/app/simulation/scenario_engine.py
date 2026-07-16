"""The scenario engine: YAML config in, seeded simulator output out, per
CORRIX_DATA_METHODOLOGY.md §12.1. Ties together the gas process, the
compliance process, and the permit/shift/worker-location generators.

Deliberately does NOT generate CVObservationEvent objects from a
scenario's `cv_event` block: CV events are hybrid — real inference,
simulated correlation (§9) — and the CVObservationEvent schema's `source`
field is `Literal["real_inference"]` for exactly that reason. Fabricating
one here would misrepresent simulated data as real inference output. The
`cv_event` config block is metadata Step 6's live-inference correlation
layer reads at demo time; the simulator's job stops at making sure a
scripted worker-location entry exists for it to correlate against.
"""

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.schemas import (
    BadgePingEvent,
    ComplianceSignalReading,
    GasSensorReading,
    PermitRecord,
    ScenarioConfig,
    ScenarioGroundTruth,
    ShiftRecord,
)
from app.simulation.compliance_process import run_compliance_process
from app.simulation.gas_process import run_gas_process
from app.simulation.permit_generator import (
    generate_background_permits,
    generate_scripted_permit,
)
from app.simulation.plant_layout import load_plant_layout
from app.simulation.shift_generator import (
    generate_background_shifts,
    generate_scenario_shift,
)
from app.simulation.worker_location_generator import (
    generate_background_pings,
    generate_scripted_ping,
)

DEFAULT_START_TIME = datetime(2026, 7, 19, 10, 0, 0)


class ScenarioOutput(BaseModel):
    scenario_id: str
    seed: int
    memory_split: str
    zone_id: str
    gas_readings: list[GasSensorReading] = []
    compliance_readings: list[ComplianceSignalReading] = []
    permits: list[PermitRecord]
    shifts: list[ShiftRecord]
    worker_pings: list[BadgePingEvent]
    ground_truth: ScenarioGroundTruth


def load_scenario_config(path: Path) -> ScenarioConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ScenarioConfig(**data)


def run_scenario(
    config: ScenarioConfig,
    start_time: datetime | None = None,
) -> ScenarioOutput:
    """Deterministic: the same config (same seed) always reproduces
    identical output, since every generator it calls is itself seeded
    from `config.seed`."""
    start_time = start_time or DEFAULT_START_TIME
    layout = load_plant_layout()
    signals = config.signals

    gas_readings: list[GasSensorReading] = []
    compliance_readings: list[ComplianceSignalReading] = []

    if signals.gas is not None:
        gas_readings = run_gas_process(
            signals.gas, config.zone, config.duration_minutes, config.seed
        )

    if signals.compliance is not None:
        changeover_minute = (
            signals.shift.changeover_at_minute
            if signals.shift is not None
            else float(config.duration_minutes * 10)  # effectively decoupled
        )
        linked_checklist_id = (
            signals.permit.linked_checklist_id
            if signals.permit is not None and signals.permit.linked_checklist_id
            else "CHK-UNSPEC"
        )
        compliance_readings = run_compliance_process(
            zone_id=config.zone,
            linked_checklist_id=linked_checklist_id,
            Q_baseline=signals.compliance.Q_baseline,
            degradation_step=signals.compliance.degradation_step,
            changeover_at_minute=changeover_minute,
            duration_minutes=config.duration_minutes,
            seed=config.seed,
        )

    permits = generate_background_permits(
        layout, config.duration_minutes, config.seed, start_time
    )
    if signals.permit is not None:
        permits.append(
            generate_scripted_permit(
                signals.permit, config.zone, start_time, config.duration_minutes
            )
        )

    shifts = generate_background_shifts(layout, start_time)
    if signals.shift is not None:
        shifts.append(generate_scenario_shift(signals.shift, config.zone, start_time))

    worker_pings = generate_background_pings(
        layout, config.duration_minutes, config.seed, start_time
    )
    if signals.worker_location is not None:
        worker_pings.append(
            generate_scripted_ping(signals.worker_location, config.zone, start_time)
        )

    return ScenarioOutput(
        scenario_id=config.scenario_id,
        seed=config.seed,
        memory_split=config.memory_split,
        zone_id=config.zone,
        gas_readings=gas_readings,
        compliance_readings=compliance_readings,
        permits=permits,
        shifts=shifts,
        worker_pings=worker_pings,
        ground_truth=config.ground_truth,
    )


def run_scenario_from_file(path: Path, start_time: datetime | None = None) -> ScenarioOutput:
    return run_scenario(load_scenario_config(path), start_time)


def find_scenario_config(
    scenarios_root: Path, scenario_id: str, seed: int
) -> Path:
    """Locate the config file for a given scenario_id + seed by reading
    each YAML's own declared fields, not by relying on a naming
    convention alone."""
    for candidate in scenarios_root.rglob("*.yaml"):
        data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        if data.get("scenario_id") == scenario_id and data.get("seed") == seed:
            return candidate
    raise FileNotFoundError(
        f"no scenario config found for scenario_id={scenario_id!r} seed={seed!r} "
        f"under {scenarios_root}"
    )
