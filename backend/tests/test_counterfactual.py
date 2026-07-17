"""Counterfactual Replay, per CORRIX_BUILD_PLAN.md Step 8: checked
against the real scenario library, not synthetic data."""

import pytest

from app.api.counterfactual import build_replay_timeline


@pytest.mark.parametrize("scenario_id", ["S1", "S2", "S3", "S4"])
def test_replay_timeline_builds_for_every_authored_scenario(scenario_id):
    timeline = build_replay_timeline(scenario_id)
    assert timeline.scenario_id == scenario_id
    assert len(timeline.frames) > 0
    assert timeline.frames == sorted(timeline.frames, key=lambda f: f.minute)


def test_corrix_path_never_escalates_later_than_the_legacy_path():
    """The whole point of the comparison: Corrix's compound awareness
    (permit conflict included) can only catch things at least as early
    as a legacy, signal-only system, never later."""
    for scenario_id in ["S1", "S2", "S3", "S4"]:
        timeline = build_replay_timeline(scenario_id)
        if timeline.legacy_first_escalation_minute is None:
            continue
        assert timeline.corrix_first_escalation_minute is not None
        assert timeline.corrix_first_escalation_minute <= timeline.legacy_first_escalation_minute


def test_replay_is_deterministic_given_the_same_seed():
    t1 = build_replay_timeline("S3")
    t2 = build_replay_timeline("S3")
    assert [f.corrix_risk_level for f in t1.frames] == [f.corrix_risk_level for f in t2.frames]
    assert [f.legacy_risk_level for f in t1.frames] == [f.legacy_risk_level for f in t2.frames]


def test_at_least_one_scenario_shows_corrix_catching_it_earlier():
    """S2/S3/S4's permit-conflict path genuinely buys lead time over the
    legacy path. This is the concrete proof, not just a mechanism check."""
    found_a_gap = False
    for scenario_id in ["S1", "S2", "S3", "S4"]:
        timeline = build_replay_timeline(scenario_id)
        if (
            timeline.corrix_first_escalation_minute is not None
            and timeline.legacy_first_escalation_minute is not None
            and timeline.corrix_first_escalation_minute < timeline.legacy_first_escalation_minute
        ):
            found_a_gap = True
    assert found_a_gap
