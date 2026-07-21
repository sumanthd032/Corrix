"""Manual round-trip check for Step 2 of the Bring Your Own Factory build
plan: saves a hand-built FactoryProfile with 2 zones and 1 adjacency
edge, reloads it from Neo4j, and asserts equality. Deletes the test
factory node afterward so repeated runs stay idempotent.

Run from backend/: python scripts/verify_factory_store_roundtrip.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.memory.exemplar_store import get_shared_driver
from app.schemas.factory import FactoryProfile
from app.schemas.shift import ShiftRecord
from app.schemas.zone import HazardClass, PlantLayout, Zone, ZoneAdjacencyEdge
from app.storage.factory_store import load_factory, save_factory

TEST_FACTORY_ID = "factory-roundtrip-check"


def build_profile() -> FactoryProfile:
    return FactoryProfile(
        factory_id=TEST_FACTORY_ID,
        name="Roundtrip Test Steelworks",
        industry="steel",
        location="Test City",
        layout=PlantLayout(
            zones=[
                Zone(
                    zone_id="RZ1",
                    name="Test Ladle Bay",
                    hazard_class=HazardClass.HIGH,
                    primary_role="casting",
                    is_confined_space=False,
                    is_assembly_point=False,
                ),
                Zone(
                    zone_id="RZ2",
                    name="Test Control Room",
                    hazard_class=HazardClass.LOW,
                    primary_role="control",
                    is_confined_space=False,
                    is_assembly_point=True,
                ),
            ],
            adjacency=[ZoneAdjacencyEdge(zone_a="RZ1", zone_b="RZ2")],
        ),
        permit_types_in_use=["hot_work", "cold_work"],
        shift_pattern=[
            ShiftRecord(
                shift_id="shift-a",
                start_time=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc),
                changeover_window_minutes=15,
                zones=["RZ1", "RZ2"],
            )
        ],
        data_source="csv",
        created_at=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
    )


def main() -> None:
    driver = get_shared_driver()

    with driver.session() as session:
        session.run(
            "MATCH (f:Factory {factory_id: $id}) "
            "OPTIONAL MATCH (f)-[:HAS_ZONE]->(z:FactoryZone) "
            "DETACH DELETE f, z",
            id=TEST_FACTORY_ID,
        )

    original = build_profile()
    save_factory(original, driver)
    reloaded = load_factory(TEST_FACTORY_ID, driver)

    assert reloaded is not None, "load_factory returned None after save_factory"
    assert reloaded.factory_id == original.factory_id
    assert reloaded.name == original.name
    assert reloaded.industry == original.industry
    assert reloaded.location == original.location
    assert reloaded.permit_types_in_use == original.permit_types_in_use
    assert reloaded.data_source == original.data_source
    assert reloaded.created_at == original.created_at
    assert {z.zone_id for z in reloaded.layout.zones} == {z.zone_id for z in original.layout.zones}
    assert sorted(reloaded.layout.zones, key=lambda z: z.zone_id) == sorted(
        original.layout.zones, key=lambda z: z.zone_id
    )
    assert {(e.zone_a, e.zone_b) for e in reloaded.layout.adjacency} == {
        (e.zone_a, e.zone_b) for e in original.layout.adjacency
    }
    assert len(reloaded.shift_pattern) == len(original.shift_pattern)
    assert reloaded.shift_pattern[0].shift_id == original.shift_pattern[0].shift_id
    assert reloaded.shift_pattern[0].zones == original.shift_pattern[0].zones

    with driver.session() as session:
        session.run(
            "MATCH (f:Factory {factory_id: $id}) "
            "OPTIONAL MATCH (f)-[:HAS_ZONE]->(z:FactoryZone) "
            "DETACH DELETE f, z",
            id=TEST_FACTORY_ID,
        )

    print("OK: FactoryProfile round-trip through Neo4j matches the original.")


if __name__ == "__main__":
    main()
