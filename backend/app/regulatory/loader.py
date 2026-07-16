"""Ingests everything into the single Neo4j AuraDB substrate: plant
zones, illustrative equipment, permit types, the mocked near-miss corpus,
and the real, chunked OISD/Factories Act clause text with embeddings —
per CORRIX_BUILD_PLAN.md Step 5's "one database, not a ChromaDB/NetworkX
split" instruction.
"""

from neo4j import Driver

from app.regulatory.chunking import Chunk, chunk_factories_act, chunk_oisd_report
from app.regulatory.corpus import IncidentRecord, load_near_miss_corpus
from app.regulatory.dgms import get_dgms_chunks
from app.regulatory.embeddings import embed_texts
from app.regulatory.equipment import EQUIPMENT
from app.regulatory.neo4j_schema import ensure_schema
from app.simulation.plant_layout import load_plant_layout

PERMIT_TYPES = [
    "hot_work", "cold_work", "confined_space_entry",
    "lifting_operation", "electrical_isolation",
]


def _load_zones(driver: Driver) -> None:
    layout = load_plant_layout()
    with driver.session() as session:
        for zone in layout.zones:
            session.run(
                """
                MERGE (z:Zone {zone_id: $zone_id})
                SET z.name = $name, z.hazard_class = $hazard_class
                """,
                zone_id=zone.zone_id,
                name=zone.name,
                hazard_class=zone.hazard_class.value,
            )


def _load_equipment(driver: Driver) -> None:
    with driver.session() as session:
        for eq in EQUIPMENT:
            session.run(
                """
                MERGE (e:Equipment {equipment_id: $equipment_id})
                SET e.name = $name, e.equipment_type = $equipment_type
                WITH e
                MATCH (z:Zone {zone_id: $zone_id})
                MERGE (e)-[:LOCATED_IN]->(z)
                """,
                **eq,
            )


def _load_permit_types(driver: Driver) -> None:
    with driver.session() as session:
        for name in PERMIT_TYPES:
            session.run("MERGE (p:PermitType {name: $name})", name=name)


def _load_incidents(driver: Driver, records: list[IncidentRecord]) -> None:
    with driver.session() as session:
        for record in records:
            entry = record.audit_log_entry
            session.run(
                """
                MERGE (i:Incident {entry_id: $entry_id})
                SET i.deviation_type = $deviation_type,
                    i.description = $description,
                    i.timestamp = $timestamp,
                    i.source_framework = $source_framework,
                    i.required_checklist_ref = $required_checklist_ref
                WITH i
                MATCH (z:Zone {zone_id: $zone_id})
                MERGE (i)-[:OCCURRED_IN]->(z)
                WITH i
                MATCH (p:PermitType {name: $permit_type})
                MERGE (i)-[:INVOLVED_PERMIT_TYPE]->(p)
                """,
                entry_id=entry.entry_id,
                deviation_type=entry.deviation_type,
                description=entry.description,
                timestamp=entry.timestamp.isoformat(),
                source_framework=entry.source_framework.value,
                required_checklist_ref=entry.required_checklist_ref,
                zone_id=entry.zone_id,
                permit_type=record.permit_type,
            )


def _load_clauses(driver: Driver, chunks: list[Chunk]) -> None:
    embeddings = embed_texts([c.text for c in chunks])
    with driver.session() as session:
        for chunk, embedding in zip(chunks, embeddings):
            session.run(
                """
                MERGE (c:Clause {clause_id: $clause_id})
                SET c.framework = $framework,
                    c.source_document = $source_document,
                    c.section_number = $section_number,
                    c.section_title = $section_title,
                    c.text = $text,
                    c.embedding = $embedding
                """,
                clause_id=chunk.clause_id,
                framework=chunk.framework,
                source_document=chunk.source_document,
                section_number=chunk.section_number,
                section_title=chunk.section_title,
                text=chunk.text,
                embedding=embedding,
            )


def _link_incidents_to_clauses(driver: Driver, records: list[IncidentRecord]) -> None:
    """Matches each Incident's required_checklist_ref back to the real
    Clause it cites, by section number embedded in the ref string. Best-
    effort string match — the ref format is authored to make this work
    (see near_miss_corpus.yaml), not a general-purpose citation parser.

    A ref may cite a numbered sub-paragraph one level deeper than any
    independently-chunked Clause (e.g. "§6.6.10.2" is a real paragraph
    inside the "6.6.10" chunk, since sub-sub-sub-numbering wasn't split
    into its own clause) — matched via the dotted-prefix form, not just
    the exact "§<number> (" leaf form.
    """
    with driver.session() as session:
        for record in records:
            entry = record.audit_log_entry
            session.run(
                """
                MATCH (i:Incident {entry_id: $entry_id})
                MATCH (c:Clause {framework: $framework})
                WHERE $ref CONTAINS ('§' + c.section_number + ' (')
                   OR $ref CONTAINS ('§' + c.section_number + '.')
                MERGE (i)-[:CITES]->(c)
                """,
                entry_id=entry.entry_id,
                framework=entry.source_framework.value,
                ref=entry.required_checklist_ref,
            )


def ingest_all(driver: Driver, sources_dir) -> dict:
    ensure_schema(driver)
    _load_zones(driver)
    _load_equipment(driver)
    _load_permit_types(driver)

    fa_chunks = chunk_factories_act(sources_dir / "factories_act_1948.pdf")
    oisd_chunks = chunk_oisd_report(sources_dir / "oisd_guideline.pdf")
    dgms_chunks = get_dgms_chunks()
    _load_clauses(driver, fa_chunks + oisd_chunks + dgms_chunks)

    records = load_near_miss_corpus()
    _load_incidents(driver, records)
    _link_incidents_to_clauses(driver, records)

    return {
        "zones": None,
        "equipment": len(EQUIPMENT),
        "permit_types": len(PERMIT_TYPES),
        "dgms_clauses": len(dgms_chunks),
        "clauses": len(fa_chunks) + len(oisd_chunks) + len(dgms_chunks),
        "incidents": len(records),
    }
