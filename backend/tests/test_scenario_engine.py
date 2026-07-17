"""Scenario engine end-to-end: determinism, schema validity, and
worker-location/permit consistency, the Step 2 Definition of Done."""

from pathlib import Path

from app.simulation.scenario_engine import run_scenario_from_file

S1_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "data" / "scenarios" / "s1_anchor.example.yaml"
)


def test_run_scenario_is_bit_for_bit_deterministic():
    out1 = run_scenario_from_file(S1_EXAMPLE)
    out2 = run_scenario_from_file(S1_EXAMPLE)
    assert [r.compliance_score for r in out1.compliance_readings] == [
        r.compliance_score for r in out2.compliance_readings
    ]
    assert [p.permit_id for p in out1.permits] == [p.permit_id for p in out2.permits]
    assert [e.timestamp for e in out1.worker_pings] == [
        e.timestamp for e in out2.worker_pings
    ]


def test_output_is_schema_valid_with_zero_manual_patching():
    # run_scenario_from_file returns a fully-typed ScenarioOutput built
    # entirely from Step 1 schema instances. If this call succeeds, every
    # nested model already validated during construction.
    out = run_scenario_from_file(S1_EXAMPLE)
    assert out.scenario_id == "S1"
    assert out.memory_split == "population"


def test_worker_with_active_permit_shows_up_in_that_zone():
    out = run_scenario_from_file(S1_EXAMPLE)
    scripted_permit = next(p for p in out.permits if p.permit_id.startswith("P-SCRIPT"))
    scripted_ping = next(e for e in out.worker_pings if e.badge_id == "W-0142")
    assert scripted_ping.zone_id == scripted_permit.zone_id
    assert scripted_permit.start_time <= scripted_ping.timestamp <= scripted_permit.end_time


def test_compliance_signal_present_and_gas_signal_absent_for_s1():
    """S1 uses the procedural-compliance model, not the gas model; the two
    are structurally separate per §2/§4."""
    out = run_scenario_from_file(S1_EXAMPLE)
    assert len(out.compliance_readings) > 0
    assert len(out.gas_readings) == 0
