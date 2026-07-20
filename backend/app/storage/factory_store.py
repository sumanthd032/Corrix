"""Neo4j persistence for `FactoryProfile` (Bring Your Own Factory), per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 2. Reuses the same Neo4j/AuraDB
instance and driver as the Regulatory Intelligence graph and the memory
loop (`app/memory/exemplar_store.get_shared_driver`), no new
infrastructure.

Deliberately uses a distinct `FactoryZone` node label, not `Zone`. The
regulatory graph already owns a `:Zone` label with a uniqueness
constraint on `zone_id` for the static demo's eight zones (Z1-Z8). A
user-onboarded factory's own zone IDs are chosen by them, not
namespaced, so writing them as `:Zone` nodes risks either violating
that constraint or, worse, `MERGE`-ing onto the real demo zone's node
and silently corrupting its regulatory data if a user happens to name
a zone "Z1". `FactoryZone` nodes are instead keyed by the composite
(factory_id, zone_id), fully isolated from the regulatory graph.
"""

import json
from datetime import datetime

from neo4j import Driver

from app.memory.exemplar_store import get_shared_driver
from app.schemas.factory import FactoryProfile
from app.schemas.shift import ShiftRecord
from app.schemas.zone import HazardClass, PlantLayout, Zone, ZoneAdjacencyEdge

FACTORY_CONSTRAINTS = [
    "CREATE CONSTRAINT factory_id_unique IF NOT EXISTS "
    "FOR (f:Factory) REQUIRE f.factory_id IS UNIQUE",
    "CREATE CONSTRAINT factory_zone_composite_unique IF NOT EXISTS "
    "FOR (z:FactoryZone) REQUIRE (z.factory_id, z.zone_id) IS UNIQUE",
]


def ensure_factory_schema(driver: Driver) -> None:
    """Idempotent, per the same `IF NOT EXISTS` discipline
    `app/regulatory/neo4j_schema.ensure_schema` already uses."""
    with driver.session() as session:
        for statement in FACTORY_CONSTRAINTS:
            session.run(statement)


def save_factory(profile: FactoryProfile, driver: Driver | None = None) -> None:
    driver = driver or get_shared_driver()
    ensure_factory_schema(driver)

    shift_pattern_json = json.dumps(
        [s.model_dump(mode="json") for s in profile.shift_pattern]
    )

    with driver.session() as session:
        session.run(
            """
            MERGE (f:Factory {factory_id: $factory_id})
            SET f.name = $name,
                f.industry = $industry,
                f.location = $location,
                f.permit_types_in_use = $permit_types_in_use,
                f.shift_pattern_json = $shift_pattern_json,
                f.data_source = $data_source,
                f.created_at = $created_at
            """,
            factory_id=profile.factory_id,
            name=profile.name,
            industry=profile.industry,
            location=profile.location,
            permit_types_in_use=profile.permit_types_in_use,
            shift_pattern_json=shift_pattern_json,
            data_source=profile.data_source,
            created_at=profile.created_at.isoformat(),
        )

        for zone in profile.layout.zones:
            session.run(
                """
                MATCH (f:Factory {factory_id: $factory_id})
                MERGE (z:FactoryZone {factory_id: $factory_id, zone_id: $zone_id})
                SET z.name = $name,
                    z.hazard_class = $hazard_class,
                    z.primary_role = $primary_role,
                    z.is_confined_space = $is_confined_space,
                    z.is_assembly_point = $is_assembly_point
                MERGE (f)-[:HAS_ZONE]->(z)
                """,
                factory_id=profile.factory_id,
                zone_id=zone.zone_id,
                name=zone.name,
                hazard_class=zone.hazard_class.value,
                primary_role=zone.primary_role,
                is_confined_space=zone.is_confined_space,
                is_assembly_point=zone.is_assembly_point,
            )

        for edge in profile.layout.adjacency:
            session.run(
                """
                MATCH (za:FactoryZone {factory_id: $factory_id, zone_id: $zone_a})
                MATCH (zb:FactoryZone {factory_id: $factory_id, zone_id: $zone_b})
                MERGE (za)-[:ADJACENT_TO]->(zb)
                """,
                factory_id=profile.factory_id,
                zone_a=edge.zone_a,
                zone_b=edge.zone_b,
            )


def load_factory(factory_id: str, driver: Driver | None = None) -> FactoryProfile | None:
    driver = driver or get_shared_driver()

    with driver.session() as session:
        factory_record = session.run(
            """
            MATCH (f:Factory {factory_id: $factory_id})
            RETURN f.name AS name,
                   f.industry AS industry,
                   f.location AS location,
                   f.permit_types_in_use AS permit_types_in_use,
                   f.shift_pattern_json AS shift_pattern_json,
                   f.data_source AS data_source,
                   f.created_at AS created_at
            """,
            factory_id=factory_id,
        ).single()

        if factory_record is None:
            return None

        zone_rows = session.run(
            """
            MATCH (:Factory {factory_id: $factory_id})-[:HAS_ZONE]->(z:FactoryZone)
            RETURN z.zone_id AS zone_id,
                   z.name AS name,
                   z.hazard_class AS hazard_class,
                   z.primary_role AS primary_role,
                   z.is_confined_space AS is_confined_space,
                   z.is_assembly_point AS is_assembly_point
            ORDER BY z.zone_id
            """,
            factory_id=factory_id,
        )
        zones = [
            Zone(
                zone_id=row["zone_id"],
                name=row["name"],
                hazard_class=HazardClass(row["hazard_class"]),
                primary_role=row["primary_role"],
                is_confined_space=row["is_confined_space"],
                is_assembly_point=row["is_assembly_point"],
            )
            for row in zone_rows
        ]

        edge_rows = session.run(
            """
            MATCH (za:FactoryZone {factory_id: $factory_id})-[:ADJACENT_TO]->(zb:FactoryZone)
            RETURN za.zone_id AS zone_a, zb.zone_id AS zone_b
            ORDER BY za.zone_id, zb.zone_id
            """,
            factory_id=factory_id,
        )
        adjacency = [
            ZoneAdjacencyEdge(zone_a=row["zone_a"], zone_b=row["zone_b"]) for row in edge_rows
        ]

    shift_pattern = [
        ShiftRecord(**s) for s in json.loads(factory_record["shift_pattern_json"])
    ]

    return FactoryProfile(
        factory_id=factory_id,
        name=factory_record["name"],
        industry=factory_record["industry"],
        location=factory_record["location"],
        layout=PlantLayout(zones=zones, adjacency=adjacency),
        permit_types_in_use=factory_record["permit_types_in_use"],
        shift_pattern=shift_pattern,
        data_source=factory_record["data_source"],
        created_at=datetime.fromisoformat(factory_record["created_at"]),
    )
