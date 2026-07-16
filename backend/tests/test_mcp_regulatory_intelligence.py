"""Regulatory Intelligence MCP server: all three query shapes callable
through the one real interface, per Step 5's Definition of Done."""

import json

import pytest

from app.mcp_servers.regulatory_intelligence import server


def _content_json(result):
    return json.loads(result[0].text)


@pytest.mark.anyio
async def test_qa_tool_returns_real_checkable_citation():
    result = await server.call_tool(
        "query_regulatory_corpus",
        {"question": "What precautions are required for explosive or flammable gas?"},
    )
    data = _content_json(result)
    assert data["citations"][0]["framework"] == "Factories_Act_1948"
    assert data["citations"][0]["section_number"] == "37"


@pytest.mark.anyio
async def test_pattern_lookup_tool_finds_seeded_recurrence():
    result = await server.call_tool(
        "lookup_incident_pattern", {"permit_type": "hot_work", "zone_hazard_class": "high"}
    )
    data = _content_json(result)
    assert data["has_occurred_before"] is True


@pytest.mark.anyio
async def test_compliance_tool_flags_seeded_deviation():
    result = await server.call_tool(
        "check_compliance", {"deviation_type": "missing_lel_reading"}
    )
    data = _content_json(result)
    assert data["deviation_flagged"] is True
    assert data["citation"]["section_number"] == "6.6.10"


@pytest.mark.anyio
async def test_dgms_scoped_qa_is_honest():
    result = await server.call_tool(
        "query_regulatory_corpus", {"question": "mine safety", "framework": "DGMS"}
    )
    data = _content_json(result)
    assert data["answer"] is None
    assert "DGMS" in data["note"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
