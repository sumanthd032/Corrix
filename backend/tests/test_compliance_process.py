"""S1 compliance process: determinism and changeover-coupling checks."""

from app.simulation.compliance_process import lapse_probability, run_compliance_process


def test_lapse_probability_elevated_near_changeover():
    far = lapse_probability(t_minute=0, changeover_at_minute=68)
    near = lapse_probability(t_minute=65, changeover_at_minute=68)
    assert near > far


def test_run_compliance_process_is_deterministic():
    r1 = run_compliance_process(
        zone_id="Z1", linked_checklist_id="CHK-0410", Q_baseline=0.92,
        degradation_step=0.35, changeover_at_minute=68,
        duration_minutes=90, seed=20260714,
    )
    r2 = run_compliance_process(
        zone_id="Z1", linked_checklist_id="CHK-0410", Q_baseline=0.92,
        degradation_step=0.35, changeover_at_minute=68,
        duration_minutes=90, seed=20260714,
    )
    assert [x.compliance_score for x in r1] == [x.compliance_score for x in r2]


def test_compliance_score_bounded_and_starts_at_baseline():
    readings = run_compliance_process(
        zone_id="Z1", linked_checklist_id="CHK-0410", Q_baseline=0.92,
        degradation_step=0.35, changeover_at_minute=68,
        duration_minutes=90, seed=1,
    )
    assert readings[0].compliance_score == 0.92
    assert all(0.0 <= r.compliance_score <= 1.0 for r in readings)


def test_a_lapse_degrades_the_score_at_most_once():
    readings = run_compliance_process(
        zone_id="Z1", linked_checklist_id="CHK-0410", Q_baseline=0.92,
        degradation_step=0.35, changeover_at_minute=68,
        duration_minutes=90, seed=20260714,
    )
    distinct_scores = sorted({r.compliance_score for r in readings})
    # baseline, and at most one post-lapse value
    assert len(distinct_scores) <= 2
    if len(distinct_scores) == 2:
        assert distinct_scores[0] == round(0.92 - 0.35, 4)
