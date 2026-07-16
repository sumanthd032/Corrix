"""The event-trigger condition (anomaly OR permit-conflict crossing
threshold): Step 3's DoD checked end-to-end against the real scenario
library, including that it stays quiet on every negative control."""

from pathlib import Path

import pytest

from app.detection.trigger import find_first_trigger
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    load_scenario_config,
    run_scenario,
)

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
POSITIVE_DIRS = ["s1", "s2", "s3", "s4"]


def _signal_values(out) -> list[float]:
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def _zone(zone_id: str):
    layout = load_plant_layout()
    return next(z for z in layout.zones if z.zone_id == zone_id)


@pytest.mark.parametrize(
    "path",
    [p for d in POSITIVE_DIRS for p in sorted((SCENARIOS_DIR / d).glob("*.yaml"))],
    ids=lambda p: p.stem,
)
def test_every_positive_scenario_triggers_with_positive_lead_time(path):
    config = load_scenario_config(path)
    out = run_scenario(config)
    trigger = find_first_trigger(
        _zone(config.zone), _signal_values(out), out.permits, DEFAULT_START_TIME
    )
    assert trigger is not None
    assert trigger.trigger_reason == "rule_threshold"
    trigger_minute = trigger.index * 5 / 60
    lead_time = config.ground_truth.incident_threshold_minute - trigger_minute
    assert lead_time > 0, f"{path.stem}: trigger came after the incident threshold"


@pytest.mark.parametrize(
    "path", sorted((SCENARIOS_DIR / "negative").glob("*.yaml")), ids=lambda p: p.stem
)
def test_negative_controls_never_trigger(path):
    config = load_scenario_config(path)
    out = run_scenario(config)
    trigger = find_first_trigger(
        _zone(config.zone), _signal_values(out), out.permits, DEFAULT_START_TIME
    )
    assert trigger is None
