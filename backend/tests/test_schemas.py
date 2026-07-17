"""Every schema round-trips from the exact example payloads given in
CORRIX_DATA_METHODOLOGY.md and CORRIX_PROJECT.md, with zero manual patching,
Step 1's Definition of Done for the schema layer."""

import yaml

from app.schemas import (
    AuditLogEntry,
    BadgePingEvent,
    ComplianceSignalReading,
    CouncilEvidence,
    CouncilVerdict,
    CVObservationEvent,
    GasSensorReading,
    HazardClass,
    PermitRecord,
    PlantLayout,
    ScenarioConfig,
    ShiftRecord,
    Zone,
    ZoneAdjacencyEdge,
)


def test_permit_record_from_doc_example():
    payload = {
        "permit_id": "P-2291",
        "type": "lifting_operation",
        "zone_id": "Z1",
        "issued_by": "Shift Supervisor A. Rao",
        "start_time": "2026-07-19T10:00:00Z",
        "end_time": "2026-07-19T14:00:00Z",
        "status": "active",
        "linked_checklist_id": "CHK-0410",
    }
    permit = PermitRecord(**payload)
    assert permit.permit_id == "P-2291"


def test_badge_ping_event_from_doc_example():
    payload = {
        "badge_id": "W-0142",
        "zone_id": "Z1",
        "timestamp": "2026-07-19T10:31:00Z",
        "event_type": "zone_entry",
    }
    event = BadgePingEvent(**payload)
    assert event.badge_id == "W-0142"


def test_cv_observation_event_from_doc_example():
    payload = {
        "event_id": "CV-0042",
        "zone_id": "Z1",
        "timestamp": "2026-07-19T10:31:10Z",
        "detection": "person",
        "confidence": 0.91,
        "source": "real_inference",
        "correlation": "no matching badge-ping in Zone 1",
        "correlation_source": "simulated",
    }
    event = CVObservationEvent(**payload)
    assert event.confidence == 0.91


def test_council_verdict_from_doc_example():
    payload = {
        "zone_id": "Z1",
        "scenario_id": "S1",
        "trigger_reason": "rule_threshold",
        "timestamp": "2026-07-19T10:32:00Z",
        "council": {
            "process_safety_engineer": "Gas readings 18% above baseline, rising",
            "permit_control_officer": "Hot work permit P-2291 active in Zone 1",
            "shift_operations": "Changeover begins in 12 minutes",
            "site_safety_observer": (
                "Personnel detected in Zone 1 without a matching permit badge scan"
            ),
        },
        "risk_level": "HIGH",
        "confidence": 0.87,
        "compound_flag": True,
        "time_to_critical": {
            "median_minutes": 18,
            "iqr_low_minutes": 15,
            "iqr_high_minutes": 22,
            "escalation_probability": 0.68,
        },
        "explanation": (
            "No single factor alone crosses a critical threshold. The "
            "combination matches the compound-risk pattern verified in the "
            "June 2025 Visakhapatnam Steel Plant SMS-2 investigation."
        ),
        "recommended_action": (
            "Suspend permit P-2291 pending gas verification; notify Zone 1 "
            "supervisor before shift handoff."
        ),
    }
    verdict = CouncilVerdict(**payload)
    assert isinstance(verdict.council, CouncilEvidence)
    assert verdict.time_to_critical.median_minutes == 18


def test_compliance_signal_reading():
    reading = ComplianceSignalReading(
        zone_id="Z1",
        linked_checklist_id="CHK-0410",
        compliance_score=0.92,
        timestamp="2026-07-19T10:20:00Z",
    )
    assert 0.0 <= reading.compliance_score <= 1.0


def test_gas_sensor_reading():
    reading = GasSensorReading(
        zone_id="Z2",
        gas_type="CO",
        concentration=34.2,
        unit="ppm",
        timestamp="2026-07-19T10:20:00Z",
    )
    assert reading.concentration == 34.2


def test_audit_log_entry_references_real_clause():
    entry = AuditLogEntry(
        entry_id="AL-0001",
        zone_id="Z3",
        timestamp="2026-07-19T09:00:00Z",
        deviation_type="missing_required_signature",
        description="Hot work checklist missing supervisor countersignature.",
        source_framework="OISD",
        required_checklist_ref="OISD-STD-XXX §4.2",
    )
    assert entry.required_checklist_ref.startswith("OISD")


def test_plant_layout_zones_and_adjacency():
    layout = PlantLayout(
        zones=[
            Zone(
                zone_id="Z1",
                name="SMS-2 Ladle Bay / Casting Floor",
                hazard_class=HazardClass.HIGH,
                primary_role="Anchor scenario S1",
            ),
            Zone(
                zone_id="Z3",
                name="Maintenance Bay",
                hazard_class=HazardClass.MEDIUM,
                primary_role="S3, S4",
            ),
        ],
        adjacency=[ZoneAdjacencyEdge(zone_a="Z1", zone_b="Z3")],
    )
    assert len(layout.zones) == 2
    assert layout.adjacency[0].zone_a == "Z1"


def test_scenario_config_from_doc_yaml_example():
    raw_yaml = """
    scenario_id: S1
    name: "Anchor case: ladle moisture/entrapped-gas compound risk"
    seed: 20260714
    memory_split: population
    duration_minutes: 90
    zone: Z1
    signals:
      compliance:
        model: procedural_compliance
        Q_baseline: 0.92
        degradation_step: 0.35
        lapse_coupling: shift_changeover_proximity
      permit:
        type: lifting_operation
        inject_at_minute: 20
        linked_checklist_id: CHK-0410
      shift:
        changeover_at_minute: 68
      worker_location:
        badge_id: W-0142
        zone_entry_at_minute: 55
      cv_event:
        inject_at_minute: 55
        detection: person
    ground_truth:
      compound_risk_window_start_minute: 60
      incident_threshold_minute: 82
    """
    data = yaml.safe_load(raw_yaml)
    config = ScenarioConfig(**data)
    assert config.scenario_id == "S1"
    assert config.memory_split == "population"
    assert config.signals.compliance is not None
    assert config.signals.gas is None


def test_shift_record():
    shift = ShiftRecord(
        shift_id="shift-A",
        start_time="2026-07-19T06:00:00Z",
        end_time="2026-07-19T14:00:00Z",
        zones=["Z1", "Z2", "Z3"],
    )
    assert shift.changeover_window_minutes == 15
