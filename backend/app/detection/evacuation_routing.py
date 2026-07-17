"""Risk-aware evacuation routing, per CORRIX_DATA_METHODOLOGY.md §8.3: a
Dijkstra shortest-path search over the zone-adjacency graph (§7) from an
affected zone to the nearest designated safe assembly point, with edges
into any other currently HIGH/CRITICAL zone penalized so the route
actively avoids other unsafe zones rather than just finding the
geometrically shortest path.

Dijkstra, not A* or anything more elaborate: the graph is 8 nodes, and
the simplest algorithm that solves the actual problem is the correct
engineering choice here, not the most impressive-sounding one.
"""

import heapq
from dataclasses import dataclass

from app.schemas import PlantLayout, RiskLevel

BASE_EDGE_WEIGHT = 1.0
# Large enough that any route through a second unsafe zone always loses
# to a route that avoids it entirely, on this 8-node graph's scale.
RISK_PENALTY_FACTOR = 50.0
_ELEVATED = ("HIGH", "CRITICAL")


@dataclass
class EvacuationRoute:
    source_zone_id: str
    assembly_point_zone_id: str
    path: list[str]  # ordered zones, source first, assembly point last


def _build_adjacency(layout: PlantLayout) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {z.zone_id: [] for z in layout.zones}
    for edge in layout.adjacency:
        adjacency[edge.zone_a].append(edge.zone_b)
        adjacency[edge.zone_b].append(edge.zone_a)
    for zone_id in adjacency:
        adjacency[zone_id].sort()  # deterministic tie-breaking
    return adjacency


def _edge_weight(zone_risk: dict[str, RiskLevel], to_zone_id: str) -> float:
    if zone_risk.get(to_zone_id, "SAFE") in _ELEVATED:
        return BASE_EDGE_WEIGHT * RISK_PENALTY_FACTOR
    return BASE_EDGE_WEIGHT


def find_evacuation_route(
    layout: PlantLayout, zone_risk: dict[str, RiskLevel], source_zone_id: str
) -> EvacuationRoute | None:
    """The risk-weighted shortest path from `source_zone_id` to whichever
    assembly point (§7, Z4 Control Room or Z8 Perimeter/Walkway) is
    cheapest to reach, avoiding other elevated-risk zones where a safe
    alternative exists. Returns None if `source_zone_id` is itself an
    assembly point (nothing to route) or is unreachable from any
    assembly point (not possible on this fully-connected 8-zone graph,
    but checked rather than assumed)."""
    assembly_points = {z.zone_id for z in layout.zones if z.is_assembly_point}
    if source_zone_id in assembly_points:
        return None

    adjacency = _build_adjacency(layout)
    distances: dict[str, float] = {source_zone_id: 0.0}
    previous: dict[str, str] = {}
    visited: set[str] = set()
    heap: list[tuple[float, str]] = [(0.0, source_zone_id)]

    while heap:
        dist, current = heapq.heappop(heap)
        if current in visited:
            continue
        visited.add(current)

        if current in assembly_points:
            path = [current]
            while path[-1] != source_zone_id:
                path.append(previous[path[-1]])
            path.reverse()
            return EvacuationRoute(
                source_zone_id=source_zone_id, assembly_point_zone_id=current, path=path
            )

        for neighbor in adjacency[current]:
            if neighbor in visited:
                continue
            candidate = dist + _edge_weight(zone_risk, neighbor)
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                previous[neighbor] = current
                heapq.heappush(heap, (candidate, neighbor))

    return None
