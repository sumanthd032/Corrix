"""Live evidence formatters: real data at a trigger moment translates
into grounded, non-fabricated per-agent text."""

from datetime import timedelta

from app.api.live_evidence import (
    format_permit_text,
    format_process_safety_text,
    format_shift_text,
    format_site_safety_text,
)
from app.api.live_scenario import precompute_playback
from app.detection.anomaly_scorer import score_series
from app.schemas import ScenarioConfig, ScenarioGroundTruth, ScenarioSignals
from app.simulation.scenario_engine import DEFAULT_START_TIME


def _signal_values(out):
    if out.gas_readings:
        return [r.concentration for r in out.gas_readings]
    return [r.compliance_score for r in out.compliance_readings]


def test_formatters_produce_grounded_text_at_the_s1_trigger():
    pb = precompute_playback("S1")
    points = score_series(_signal_values(pb.output))
    point = points[pb.trigger_tick_index]
    frame = pb.frames[pb.trigger_frame_index]
    at_time = DEFAULT_START_TIME + timedelta(minutes=frame.minute)

    pse = format_process_safety_text(pb.config, point)
    assert "Z1" in pse
    assert "critical" in pse.lower() or "high" in pse.lower()

    pco = format_permit_text(pb.config, pb.output.permits, at_time)
    assert "CHK-0410" in pco
    assert "lifting_operation" in pco

    so = format_shift_text(pb.output.shifts, pb.config.zone, at_time)
    assert "Z1" in so
    assert "minute" in so

    sso = format_site_safety_text(frame.worker_positions, pb.config.zone)
    assert "W-0142" in sso


def test_permit_text_reports_no_permits_when_none_active():
    config = ScenarioConfig(
        scenario_id="TEST",
        name="t",
        seed=1,
        memory_split="population",
        duration_minutes=10,
        zone="Z9",
        signals=ScenarioSignals(),
        ground_truth=ScenarioGroundTruth(
            compound_risk_window_start_minute=10, incident_threshold_minute=10
        ),
    )
    result = format_permit_text(config, [], DEFAULT_START_TIME)
    assert "No active permits" in result


def test_site_safety_text_reports_no_workers_when_zone_empty():
    result = format_site_safety_text({"W-0001": "Z2"}, "Z9")
    assert "No workers currently detected" in result
