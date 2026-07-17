"""Verify the agent-silo constraint BY CONSTRUCTION, per CORRIX_PROJECT.md
§6.1 and Step 4's Definition of Done: each agent's bound tool set must
literally not include tools from servers it isn't supposed to see,
checked by inspecting the agent's actual bound tool list, not by reading
its prompt."""

from app.council.agents import (
    PERMIT_CONTROL_OFFICER,
    PROCESS_SAFETY_ENGINEER,
    SHIFT_OPERATIONS,
    SITE_SAFETY_OBSERVER,
)

SENSOR_TOOLS = {"get_zone_readings", "get_anomaly_score"}
PERMIT_SHIFT_TOOLS = {"get_active_permits", "check_permit_conflict", "get_shift_status"}
CV_TOOLS = {"get_recent_detections"}
WORKER_LOCATION_TOOLS = {"get_zone_occupancy"}


def test_process_safety_engineer_only_has_sensor_tools():
    bound = set(PROCESS_SAFETY_ENGINEER.bound_tool_names)
    assert bound == SENSOR_TOOLS
    assert bound.isdisjoint(PERMIT_SHIFT_TOOLS)
    assert bound.isdisjoint(CV_TOOLS)
    assert bound.isdisjoint(WORKER_LOCATION_TOOLS)


def test_permit_control_officer_only_has_permit_shift_tools():
    bound = set(PERMIT_CONTROL_OFFICER.bound_tool_names)
    assert bound == PERMIT_SHIFT_TOOLS
    assert bound.isdisjoint(SENSOR_TOOLS)
    assert bound.isdisjoint(CV_TOOLS)
    assert bound.isdisjoint(WORKER_LOCATION_TOOLS)


def test_shift_operations_only_has_permit_shift_tools():
    bound = set(SHIFT_OPERATIONS.bound_tool_names)
    assert bound == PERMIT_SHIFT_TOOLS
    assert bound.isdisjoint(SENSOR_TOOLS)
    assert bound.isdisjoint(CV_TOOLS)
    assert bound.isdisjoint(WORKER_LOCATION_TOOLS)


def test_site_safety_observer_only_has_cv_and_worker_location_tools():
    bound = set(SITE_SAFETY_OBSERVER.bound_tool_names)
    assert bound == CV_TOOLS | WORKER_LOCATION_TOOLS
    assert bound.isdisjoint(SENSOR_TOOLS)
    assert bound.isdisjoint(PERMIT_SHIFT_TOOLS)


def test_no_two_agents_share_all_the_same_tools():
    """Sanity check that the silo actually differentiates agents: if two
    agents ended up with identical bound tools, the silo would be
    cosmetic, not structural."""
    agents = [
        PROCESS_SAFETY_ENGINEER,
        PERMIT_CONTROL_OFFICER,
        SHIFT_OPERATIONS,
        SITE_SAFETY_OBSERVER,
    ]
    tool_sets = [frozenset(a.bound_tool_names) for a in agents]
    # Permit Control Officer and Shift Operations legitimately share a
    # server per §6.1 ("Shift Operations → Permit/Shift MCP (roster/
    # changeover data only)"); every other pair must differ.
    for i, a in enumerate(agents):
        for j, b in enumerate(agents):
            if i >= j:
                continue
            same_server_pair = {a.persona_key, b.persona_key} == {
                "permit_control_officer",
                "shift_operations",
            }
            if not same_server_pair:
                assert tool_sets[i] != tool_sets[j], (
                    f"{a.display_name} and {b.display_name} unexpectedly "
                    "share identical bound tools"
                )
