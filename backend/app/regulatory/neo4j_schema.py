"""Neo4j graph schema for the Regulatory Intelligence substrate, per
CORRIX_BUILD_PLAN.md Step 5: "equipment-permit-zone-incident node/edge
types," serving three query shapes over one database (§8 Pillar 3):
vector similarity for regulatory Q&A, graph traversal for pattern
lookup, and a compliance-check mode.

Node labels
-----------
Zone             (zone_id, name, hazard_class): same identity as the
                 plant layout (Step 2), not a duplicate model, just the
                 graph-side representation the RAG layer needs to join
                 against.
Equipment        (equipment_id, name, equipment_type, zone_id): the
                 physical assets a permit or incident can be tied to.
PermitType       (name): one node per permit taxonomy entry (hot_work,
                 cold_work, confined_space_entry, lifting_operation,
                 electrical_isolation), so pattern-lookup queries can
                 traverse "which incidents involved this permit type."
Incident         (entry_id, deviation_type, description, timestamp,
                 source_framework, required_checklist_ref): the mocked
                 near-miss/audit-log corpus (§10), schema-identical to
                 Step 1's AuditLogEntry.
Clause           (clause_id, framework, source_document, section_number,
                 section_title, text, embedding): a chunked, vector-
                 indexed piece of real regulatory text (§11). `embedding`
                 is a list[float] scored by the vector index.

Relationships
-------------
(Equipment)-[:LOCATED_IN]->(Zone)
(Incident)-[:OCCURRED_IN]->(Zone)
(Incident)-[:INVOLVED_EQUIPMENT]->(Equipment)      -- optional
(Incident)-[:INVOLVED_PERMIT_TYPE]->(PermitType)
(Incident)-[:CITES]->(Clause)                      -- the real clause
                                                        a mocked incident
                                                        record points to

Why this shape: the doc's own pattern-lookup example question is "has a
hot-work-near-gas pattern occurred before", answerable as a graph
traversal from PermitType through Incident to Zone (filtering on
zone.hazard_class), not a vector search. The compliance-check mode is
the same traversal from the other direction: given a permit type + zone
+ deviation type, find a matching Incident and follow CITES to its real
clause. The regulatory Q&A mode is pure vector similarity over Clause
nodes and doesn't touch the other four labels at all: one database,
three retrieval shapes, per the build plan's explicit instruction not to
split this into three separate agents/servers.
"""

from neo4j import Driver

EMBEDDING_DIMENSIONS = 384  # all-MiniLM-L6-v2's output dimension

CONSTRAINTS = [
    "CREATE CONSTRAINT zone_id_unique IF NOT EXISTS FOR (z:Zone) REQUIRE z.zone_id IS UNIQUE",
    "CREATE CONSTRAINT equipment_id_unique IF NOT EXISTS FOR (e:Equipment) REQUIRE e.equipment_id IS UNIQUE",
    "CREATE CONSTRAINT permit_type_name_unique IF NOT EXISTS FOR (p:PermitType) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT incident_entry_id_unique IF NOT EXISTS FOR (i:Incident) REQUIRE i.entry_id IS UNIQUE",
    "CREATE CONSTRAINT clause_id_unique IF NOT EXISTS FOR (c:Clause) REQUIRE c.clause_id IS UNIQUE",
]

VECTOR_INDEX = f"""
CREATE VECTOR INDEX clause_embedding_index IF NOT EXISTS
FOR (c:Clause) ON (c.embedding)
OPTIONS {{
  indexConfig: {{
    `vector.dimensions`: {EMBEDDING_DIMENSIONS},
    `vector.similarity_function`: 'cosine'
  }}
}}
"""


def ensure_schema(driver: Driver) -> None:
    """Idempotent: safe to call on every app startup, per the `IF NOT
    EXISTS` guards on every constraint/index."""
    with driver.session() as session:
        for statement in CONSTRAINTS:
            session.run(statement)
        session.run(VECTOR_INDEX)


def wipe_all(driver: Driver) -> None:
    """Testing/re-ingestion convenience: deletes every node this schema
    owns. Never called by application code paths, only test/authoring
    scripts."""
    with driver.session() as session:
        session.run("MATCH (n) WHERE n:Zone OR n:Equipment OR n:PermitType OR n:Incident OR n:Clause DETACH DELETE n")
