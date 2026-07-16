"""Neo4j ingestion pipeline: real integration test against the live
AuraDB instance — zones, equipment, permit types, incidents, and real
chunked clauses, with every Incident correctly linked to the real
Clause it cites."""

from pathlib import Path

import pytest
from neo4j import GraphDatabase

from app.config import get_settings
from app.regulatory.loader import ingest_all

SOURCES_DIR = Path(__file__).resolve().parents[2] / "data" / "regulatory" / "sources"


@pytest.fixture(scope="module")
def driver():
    settings = get_settings()
    d = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    yield d
    d.close()


@pytest.fixture(scope="module")
def ingested(driver):
    return ingest_all(driver, SOURCES_DIR)


def test_ingestion_reports_expected_counts(ingested):
    assert ingested["equipment"] == 4
    assert ingested["permit_types"] == 5
    assert ingested["clauses"] > 150
    assert ingested["incidents"] == 8


def test_every_incident_cites_a_real_clause(driver, ingested):
    with driver.session() as session:
        result = session.run(
            "MATCH (i:Incident) WHERE NOT (i)-[:CITES]->(:Clause) RETURN i.entry_id AS e"
        )
        missing = [r["e"] for r in result]
    assert missing == [], f"incidents with no CITES edge: {missing}"


def test_zones_and_equipment_are_linked(driver, ingested):
    with driver.session() as session:
        result = session.run(
            "MATCH (e:Equipment)-[:LOCATED_IN]->(z:Zone) RETURN count(*) AS n"
        )
        count = result.single()["n"]
    assert count == 4


def test_vector_search_finds_relevant_clause(driver, ingested):
    from app.regulatory.embeddings import embed_text

    query_vector = embed_text("hot work permit missing LEL gas reading")
    with driver.session() as session:
        result = session.run(
            """
            CALL db.index.vector.queryNodes('clause_embedding_index', 3, $vector)
            YIELD node, score
            RETURN node.section_number AS section, node.framework AS framework, score
            ORDER BY score DESC
            """,
            vector=query_vector,
        )
        top = [dict(r) for r in result]
    assert len(top) > 0
    assert any(r["section"] == "6.6.10" for r in top)
