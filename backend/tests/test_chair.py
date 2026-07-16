"""The Chair synthesis node: real LLM calls against the hand-crafted
S1-S4 payloads, per Step 4's Definition of Done — feeding a hand-crafted
evidence payload through produces a plausible, well-formed verdict, and
S2-S4 produce sensible, differently-reasoned verdicts too, not just S1."""

import pytest

from app.council.chair import synthesize
from app.council.sample_payloads import ALL_SAMPLE_PAYLOADS
from app.schemas import CouncilEvidence


def _evidence_from_payload(payload: dict) -> CouncilEvidence:
    return CouncilEvidence(
        process_safety_engineer=payload["process_safety_engineer"],
        permit_control_officer=payload["permit_control_officer"],
        shift_operations=payload["shift_operations"],
        site_safety_observer=payload["site_safety_observer"],
    )


@pytest.mark.parametrize("scenario_id", ["S1", "S2", "S3", "S4"])
def test_synthesize_produces_well_formed_compound_verdict(scenario_id):
    payload = ALL_SAMPLE_PAYLOADS[scenario_id]
    evidence = _evidence_from_payload(payload)
    verdict = synthesize(
        zone_id=payload["zone_id"],
        trigger_reason="rule_threshold",
        evidence=evidence,
        scenario_id=scenario_id,
    )
    assert verdict.zone_id == payload["zone_id"]
    assert verdict.scenario_id == scenario_id
    assert verdict.risk_level in ("HIGH", "CRITICAL")
    assert verdict.compound_flag is True
    assert 0.0 <= verdict.confidence <= 1.0
    assert verdict.time_to_critical.median_minutes > 0
    assert len(verdict.explanation) > 0
    assert len(verdict.recommended_action) > 0
    # the Chair's evidence in the verdict is our own assembled data, not
    # an LLM echo — must match exactly
    assert verdict.council.process_safety_engineer == payload["process_safety_engineer"]


def test_verdicts_are_differently_reasoned_not_templated():
    """A plausible failure mode would be the Chair returning the same
    boilerplate explanation regardless of input — confirm the four
    explanations actually differ."""
    explanations = set()
    for scenario_id, payload in ALL_SAMPLE_PAYLOADS.items():
        evidence = _evidence_from_payload(payload)
        verdict = synthesize(
            zone_id=payload["zone_id"],
            trigger_reason="rule_threshold",
            evidence=evidence,
            scenario_id=scenario_id,
        )
        explanations.add(verdict.explanation)
    assert len(explanations) == 4
