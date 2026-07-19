"""REST endpoint for the Regulatory Intelligence chat drawer.

A REST fetch, not a WebSocket message: one-shot request/response Q&A,
the same shape `replay.py` and `evaluation.py` already use for backend-
computed-but-not-streamed data. Reuses the same shared Neo4j driver and
the same `answer_regulatory_question` retrieval function the outward-
facing MCP server and the Council's own regulatory tool already call
(`app/regulatory/retrieval.py`), so the chat drawer answers from the
identical substrate, not a second, parallel implementation.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.memory.exemplar_store import get_shared_driver
from app.regulatory.retrieval import answer_regulatory_question

router = APIRouter()


class RegulatoryChatRequest(BaseModel):
    question: str


@router.post("/api/regulatory-chat")
def post_regulatory_chat(payload: RegulatoryChatRequest) -> dict:
    result = answer_regulatory_question(get_shared_driver(), payload.question)
    if not result["citations"]:
        return {
            "answer": result.get("note") or "No matching regulatory content found for that question.",
            "citations": [],
        }
    return {
        "answer": result["answer"],
        "citations": [
            {
                "framework": c["framework"],
                "sourceDocument": c["source_document"],
                "sectionNumber": c["section_number"],
                "isSupplementary": c["is_supplementary"],
            }
            for c in result["citations"]
        ],
    }
