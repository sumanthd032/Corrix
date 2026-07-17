from typing import Literal

from pydantic import BaseModel

MemorySplit = Literal["population", "held_out"]


class ComplianceSignalConfig(BaseModel):
    """S1's compliance-signal parameters, per §4."""

    model: Literal["procedural_compliance"] = "procedural_compliance"
    Q_baseline: float
    degradation_step: float
    lapse_coupling: str


class GasSignalConfig(BaseModel):
    """S2/S3/S4's OU-process gas parameters, per §3."""

    model: Literal["ou_gas_process"] = "ou_gas_process"
    gas_type: str
    unit: str = "ppm"
    C_baseline: float
    k: float
    sigma: float
    source_shape: Literal["ramp", "step_decay", "ramp_with_plateau"]
    a: float
    t0_minute: float
    t_rise_minutes: float | None = None
    tau_minutes: float | None = None
    # ramp_with_plateau only (§3.3): the secondary, smaller ramp triggered by
    # the compounding factor (e.g. ventilation reduction at changeover) that
    # pushes an already-plateaued concentration the rest of the way critical.
    C_plateau: float | None = None
    secondary_trigger_minute: float | None = None
    secondary_rise_minutes: float | None = None
    secondary_magnitude: float | None = None


class PermitInjectionConfig(BaseModel):
    type: str
    inject_at_minute: float
    linked_checklist_id: str | None = None


class ShiftInjectionConfig(BaseModel):
    changeover_at_minute: float


class WorkerLocationInjectionConfig(BaseModel):
    badge_id: str
    zone_entry_at_minute: float


class CVEventInjectionConfig(BaseModel):
    inject_at_minute: float
    detection: str


class ScenarioSignals(BaseModel):
    """A scenario injects at most one of the two signal models: S1 uses
    `compliance`, S2-S4 use `gas`, never both, per §2's structural split."""

    compliance: ComplianceSignalConfig | None = None
    gas: GasSignalConfig | None = None
    permit: PermitInjectionConfig | None = None
    shift: ShiftInjectionConfig | None = None
    worker_location: WorkerLocationInjectionConfig | None = None
    cv_event: CVEventInjectionConfig | None = None


class ScenarioGroundTruth(BaseModel):
    """Code-level incident-threshold definition, per §14.1: the reference
    points lead time and the memory-loop evaluation are measured against."""

    compound_risk_window_start_minute: float
    incident_threshold_minute: float


class ScenarioConfig(BaseModel):
    """A versioned scenario config, per §12.1: YAML in, this model out, then
    fed to the scenario engine's simulator parameters. Not a hardcoded
    script: every parameter here is what makes the library extensible."""

    scenario_id: str
    name: str
    seed: int
    memory_split: MemorySplit
    duration_minutes: int
    zone: str
    signals: ScenarioSignals
    ground_truth: ScenarioGroundTruth
