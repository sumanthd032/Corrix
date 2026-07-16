from enum import Enum

from pydantic import BaseModel


class HazardClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Zone(BaseModel):
    """A single plant zone, per CORRIX_DATA_METHODOLOGY.md §7."""

    zone_id: str
    name: str
    hazard_class: HazardClass
    primary_role: str
    is_confined_space: bool = False
    is_assembly_point: bool = False


class ZoneAdjacencyEdge(BaseModel):
    """One undirected edge in the zone-adjacency graph, per §7's edge list."""

    zone_a: str
    zone_b: str


class PlantLayout(BaseModel):
    """The full eight-zone layout plus its adjacency graph (§7), feeding the
    evacuation-routing algorithm (§8.3) and nothing else."""

    zones: list[Zone]
    adjacency: list[ZoneAdjacencyEdge]
