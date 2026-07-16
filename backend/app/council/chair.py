"""The Chair synthesis node, per CORRIX_PROJECT.md §6.1/§6.2: the only
node that sees all four evidence agents' structured output, and the only
one that produces the final CouncilVerdict.

The Chair is asked for judgment fields only (risk_level, confidence,
compound_flag, time_to_critical, explanation, recommended_action) —
zone_id/scenario_id/trigger_reason/timestamp/council are assembled
programmatically from values already known to the caller, not trusted to
an LLM's JSON echo. This keeps the one place where correctness actually
matters (which zone, which scenario, whose evidence) deterministic, while
still letting the LLM do the actual synthesis judgment.

`time_to_critical` here is still the Step 4 LLM-estimated placeholder
band. For gas-based zones, the live WebSocket layer (`app/api/websocket.
_convene_council`) overwrites it after synthesis with the real Step 8
Monte Carlo rollout (`app/detection/time_to_critical.py`), which reuses
the simulator's own `step()` function — deliberately done as a
post-synthesis replacement rather than feeding the forecast into the
Chair's own prompt, since the forecast is a deterministic computation,
not a judgment call the LLM should be asked to reproduce or second-guess.
S1's compliance signal isn't an OU process, so it keeps this LLM
estimate — a real, documented scope limit, not an oversight.
"""

import json
from datetime import datetime, timezone

from app.council.llm_client import chat_completion
from app.schemas import CouncilEvidence, CouncilVerdict, TimeToCriticalForecast, TriggerReason

CHAIR_SYSTEM_PROMPT = (
    "You are the Chair of an industrial Safety Council. Four specialist "
    "agents — a Process Safety Engineer, a Permit Control Officer, a Shift "
    "Operations lead, and a Site Safety Observer — have each independently "
    "assessed the same situation from their own narrow perspective, without "
    "seeing each other's evidence. None of them can see the compound picture "
    "you can see.\n\n"
    "A compound risk is a combination of ordinary-looking conditions that, "
    "together, are dangerous — even though no single one of them would "
    "trigger an alarm on its own. This is the central failure mode you "
    "exist to catch: a real worker fatality happened when a physical "
    "condition (entrapped gas in a ladle) coincided with an active lifting "
    "operation and an approaching shift changeover, and no system connected "
    "those facts in time. Treat any case where an active permit, elevated "
    "or degrading process/compliance readings, an imminent shift changeover, "
    "and a worker's physical presence all coincide in the same zone as at "
    "least HIGH risk with compound_flag true, even if each individual "
    "reading looks moderate — the danger is in the coincidence, not in any "
    "one number. Only rate SAFE or CAUTION when the evidence genuinely "
    "shows no meaningful overlap between conditions (e.g. no active permit, "
    "or the compliance/process signal is still nominal).\n\n"
    "Your job is to synthesize the four reports into one verdict: the risk "
    "level, whether it's a compound risk, how urgent it is, and what should "
    "be done. Respond with ONLY a single JSON object, no markdown code "
    "fences, no commentary before or after it."
)


class ChairSynthesisError(Exception):
    pass


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ChairSynthesisError(f"no JSON object found in Chair response: {text!r}")
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ChairSynthesisError(f"Chair response was not valid JSON: {candidate!r}") from exc


def _build_user_prompt(
    zone_id: str,
    trigger_reason: TriggerReason,
    evidence: CouncilEvidence,
    override_note: str | None = None,
    memory_context: str | None = None,
) -> str:
    override_block = ""
    if override_note:
        override_block = f"""
A human Safety Officer has paused the Council and added this note — you
must take it into account and reflect it in your explanation and
recommended_action:
"{override_note}"
"""
    memory_block = ""
    if memory_context:
        memory_block = f"""
This case was flagged by the self-improving memory loop, not the rule
threshold or novelty score: the current evidence closely resembles a
documented past miss, described below. Weigh this precedent seriously
even if the current readings look individually unremarkable — that
past case was missed for exactly that reason:
"{memory_context}"
"""
    return f"""Zone: {zone_id}
Trigger reason: {trigger_reason}

Independent agent reports:
- Process Safety Engineer: {evidence.process_safety_engineer}
- Permit Control Officer: {evidence.permit_control_officer}
- Shift Operations: {evidence.shift_operations}
- Site Safety Observer: {evidence.site_safety_observer}
{override_block}{memory_block}
Respond with ONLY this JSON shape:
{{
  "risk_level": "SAFE" | "CAUTION" | "HIGH" | "CRITICAL",
  "confidence": <float 0.0-1.0>,
  "compound_flag": <true if the risk arises specifically from the combination of the above, not any single factor alone, else false>,
  "time_to_critical": {{
    "median_minutes": <float>,
    "iqr_low_minutes": <float>,
    "iqr_high_minutes": <float>,
    "escalation_probability": <float 0.0-1.0>,
    "horizon_minutes": 60
  }},
  "explanation": "<1-3 sentences explaining the compound reasoning>",
  "recommended_action": "<one concrete recommended action>"
}}"""


def synthesize(
    zone_id: str,
    trigger_reason: TriggerReason,
    evidence: CouncilEvidence,
    scenario_id: str | None = None,
    timestamp: datetime | None = None,
    override_note: str | None = None,
    memory_context: str | None = None,
) -> CouncilVerdict:
    timestamp = timestamp or datetime.now(timezone.utc)
    user_prompt = _build_user_prompt(
        zone_id, trigger_reason, evidence, override_note, memory_context
    )
    response = chat_completion(CHAIR_SYSTEM_PROMPT, user_prompt, max_tokens=500)
    data = _extract_json(response.text)

    return CouncilVerdict(
        zone_id=zone_id,
        scenario_id=scenario_id,
        trigger_reason=trigger_reason,
        timestamp=timestamp,
        council=evidence,
        risk_level=data["risk_level"],
        confidence=float(data["confidence"]),
        compound_flag=bool(data["compound_flag"]),
        time_to_critical=TimeToCriticalForecast(**data["time_to_critical"]),
        explanation=data["explanation"],
        recommended_action=data["recommended_action"],
    )
