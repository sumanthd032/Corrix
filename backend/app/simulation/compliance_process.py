"""S1's procedural-compliance degradation process, per
CORRIX_DATA_METHODOLOGY.md §4 and §2. Deliberately NOT the OU gas model
(gas_process.py) — the real, verified anchor incident's mechanism is a
procedural/human-factors lapse, not a rising ambient concentration, and
forcing it into the gas model's shape would misrepresent the incident.

Q(t) = Q_baseline - p_lapse(t) * degradation_step

p_lapse(t) is coupled to shift-changeover proximity (§4.1): the model
captures that changeover pressure both *causes* a lapse and *independently*
elevates operational risk. A lapse is sampled once per tick (Bernoulli);
once sampled, Q permanently drops by `degradation_step` (floored at 0) and
no further lapses are sampled for the remainder of the run — this models
the single pre-lift moisture/dryness check the scenario is about, not a
repeatedly-degrading process.
"""

from datetime import datetime, timedelta

import numpy as np

from app.schemas import ComplianceSignalReading


def lapse_probability(
    t_minute: float,
    changeover_at_minute: float,
    p_base: float = 0.0002,
    p_boost: float = 0.15,
    window_minutes: float = 20.0,
) -> float:
    """Per-tick lapse probability, elevated near shift-changeover proximity
    (§4.1) — a documented human-factors risk driver."""
    distance = abs(t_minute - changeover_at_minute)
    if distance <= window_minutes:
        proximity = 1.0 - distance / window_minutes
        return p_base + p_boost * proximity
    return p_base


def run_compliance_process(
    zone_id: str,
    linked_checklist_id: str,
    Q_baseline: float,
    degradation_step: float,
    changeover_at_minute: float,
    duration_minutes: int,
    seed: int,
    dt_seconds: float = 5.0,
    start_time: datetime | None = None,
) -> list[ComplianceSignalReading]:
    """Deterministic, seeded run of the compliance process. Same inputs +
    seed reproduce bit-for-bit identically."""
    rng = np.random.default_rng(seed)
    dt_minutes = dt_seconds / 60.0
    n_steps = int(duration_minutes * 60 / dt_seconds)
    start_time = start_time or datetime(2026, 7, 19, 10, 0, 0)

    Q = Q_baseline
    lapse_already_sampled = False
    readings: list[ComplianceSignalReading] = []
    for i in range(n_steps + 1):
        t_minute = i * dt_minutes
        if not lapse_already_sampled:
            p = lapse_probability(t_minute, changeover_at_minute)
            if rng.random() < p * dt_minutes:
                Q = max(0.0, Q - degradation_step)
                lapse_already_sampled = True
        readings.append(
            ComplianceSignalReading(
                zone_id=zone_id,
                linked_checklist_id=linked_checklist_id,
                compliance_score=round(Q, 4),
                timestamp=start_time + timedelta(minutes=t_minute),
            )
        )
    return readings
