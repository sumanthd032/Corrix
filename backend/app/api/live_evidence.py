"""Translates real Step 2/3 data at a trigger moment into the same
per-agent evidence-text shape the hand-crafted sample payloads use
(backend/app/council/sample_payloads.py) — plain factual descriptions,
not pre-written verdicts, consistent with the Council's silo design:
each formatter only ever sees the slice of data its real-world
counterpart would have.
"""

from datetime import datetime

from app.detection.anomaly_scorer import AnomalyPoint
from app.detection.permit_conflict import active_permits_at
from app.schemas import PermitRecord, ScenarioConfig, ShiftRecord


def format_process_safety_text(config: ScenarioConfig, point: AnomalyPoint) -> str:
    if config.signals.gas is not None:
        gas_type = config.signals.gas.gas_type
        return (
            f"Zone {config.zone} {gas_type} reading at {point.value:.1f} "
            f"({point.risk_level.lower()}), statistically {abs(point.z_score):.1f} "
            f"standard deviations from its calibrated baseline."
        )
    return (
        f"Zone {config.zone} procedural-compliance score at {point.value:.2f} "
        f"({point.risk_level.lower()})."
    )


def format_permit_text(config: ScenarioConfig, permits: list[PermitRecord], at_time: datetime) -> str:
    active = active_permits_at(permits, config.zone, at_time)
    if not active:
        return f"No active permits currently on file for Zone {config.zone}."
    parts = []
    for p in active:
        text = f"{p.type.value} permit {p.permit_id}"
        if p.linked_checklist_id:
            text += f", linked to checklist {p.linked_checklist_id}"
        parts.append(text)
    return "; ".join(parts) + " active."


def format_shift_text(shifts: list[ShiftRecord], zone_id: str, at_time: datetime) -> str:
    relevant = [s for s in shifts if zone_id in s.zones and s.start_time <= at_time <= s.end_time]
    if not relevant:
        return f"No shift roster data currently available for Zone {zone_id}."
    nearest = min(relevant, key=lambda s: abs((s.end_time - at_time).total_seconds()))
    minutes_to_changeover = (nearest.end_time - at_time).total_seconds() / 60
    if minutes_to_changeover < 0:
        return f"Zone {zone_id} shift changeover just occurred."
    return f"Zone {zone_id} shift changeover begins in {minutes_to_changeover:.0f} minutes."


def format_site_safety_text(worker_positions: dict[str, str], zone_id: str) -> str:
    present = sorted(badge for badge, z in worker_positions.items() if z == zone_id)
    if not present:
        return f"No workers currently detected in Zone {zone_id}."
    named = ", ".join(present[:3])
    suffix = f" (+{len(present) - 3} more)" if len(present) > 3 else ""
    return f"Badge(s) {named}{suffix} present in Zone {zone_id}."
