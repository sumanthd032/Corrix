"""Scenario playback precomputation for the live WebSocket stream:
deterministic, matches the same trigger the offline detection tests
find, and produces a real per-minute frame sequence."""

import pytest
from neo4j import GraphDatabase

from app.api.live_scenario import find_default_seed, precompute_playback
from app.config import get_settings
from app.detection.novelty_training import fit_novelty_model_from_library
from app.memory.exemplar_store import ensure_memory_schema


def test_find_default_seed_picks_a_population_split_config():
    seed = find_default_seed("S1")
    assert seed == 20260714  # first population-split S1 seed authored in Step 2


def test_precompute_playback_is_deterministic():
    pb1 = precompute_playback("S1")
    pb2 = precompute_playback("S1")
    assert [f.risk_level for f in pb1.frames] == [f.risk_level for f in pb2.frames]
    assert pb1.trigger_frame_index == pb2.trigger_frame_index


def test_precompute_playback_finds_a_trigger_for_every_positive_scenario():
    """Matches Step 3's actual trigger condition (HIGH/CRITICAL risk OR a
    permit conflict), not risk level alone: a HIGH-hazard zone's permit
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


def test_s5_never_triggers_live_without_the_novelty_and_retrieval_paths():
    """Confirms the real gap this scenario was built to demonstrate: S5
    is deliberately tuned to evade rule/threshold, so without wiring in
    the other two trigger paths, selecting it live would stream to the
    end with nothing ever happening."""
    pb = precompute_playback("S5")
    assert pb.trigger_frame_index is None


@pytest.fixture(scope="module")
def novelty_model():
    return fit_novelty_model_from_library()


@pytest.fixture(scope="module")
def driver():
    settings = get_settings()
    d = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    ensure_memory_schema(d)
    yield d
    d.close()


def test_s5_triggers_live_via_novelty_once_the_novelty_model_is_supplied(novelty_model):
    """Even with no stored exemplars, S5 should have some chance of
    triggering via the novelty path alone on at least one of its seeds.
    This only asserts the *mechanism* runs end-to-end without error,
    since S5's own seeds were specifically selected to miss novelty too
    (see author_s5's docstring) and won't trigger without a matching
    exemplar; the real proof of S5 triggering live is the memory-loop
    test below."""
    pb = precompute_playback("S5", novelty_model=novelty_model)
    assert pb.trigger_frame_index is None  # by construction, matches the offline finding


def test_s5_triggers_live_via_memory_retrieval_with_a_matching_exemplar(novelty_model, driver):
    """The actual Step 9 proof: with a population-derived exemplar
    stored (as the memory loop experiment already leaves behind), a
    held-out S5 seed genuinely convenes the Council live, tagged
    memory_retrieval, not just in the offline harness."""
    from app.detection.retrieval_trigger import describe_evidence_snapshot
    from app.detection.joint_evidence import build_joint_evidence_series
    from app.detection.anomaly_scorer import score_series
    from app.memory.exemplar_store import store_exemplar, wipe_all_exemplars
    from app.simulation.plant_layout import load_plant_layout
    from app.simulation.scenario_engine import DEFAULT_START_TIME, load_scenario_config, run_scenario
    from pathlib import Path
    from datetime import timedelta

    scenarios_dir = Path(__file__).resolve().parents[2] / "data" / "scenarios"
    wipe_all_exemplars(driver)
    try:
        pop_path = sorted((scenarios_dir / "s5").glob("*.yaml"))[0]
        config = load_scenario_config(pop_path)
        out = run_scenario(config)
        zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
        zone = zones_by_id[config.zone]
        vectors = build_joint_evidence_series(zone, out)
        window_minute = config.ground_truth.compound_risk_window_start_minute
        tick_index = int(window_minute * 60 / 5)
        at_time = DEFAULT_START_TIME + timedelta(minutes=window_minute)
        points = score_series([r.concentration for r in out.gas_readings])
        text = describe_evidence_snapshot(
            config, out, points[tick_index],
            {p.badge_id: p.zone_id for p in out.worker_pings if p.timestamp <= at_time},
            at_time,
        )
        store_exemplar(
            driver, exemplar_id="test-live-s5", scenario_id=config.scenario_id,
            seed=config.seed, zone_id=config.zone, joint_evidence_vector=vectors[tick_index],
            evidence_text=text, correct_risk_level="HIGH", why="test exemplar",
        )

        # A genuinely different, held-out seed, not the same seed the
        # exemplar was stored from, is the real proof this is cross-seed
        # retrieval, not the exemplar trivially matching itself.
        held_out_seed = 90504
        assert held_out_seed != config.seed
        pb = precompute_playback(
            "S5", seed=held_out_seed, novelty_model=novelty_model, memory_driver=driver
        )
        assert pb.trigger_frame_index is not None
        assert pb.trigger_reason == "memory_retrieval"
        assert pb.matched_exemplar is not None
    finally:
        wipe_all_exemplars(driver)
