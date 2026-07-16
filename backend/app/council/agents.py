"""The four Safety Council evidence agents, per CORRIX_PROJECT.md §6.1.

Each agent is constructed with an explicit `bound_servers` list — the
only MCP server object(s) its real-world counterpart would have. This is
what makes the silo constraint checkable by construction: `bound_tool_names`
inspects each server's actual registered tools (not the agent's prompt),
so a test can assert, for example, that the Process Safety Engineer's
bound tools never include anything from the Permit/Shift server.

For Step 4, agents reason over a hand-fed evidence string (Council DoD:
"a hardcoded S1-shaped JSON blob is enough to start") rather than making
live MCP calls themselves — the MCP binding exists and is verified now;
wiring agents to call their own bound tools live is Step 9 integration
work once there's a running app state to query.
"""

from dataclasses import dataclass, field

from mcp.server.fastmcp import FastMCP

from app.council.llm_client import LLMResponse, chat_completion
from app.mcp_servers import cv_observation, permit_shift, sensor_stream, worker_location


def _tool_names(server: FastMCP) -> list[str]:
    return sorted(t.name for t in server._tool_manager.list_tools())


# Appended to every persona's system prompt. Without this, agents tend to
# paraphrase their report into vague reassurance ("no issues reported"),
# dropping the exact IDs and figures another agent's report also
# references — and it's exactly those shared identifiers (a permit's
# linked_checklist_id matching the checklist a sensor reading is tied to,
# a badge ID matching a permit's zone) that let the Chair, seeing all
# four reports, connect a compound pattern no single agent could.
PRESERVE_DETAIL_INSTRUCTION = (
    " Always include every exact identifier (permit IDs, checklist IDs, "
    "badge IDs), exact numeric value, and exact timing mentioned in the "
    "raw data you're given — never paraphrase them away or replace them "
    "with vague language like 'no issues' or 'within normal parameters'. "
    "Another reviewer with a different, non-overlapping view of this "
    "situation depends on those exact details to cross-reference against "
    "their own."
)


@dataclass
class EvidenceAgent:
    display_name: str
    persona_key: str  # matches a field name on CouncilEvidence
    system_prompt: str
    bound_servers: list[FastMCP] = field(default_factory=list)

    @property
    def bound_tool_names(self) -> list[str]:
        names: list[str] = []
        for server in self.bound_servers:
            names.extend(_tool_names(server))
        return names

    def run(self, evidence_text: str) -> LLMResponse:
        return chat_completion(self.system_prompt, evidence_text, max_tokens=150)


PROCESS_SAFETY_ENGINEER = EvidenceAgent(
    display_name="Process Safety Engineer",
    persona_key="process_safety_engineer",
    system_prompt=(
        "You are the Process Safety Engineer on an industrial Safety Council. "
        "You evaluate whether the physical/process condition in a zone is "
        "abnormal, using only sensor/compliance data. You have no visibility "
        "into permits, shift schedules, or worker location — do not reference "
        "them. If the raw data mentions gas readings, report O2 first, then "
        "flammable gas (LEL%), then toxic gas (CO/H2S), in that order, "
        "matching OSHA confined-space testing order. Respond in one concise, "
        "factual sentence, in the voice of a process safety engineer."
    )
    + PRESERVE_DETAIL_INSTRUCTION,
    bound_servers=[sensor_stream.server],
)

PERMIT_CONTROL_OFFICER = EvidenceAgent(
    display_name="Permit Control Officer",
    persona_key="permit_control_officer",
    system_prompt=(
        "You are the Permit Control Officer on an industrial Safety Council. "
        "You evaluate whether authorized work is compatible with current "
        "conditions, using only permit-to-work data. You have no visibility "
        "into sensor readings, shift changeover timing, or worker location — "
        "do not reference them. Respond in one concise, factual sentence, in "
        "the voice of a permit control officer."
    )
    + PRESERVE_DETAIL_INSTRUCTION,
    bound_servers=[permit_shift.server],
)

SHIFT_OPERATIONS = EvidenceAgent(
    display_name="Shift Operations",
    persona_key="shift_operations",
    system_prompt=(
        "You are the Shift Operations lead on an industrial Safety Council. "
        "You evaluate whether human-factors risk is elevated right now, using "
        "only shift roster and changeover data. You have no visibility into "
        "sensor readings, permit details, or worker location — do not "
        "reference them. Respond in one concise, factual sentence, in the "
        "voice of a shift operations lead."
    )
    + PRESERVE_DETAIL_INSTRUCTION,
    bound_servers=[permit_shift.server],
)

SITE_SAFETY_OBSERVER = EvidenceAgent(
    display_name="Site Safety Observer",
    persona_key="site_safety_observer",
    system_prompt=(
        "You are the Site Safety Observer on an industrial Safety Council. "
        "You evaluate whether site-observation data (CV detections and worker "
        "location) corroborates or contradicts the other evidence. You have "
        "no visibility into sensor readings, permit details, or shift "
        "schedules — do not reference them. Respond in one concise, factual "
        "sentence, in the voice of a site safety observer."
    )
    + PRESERVE_DETAIL_INSTRUCTION,
    bound_servers=[cv_observation.server, worker_location.server],
)

ALL_AGENTS = [
    PROCESS_SAFETY_ENGINEER,
    PERMIT_CONTROL_OFFICER,
    SHIFT_OPERATIONS,
    SITE_SAFETY_OBSERVER,
]
