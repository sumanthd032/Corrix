"""Spatial risk propagation, per CORRIX_PROJECT.md's compound-risk thesis
extended across space: a breadth-first walk over the zone-adjacency graph
(§7) from an affected zone, estimating how a compound risk in one zone
could migrate to its neighbours.

The estimate is deliberately simple and explainable, not a gas-dispersion
CFD: spread risk decays with hop distance from the source and is weighted
by each neighbour's own hazard class, since a high-hazard zone (a gas
vault, a ladle bay) is far more susceptible to a spreading release than a
low-hazard walkway. It answers the operational question "if this doesn't
get contained, where does it go next", which single-zone detection never
asks.
"""

from collections import deque
from dataclasses import dataclass

from app.schemas import PlantLayout

HOP_DECAY = 0.55
HAZARD_SUSCEPTIBILITY = {"high": 1.0, "medium": 0.65, "low": 0.35}
MAX_HOPS = 2


@dataclass
class PropagationZone:
    zone_id: str
    hops: int
    score: float  # 0..1, estimated risk of the compound event spreading here


def _adjacency(layout: PlantLayout) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {z.zone_id: [] for z in layout.zones}
    for edge in layout.adjacency:
        adj[edge.zone_a].append(edge.zone_b)
        adj[edge.zone_b].append(edge.zone_a)
    return adj


def predict_risk_propagation(
    layout: PlantLayout, source_zone_id: str, max_hops: int = MAX_HOPS
) -> list[PropagationZone]:
    """The zones a compound risk in `source_zone_id` could spread to within
    `max_hops` adjacency hops, each with an estimated spread score. The
    source itself is excluded. Ordered most-at-risk first."""
    adj = _adjacency(layout)
    if source_zone_id not in adj:
        return []

    hazard = {z.zone_id: z.hazard_class.value for z in layout.zones}

    dist: dict[str, int] = {source_zone_id: 0}
    queue: deque[str] = deque([source_zone_id])
    while queue:
        current = queue.popleft()
        if dist[current] >= max_hops:
            continue
        for neighbour in adj[current]:
            if neighbour not in dist:
                dist[neighbour] = dist[current] + 1
                queue.append(neighbour)

    out: list[PropagationZone] = []
    for zone_id, hops in dist.items():
        if hops == 0:
            continue
        susceptibility = HAZARD_SUSCEPTIBILITY.get(hazard.get(zone_id, "low"), 0.35)
        score = round((HOP_DECAY ** hops) * susceptibility, 3)
        out.append(PropagationZone(zone_id=zone_id, hops=hops, score=score))

    out.sort(key=lambda p: (-p.score, p.zone_id))
    return out
