"""One retrieval layer serving three query shapes over the single Neo4j
substrate, per CORRIX_BUILD_PLAN.md Step 5 and CORRIX_PROJECT.md §8
Pillar 3: resist the urge to build three separate agents/servers for
one database.

1. `answer_regulatory_question`: vector similarity Q&A.
2. `lookup_incident_pattern`: graph traversal ("has this pattern
   happened before").
3. `check_compliance`: matches a deviation type against the mocked
   audit-log corpus and returns the real clause it violates.

DGMS handling: no DGMS content is ingested yet (§7.3, pending user
selection/verification against dgms.gov.in). `answer_regulatory_question`
still accepts `framework="DGMS"` and honestly reports zero results
rather than silently falling back to OISD/Factories Act content and
mislabeling it; once DGMS clauses exist, they carry `is_supplementary:
true` in every result, never presented as a primary citation.
"""

from neo4j import Driver

from app.regulatory.embeddings import embed_text

SUPPLEMENTARY_FRAMEWORKS = {"DGMS"}


def answer_regulatory_question(
    driver: Driver, question: str, framework: str | None = None, top_k: int = 3
) -> dict:
    query_vector = embed_text(question)
    with driver.session() as session:
        if framework:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('clause_embedding_index', $top_k, $vector)
                YIELD node, score
                WHERE node.framework = $framework
                RETURN node.section_number AS section_number,
                       node.section_title AS section_title,
                       node.source_document AS source_document,
                       node.framework AS framework,
                       node.text AS text,
                       score
                ORDER BY score DESC
                """,
                vector=query_vector,
                framework=framework,
                top_k=top_k * 5,  # over-fetch since we filter after
            )
        else:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('clause_embedding_index', $top_k, $vector)
                YIELD node, score
                RETURN node.section_number AS section_number,
                       node.section_title AS section_title,
                       node.source_document AS source_document,
                       node.framework AS framework,
                       node.text AS text,
                       score
                ORDER BY score DESC
                """,
                vector=query_vector,
                top_k=top_k,
            )
        rows = [dict(r) for r in result][:top_k]

    if not rows:
        return {
            "question": question,
            "answer": None,
            "citations": [],
            "note": (
                f"No {framework} content has been ingested yet."
                if framework
                else "No matching regulatory content found."
            ),
        }

    citations = [
        {
            "framework": r["framework"],
            "source_document": r["source_document"],
            "section_number": r["section_number"],
            "section_title": r["section_title"],
            "is_supplementary": r["framework"] in SUPPLEMENTARY_FRAMEWORKS,
            "similarity_score": round(r["score"], 4),
        }
        for r in rows
    ]
    return {
        "question": question,
        "answer": rows[0]["text"],
        "citations": citations,
    }


def lookup_incident_pattern(
    driver: Driver, permit_type: str, zone_hazard_class: str | None = None
) -> dict:
    """Graph traversal: has a compound pattern like this occurred before?
    Matches on permit type (and optionally zone hazard class) against
    the mocked near-miss/audit-log corpus."""
    with driver.session() as session:
        if zone_hazard_class:
            result = session.run(
                """
                MATCH (i:Incident)-[:INVOLVED_PERMIT_TYPE]->(p:PermitType {name: $permit_type})
                MATCH (i)-[:OCCURRED_IN]->(z:Zone {hazard_class: $hazard_class})
                OPTIONAL MATCH (i)-[:CITES]->(c:Clause)
                RETURN i.entry_id AS entry_id, i.deviation_type AS deviation_type,
                       i.description AS description, i.timestamp AS timestamp,
                       z.zone_id AS zone_id,
                       c.framework AS framework, c.section_number AS section_number,
                       c.source_document AS source_document
                ORDER BY i.timestamp
                """,
                permit_type=permit_type,
                hazard_class=zone_hazard_class,
            )
        else:
            result = session.run(
                """
                MATCH (i:Incident)-[:INVOLVED_PERMIT_TYPE]->(p:PermitType {name: $permit_type})
                MATCH (i)-[:OCCURRED_IN]->(z:Zone)
                OPTIONAL MATCH (i)-[:CITES]->(c:Clause)
                RETURN i.entry_id AS entry_id, i.deviation_type AS deviation_type,
                       i.description AS description, i.timestamp AS timestamp,
                       z.zone_id AS zone_id,
                       c.framework AS framework, c.section_number AS section_number,
                       c.source_document AS source_document
                ORDER BY i.timestamp
                """,
                permit_type=permit_type,
            )
        matches = [dict(r) for r in result]

    return {
        "permit_type": permit_type,
        "zone_hazard_class": zone_hazard_class,
        "has_occurred_before": len(matches) > 0,
        "matches": matches,
    }


def check_compliance(driver: Driver, deviation_type: str) -> dict:
    """Compliance-check mode: does this deviation type match a known,
    cited pattern in the mocked audit-log corpus? If so, flag it and
    return the real clause it violates."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (i:Incident {deviation_type: $deviation_type})
            OPTIONAL MATCH (i)-[:CITES]->(c:Clause)
            RETURN i.entry_id AS entry_id, i.description AS description,
                   c.framework AS framework, c.section_number AS section_number,
                   c.section_title AS section_title, c.source_document AS source_document
            LIMIT 1
            """,
            deviation_type=deviation_type,
        )
        row = result.single()

    if row is None:
        return {"deviation_type": deviation_type, "deviation_flagged": False, "citation": None}

    data = dict(row)
    return {
        "deviation_type": deviation_type,
        "deviation_flagged": True,
        "matched_entry_id": data["entry_id"],
        "citation": {
            "framework": data["framework"],
            "source_document": data["source_document"],
            "section_number": data["section_number"],
            "section_title": data["section_title"],
            "is_supplementary": data["framework"] in SUPPLEMENTARY_FRAMEWORKS,
        },
    }
