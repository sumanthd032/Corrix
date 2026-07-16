"""Validates the curated Open Challenge combinations ahead of the demo,
per CORRIX_DATA_METHODOLOGY.md §13.5: each one is pre-generated and
pre-validated so the novelty detector is confirmed to handle it
correctly before it's ever drawn live. Run from backend/:
python scripts/validate_open_challenge.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.detection.anomaly_scorer import score_series  # noqa: E402
from app.detection.novelty_training import fit_novelty_model_from_library  # noqa: E402
from app.detection.novelty_detector import find_first_novelty_trigger  # noqa: E402
from app.detection.trigger import find_first_trigger  # noqa: E402
from app.evaluation.harness import _convene_at_tick  # noqa: E402
from app.simulation.open_challenge import CURATED_COMBINATIONS, assemble_open_challenge_config  # noqa: E402
from app.simulation.plant_layout import load_plant_layout  # noqa: E402
from app.simulation.scenario_engine import DEFAULT_START_TIME, run_scenario  # noqa: E402


def main() -> None:
    zones_by_id = {z.zone_id: z for z in load_plant_layout().zones}
    model = fit_novelty_model_from_library()

    all_pass = True
    for i, params in enumerate(CURATED_COMBINATIONS):
        seed = 80000 + i
        config = assemble_open_challenge_config(params, seed)
        out = run_scenario(config)
        zone = zones_by_id[config.zone]
        values = [r.concentration for r in out.gas_readings]

        rule_trigger = find_first_trigger(zone, values, out.permits, DEFAULT_START_TIME)
        novelty_result = find_first_novelty_trigger(model, zone, out)

        rule_idx = rule_trigger.index if rule_trigger else None
        novelty_idx = novelty_result if novelty_result is not None else None

        winner = None
        if rule_idx is not None and (novelty_idx is None or rule_idx <= novelty_idx):
            winner = "rule_threshold"
        elif novelty_idx is not None:
            winner = "novelty"

        trigger_ok = winner == "novelty"

        verdict_ok = False
        risk_level = None
        if trigger_ok:
            points = score_series(values)
            verdict = None
            for attempt in range(6):
                try:
                    verdict = _convene_at_tick(
                        config, out, points[novelty_idx], novelty_idx, trigger_reason="novelty"
                    )
                    break
                except Exception as exc:
                    print(f"  (attempt {attempt + 1} failed: {exc}; retrying in 20s)")
                    time.sleep(20)
            if verdict is not None:
                risk_level = verdict.risk_level
                verdict_ok = verdict.risk_level in ("HIGH", "CRITICAL") and verdict.trigger_reason == "novelty"

        ok = trigger_ok and verdict_ok
        all_pass = all_pass and ok
        print(
            f"{'OK ' if ok else 'FAIL'} {params.label} (zone={params.zone}, "
            f"rule_idx={rule_idx}, novelty_idx={novelty_idx}, winner={winner}, "
            f"verdict_risk_level={risk_level})"
        )

    print("\nAll 5 combinations trigger via novelty and resolve to a real HIGH/CRITICAL verdict:", all_pass)


if __name__ == "__main__":
    main()
