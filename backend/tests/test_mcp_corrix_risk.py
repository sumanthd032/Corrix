"""Corrix Risk MCP server: the outward-facing half of the dual-role MCP
story (CORRIX_PROJECT.md §7.2). Behavior is checked two ways here. The
in-process tool calls below match the pattern every other MCP server in
this project uses, but Step 9's Definition of Done is explicit that this
particular server also needs a real external client round trip, since
it is the one server in this package meant to run as a standalone,
independently-reachable process rather than be consumed in-process by
the Council. That round trip lives in
test_mcp_corrix_risk_external_client.py."""

import json

import pytest

from app.mcp_servers.corrix_risk import _get_driver, server
from app.state.live_risk_state import (
    ensure_live_risk_state_schema,
    update_zone_risk_state,
    wipe_all_live_risk_state,
)


def _content_json(result):
    return json.loads(result[0].text)


@pytest.fixture(autouse=True)
def _clean_live_risk_state():
    driver = _get_driver()
    ensure_live_risk_state_schema(driver)
    wipe_all_live_risk_state(driver)
    yield
    wipe_all_live_risk_state(driver)


@pytest.mark.anyio
async def test_list_zones_returns_the_real_plant_layout():
    result = await server.call_tool("list_zones", {})
    data = _content_json(result)
    zone_ids = {z["zone_id"] for z in data["zones"]}
    assert "Z1" in zone_ids
    assert len(zone_ids) >= 5


@pytest.mark.anyio
async def test_unknown_zone_id_is_reported_honestly():
    result = await server.call_tool("get_zone_compound_risk", {"zone_id": "Z999"})
    data = _content_json(result)
    assert "error" in data


@pytest.mark.anyio
async def test_zone_with_no_verdict_yet_is_reported_honestly_not_faked_safe():
    result = await server.call_tool("get_zone_compound_risk", {"zone_id": "Z1"})
    data = _content_json(result)
    assert data["has_verdict"] is False


@pytest.mark.anyio
async def test_zone_with_a_stored_verdict_returns_the_councils_own_judgment():
    update_zone_risk_state(
        _get_driver(),
        zone_id="Z1",
        risk_level="HIGH",
        confidence=0.81,
        compound_flag=True,
        trigger_reason="rule_threshold",
        explanation="Zone 1 gas concentration crossed the CRITICAL threshold during an active hot-work permit.",
        recommended_action="Evacuate Zone 1 immediately via the nearest marked route.",
        scenario_id="S1",
    )
    result = await server.call_tool("get_zone_compound_risk", {"zone_id": "Z1"})
    data = _content_json(result)
    assert data["has_verdict"] is True
    assert data["risk_level"] == "HIGH"
    assert data["compound_flag"] is True
    assert "hot-work" in data["explanation"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
