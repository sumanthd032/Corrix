"""Scenario playback precomputation for the live WebSocket stream:
deterministic, matches the same trigger the offline detection tests
find, and produces a real per-minute frame sequence."""

from app.api.live_scenario import find_default_seed, precompute_playback


def test_find_default_seed_picks_a_population_split_config():
    seed = find_default_seed("S1")
    assert seed == 20260714  # first population-split S1 seed authored in Step 2


def test_precompute_playback_is_deterministic():
    pb1 = precompute_playback("S1")
    pb2 = precompute_playback("S1")
    assert [f.risk_level for f in pb1.frames] == [f.risk_level for f in pb2.frames]
    assert pb1.trigger_frame_index == pb2.trigger_frame_index


def test_precompute_playback_finds_a_trigger_for_every_positive_scenario():
    """Matches Step 3's actual trigger condition — HIGH/CRITICAL risk OR a
    permit conflict — not risk level alone: a HIGH-hazard zone's permit
    conflict can fire at CAUTION (per the hazard-class rule table), which
    is exactly what happens for S2's confined-space zone here."""
    for scenario_id in ["S1", "S2", "S3", "S4"]:
        pb = precompute_playback(scenario_id)
        assert pb.trigger_frame_index is not None, f"{scenario_id} never triggered"
        trigger_frame = pb.frames[pb.trigger_frame_index]
        assert trigger_frame.should_trigger is True


def test_frames_carry_worker_positions_consistent_with_scripted_zone():
    """The scripted worker for S1 (W-0142) should appear in Zone 1 by the
    time the trigger fires, per the scenario's own scripted timing."""
    pb = precompute_playback("S1")
    trigger_frame = pb.frames[pb.trigger_frame_index]
    assert trigger_frame.worker_positions.get("W-0142") == "Z1"


def test_zone_risk_only_varies_for_the_scenario_zone():
    pb = precompute_playback("S1")
    trigger_frame = pb.frames[pb.trigger_frame_index]
    other_zones = {zid: level for zid, level in trigger_frame.zone_risk.items() if zid != "Z1"}
    assert all(level == "SAFE" for level in other_zones.values())
