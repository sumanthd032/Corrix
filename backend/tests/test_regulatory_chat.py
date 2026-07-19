"""The Regulatory Intelligence chat drawer's real backend endpoint.

Before this, the frontend's `sendChatMessage` action only appended the
user's own typed text to local state and never called anything: no
loading state, no reply, no error, on either a live or unreachable
backend. This endpoint, and the frontend wiring that calls it, close
that gap. Verified here against the live Neo4j substrate, the same one
`test_regulatory_retrieval.py` already proves works."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_regulatory_chat_returns_a_real_checkable_citation():
    response = client.post(
        "/api/regulatory-chat",
        json={"question": "What precautions are required for explosive or flammable gas?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"]
    assert data["citations"]
    citation = data["citations"][0]
    assert citation["sectionNumber"]
    assert citation["sourceDocument"]
    assert isinstance(citation["isSupplementary"], bool)


def test_regulatory_chat_on_a_question_with_no_match_is_honest_not_a_500():
    response = client.post(
        "/api/regulatory-chat",
        json={"question": "xyzzy nonexistent gibberish query with no plausible match"},
    )
    assert response.status_code == 200
    data = response.json()
    # A vector index always returns *something* by score, so this
    # mainly guards the shape stays valid even for a low-relevance
    # question rather than that it returns literally zero citations.
    assert "answer" in data
    assert "citations" in data
