"""Risk-aware evacuation routing, per CORRIX_DATA_METHODOLOGY.md §8.3."""

from app.detection.evacuation_routing import find_evacuation_route
from app.simulation.plant_layout import load_plant_layout

LAYOUT = load_plant_layout()


def test_route_reaches_a_real_assembly_point():
    route = find_evacuation_route(LAYOUT, {}, "Z1")
    assert route is not None
    assembly_ids = {z.zone_id for z in LAYOUT.zones if z.is_assembly_point}
    assert route.assembly_point_zone_id in assembly_ids
    assert route.path[0] == "Z1"
    assert route.path[-1] == route.assembly_point_zone_id


def test_route_from_an_assembly_point_is_none():
    assert find_evacuation_route(LAYOUT, {}, "Z4") is None
    assert find_evacuation_route(LAYOUT, {}, "Z8") is None


def test_route_avoids_a_critical_intermediate_zone():
    """The Step 8 Definition of Done: a CRITICAL verdict produces a route
    that visibly avoids any other currently-unsafe zone. Z2's two
    shortest paths to an assembly point are equal-cost (Z2-Z3-Z4 and
    Z2-Z7-Z8) — with Z3 healthy, the route goes through it; with Z3
    marked CRITICAL, the route must reroute through Z7 instead."""
    healthy_route = find_evacuation_route(LAYOUT, {}, "Z2")
    assert "Z3" in healthy_route.path

    zone_risk = {"Z3": "CRITICAL"}
    rerouted = find_evacuation_route(LAYOUT, zone_risk, "Z2")
    assert "Z3" not in rerouted.path
    assert rerouted.path == ["Z2", "Z7", "Z8"]


def test_route_avoids_high_risk_zone_too_not_only_critical():
    zone_risk = {"Z3": "HIGH"}
    rerouted = find_evacuation_route(LAYOUT, zone_risk, "Z2")
    assert "Z3" not in rerouted.path


def test_route_still_uses_an_elevated_zone_if_it_is_the_only_path():
    """If every alternative is also elevated (or there is no alternative),
    the search still returns the best available path rather than failing
    outright — a real evacuation instruction beats none."""
    zone_risk = {"Z3": "CRITICAL", "Z7": "CRITICAL"}
    route = find_evacuation_route(LAYOUT, zone_risk, "Z2")
    assert route is not None
    assert route.path[0] == "Z2"


def test_every_zone_has_some_route_to_an_assembly_point():
    assembly_ids = {z.zone_id for z in LAYOUT.zones if z.is_assembly_point}
    for zone in LAYOUT.zones:
        if zone.zone_id in assembly_ids:
            continue
        route = find_evacuation_route(LAYOUT, {}, zone.zone_id)
        assert route is not None, f"{zone.zone_id} has no route to any assembly point"
