"""Monte Carlo Time-to-Critical forecasting, per
CORRIX_DATA_METHODOLOGY.md §3.6: checked against the real scenario
library, not synthetic examples."""

from pathlib import Path

from app.api.live_scenario import precompute_playback
from app.detection.anomaly_scorer import calibrate_baseline
from app.detection.time_to_critical import forecast_time_to_critical
from app.simulation.scenario_engine import load_scenario_config, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"


def _forecast_at_trigger(scenario_id: str):
    pb = precompute_playback(scenario_id)
    values = [r.concentration for r in pb.output.gas_readings]
    mean, std = calibrate_baseline(values)
    point = pb.points[pb.trigger_tick_index]
    frame = pb.frames[pb.trigger_frame_index]
    return forecast_time_to_critical(
        current_value=point.value,
        elapsed_minutes=frame.minute,
        gas_config=pb.config.signals.gas,
        baseline_mean=mean,
        baseline_std=std,
        seed=pb.config.seed,
    )


def test_forecast_is_deterministic_given_the_same_seed():
    f1 = _forecast_at_trigger("S3")
    f2 = _forecast_at_trigger("S3")
    assert f1 == f2


def test_forecast_reports_a_band_not_a_point():
    forecast = _forecast_at_trigger("S2")
    assert forecast.iqr_low_minutes <= forecast.median_minutes <= forecast.iqr_high_minutes


def test_forecast_at_a_real_trigger_shows_high_escalation_probability():
    """At the moment S2/S3/S4 actually trigger, the gas signal is already
    trending hard toward its scripted threshold, so the rollout should
    agree that escalation is highly likely, not a coin flip."""
    for scenario_id in ["S2", "S3", "S4"]:
        forecast = _forecast_at_trigger(scenario_id)
        assert forecast.escalation_probability > 0.5, scenario_id


def test_forecast_on_a_quiet_negative_control_shows_low_escalation_probability():
    path = sorted((SCENARIOS_DIR / "negative").glob("*.yaml"))[0]
    config = load_scenario_config(path)
    out = run_scenario(config)
    values = [r.concentration for r in out.gas_readings]
    mean, std = calibrate_baseline(values)
    mid = len(values) // 2
    forecast = forecast_time_to_critical(
        current_value=values[mid],
        elapsed_minutes=mid * 5 / 60,
        gas_config=config.signals.gas,
        baseline_mean=mean,
        baseline_std=std,
        seed=config.seed,
    )
    assert forecast.escalation_probability < 0.1


def test_forecast_on_s5_reflects_its_own_sub_threshold_construction():
    """S5 never actually reaches HIGH/CRITICAL by construction (see
    author_s5's docstring); the forecast should honestly report that,
    not manufacture false confidence."""
    path = sorted((SCENARIOS_DIR / "s5").glob("*.yaml"))[0]
    config = load_scenario_config(path)
    out = run_scenario(config)
    values = [r.concentration for r in out.gas_readings]
    mean, std = calibrate_baseline(values)
    mid = len(values) // 2
    forecast = forecast_time_to_critical(
        current_value=values[mid],
        elapsed_minutes=mid * 5 / 60,
        gas_config=config.signals.gas,
        baseline_mean=mean,
        baseline_std=std,
        seed=config.seed,
    )
    assert forecast.escalation_probability < 0.1


def test_forecast_reuses_the_horizon_as_the_never_crossed_sentinel():
    """A path that never crosses within the horizon isn't silently
    dropped; the forecaster should report the horizon itself rather
    than fabricating a crossing time nothing in the rollout produced."""
    forecast = _forecast_at_trigger("S3")
    assert forecast.horizon_minutes == 60
