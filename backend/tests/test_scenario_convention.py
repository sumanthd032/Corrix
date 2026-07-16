"""The data/scenarios/ folder convention: a real YAML file on disk loads
and validates against ScenarioConfig with zero manual patching."""

from pathlib import Path

import yaml

from app.schemas import ScenarioConfig

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"


def test_s1_example_yaml_loads_and_validates():
    raw = (SCENARIOS_DIR / "s1_anchor.example.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    config = ScenarioConfig(**data)
    assert config.scenario_id == "S1"
    assert config.memory_split == "population"
    assert config.ground_truth.incident_threshold_minute == 82
