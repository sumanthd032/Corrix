"""Interactive what-if mitigation: re-runs the real Monte Carlo forecaster
under a proposed intervention and returns the before/after time-to-critical,
so a safety officer can see the predicted effect of an action before taking
it, not just react after the fact.

The physics-changing interventions (isolating the source, adding
ventilation) actually modify the gas process's own source term and re-roll
the same simulator the live forecast uses, so the shift in time-to-critical
is a genuine computed result, not a canned number. The procedural
interventions (suspending the permit, evacuating) don't change the gas
physics and say so honestly: they break the compound pattern or remove
exposure rather than slowing the accumulation.
"""

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.live_scenario import precompute_playback
from app.detection.anomaly_scorer import calibrate_baseline
from app.detection.time_to_critical import forecast_time_to_critical
from app.schemas import TimeToCriticalForecast
from app.simulation.scenario_engine import DEFAULT_START_TIME  # noqa: F401  (kept for parity)

router = APIRouter()

# factor: how much the intervention scales the gas source term (a smaller
# source rises more slowly). None means the intervention doesn't touch the
# gas physics, only the procedural/compound context.
INTERVENTIONS: dict[str, dict] = {
    "isolate_source": {"label": "Isolate the gas source", "factor": 0.2},
    "increase_ventilation": {"label": "Increase forced ventilation", "factor": 0.5},
    "suspend_permit": {"label": "Suspend the active permit", "factor": None},
    "evacuate_zone": {"label": "Evacuate the zone", "factor": None},
}

_PROCEDURAL_NOTE = {
    "suspend_permit": (
        "Suspending the permit breaks the compound pattern: the permit-conflict "
        "trigger clears and the situation is no longer a fused risk. The gas trend "
        "itself is unchanged, so the residual risk is the gas anomaly alone."
    ),
    "evacuate_zone": (
        "Evacuating removes personnel exposure. The hazard persists and the "
        "forecast is unchanged, but no worker is in harm's way if it escalates."
    ),
}


class WhatIfRequest(BaseModel):
    scenario_id: str
    intervention: str


def _ttc(f: TimeToCriticalForecast) -> dict:
    return {
        "medianMinutes": f.median_minutes,
        "iqrLowMinutes": f.iqr_low_minutes,
        "iqrHighMinutes": f.iqr_high_minutes,
        "escalationProbability": f.escalation_probability,
        "horizonMinutes": f.horizon_minutes,
    }


@router.post("/api/what-if")
def what_if(req: WhatIfRequest) -> dict:
    intervention = req.intervention
    if intervention not in INTERVENTIONS:
        return {"available": False, "note": f"Unknown intervention '{intervention}'."}

    # Rule-only playback (no novelty/memory needed here): fast, and enough to
    # locate the gas-driven trigger this forecast is anchored to.
    playback = precompute_playback(req.scenario_id)
    config = playback.config
    gas = config.signals.gas

    if gas is None or playback.trigger_frame_index is None or playback.trigger_tick_index is None:
        return {
            "available": False,
            "note": (
                "What-if forecasting applies to a gas-driven zone at its trigger "
                "point (scenarios S2, S3, S4). This scenario has no gas-based "
                "time-to-critical to re-forecast."
            ),
        }

    values = [r.concentration for r in playback.output.gas_readings]
    baseline_mean, baseline_std = calibrate_baseline(values)
    point = playback.points[playback.trigger_tick_index]
    frame = playback.frames[playback.trigger_frame_index]

    before = forecast_time_to_critical(
        current_value=point.value,
        elapsed_minutes=frame.minute,
        gas_config=gas,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
        seed=config.seed,
    )

    spec = INTERVENTIONS[intervention]
    factor = spec["factor"]

    if factor is None:
        after = before
        note = _PROCEDURAL_NOTE[intervention]
    else:
        update = {"a": gas.a * factor}
        if gas.secondary_magnitude is not None:
            update["secondary_magnitude"] = gas.secondary_magnitude * factor
        modified = gas.model_copy(update=update)
        after = forecast_time_to_critical(
            current_value=point.value,
            elapsed_minutes=frame.minute,
            gas_config=modified,
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            seed=config.seed,
        )
        gained = after.median_minutes - before.median_minutes
        esc_before = round(before.escalation_probability * 100)
        esc_after = round(after.escalation_probability * 100)
        note = (
            f"{spec['label']} slows the accumulation: the forecast crossing moves "
            f"from a median of {before.median_minutes:.0f} to {after.median_minutes:.0f} minutes"
            + (f", buying about {gained:.0f} more minutes to act." if gained > 0.5 else ".")
        )
        if esc_before != esc_after:
            note += f" Escalation probability within the hour drops from {esc_before}% to {esc_after}%."

    return {
        "available": True,
        "scenarioId": config.scenario_id,
        "zoneId": config.zone,
        "intervention": intervention,
        "label": spec["label"],
        "before": _ttc(before),
        "after": _ttc(after),
        "note": note,
    }
