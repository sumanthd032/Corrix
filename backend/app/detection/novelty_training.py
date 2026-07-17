"""Assembles the novelty detector's training set from the real scenario
library, per §13.2: every tick of every `memory_split: population`
negative-control run is, for free, a reference sample of what a normal
joint plant state looks like. No new data generation needed.
"""

from functools import lru_cache
from pathlib import Path

from app.detection.joint_evidence import build_joint_evidence_series
from app.detection.novelty_detector import NoveltyModel, fit_novelty_model
from app.simulation.plant_layout import load_plant_layout
from app.simulation.scenario_engine import load_scenario_config, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "data" / "scenarios"


def collect_population_negative_control_vectors(
    scenarios_dir: Path = SCENARIOS_DIR,
) -> list[list[float]]:
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
    vectors: list[list[float]] = []
    for path in sorted((scenarios_dir / "negative").glob("*.yaml")):
        config = load_scenario_config(path)
        if config.memory_split != "population":
            continue
        out = run_scenario(config)
        zone = zones_by_id[config.zone]
        vectors.extend(build_joint_evidence_series(zone, out))
    return vectors


def fit_novelty_model_from_library(scenarios_dir: Path = SCENARIOS_DIR) -> NoveltyModel:
    training_vectors = collect_population_negative_control_vectors(scenarios_dir)
    return fit_novelty_model(training_vectors)


@lru_cache
def get_cached_novelty_model() -> NoveltyModel:
    """The live system (scenario triggering, Open Challenge) fits this
    once per process and reuses it: refitting on every scenario switch
    or Open Challenge draw would mean re-running every population
    negative control from scratch on every request, for a model whose
    training set (the authored scenario library) never changes at
    runtime."""
    return fit_novelty_model_from_library()
