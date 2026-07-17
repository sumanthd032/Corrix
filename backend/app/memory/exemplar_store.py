"""The self-improving memory loop's exemplar store, per
CORRIX_PROJECT.md §6.3 and CORRIX_DATA_METHODOLOGY.md §12.5: Evaluation
Harness misses from `memory_split: population` runs, stored as
structured exemplars in the same Neo4j graph substrate the Regulatory
Intelligence RAG layer already uses (`app/regulatory/`), not a new
database, the same one, per CORRIX_PROJECT.md §7.1's "one free,
persistent, real database" choice.

Exemplar vectors are fetched and compared in Python via Mahalanobis
distance (`app/detection/retrieval_trigger.py`), not Neo4j's built-in
vector-index similarity search, a real, empirically-forced design
change. Checked against the real scenario library rather than assumed
correct: neither cosine similarity, Euclidean distance, nor Mahalanobis
distance scored through Neo4j's vector index could separate a genuine
S5 near-miss recurrence from ordinary negative-control noise when
searching across a whole run: S5's signal is deliberately tuned to sit
at the edge of the OU process's own noise floor (that's what makes it
"unsolvable by threshold logic," Section 12.3), and it turns out that
same subtlety makes naive distance search over single-tick snapshots,
window-trend differences, and time-series shape correlation all fail
the same way: several negative controls' own noise excursions sit
*closer* to a stored S5 exemplar than a genuine held-out S5 recurrence
does. No threshold cleanly separates the two classes. Fetching all
exemplars and computing Mahalanobis distance directly in Python (reusing
the already-calibrated novelty detector's covariance) is simply easier
to control and inspect than trying to coerce Neo4j's index into the
same computation; the underlying separability limit is real either
way, and is disclosed, not hidden, in `retrieval_trigger.py`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.config import get_settings

MEMORY_CONSTRAINT = (
    "CREATE CONSTRAINT memory_exemplar_id_unique IF NOT EXISTS "
    "FOR (m:MemoryExemplar) REQUIRE m.exemplar_id IS UNIQUE"
)


@lru_cache
def get_shared_driver() -> Driver:
    """One driver instance reused across the live system's memory-loop
    retrieval checks, the same pattern `mcp_servers/regulatory_
    intelligence.py` already uses for its own module-level driver,
    rather than opening a fresh connection per scenario switch."""
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )


@dataclass
class MemoryExemplar:
    exemplar_id: str
    scenario_id: str
    seed: int
    zone_id: str
    evidence_text: str
    correct_risk_level: str
    why: str
    created_at: str
    joint_evidence_vector: list[float]


def ensure_memory_schema(driver: Driver) -> None:
    """Idempotent, per the same `IF NOT EXISTS` discipline
    `neo4j_schema.ensure_schema` already uses."""
    with driver.session() as session:
        session.run(MEMORY_CONSTRAINT)


def store_exemplar(
    driver: Driver,
    exemplar_id: str,
    scenario_id: str,
    seed: int,
    zone_id: str,
    joint_evidence_vector: list[float],
    evidence_text: str,
    correct_risk_level: str,
    why: str,
) -> MemoryExemplar:
    created_at = datetime.now(timezone.utc).isoformat()
    with driver.session() as session:
        session.run(
            """
            MERGE (m:MemoryExemplar {exemplar_id: $exemplar_id})
            SET m.scenario_id = $scenario_id,
                m.seed = $seed,
                m.zone_id = $zone_id,
                m.evidence_text = $evidence_text,
                m.correct_risk_level = $correct_risk_level,
                m.why = $why,
                m.created_at = $created_at,
                m.embedding = $embedding
            """,
            exemplar_id=exemplar_id,
            scenario_id=scenario_id,
            seed=seed,
            zone_id=zone_id,
            evidence_text=evidence_text,
            correct_risk_level=correct_risk_level,
            why=why,
            created_at=created_at,
            embedding=joint_evidence_vector,
        )
    return MemoryExemplar(
        exemplar_id=exemplar_id,
        scenario_id=scenario_id,
        seed=seed,
        zone_id=zone_id,
        evidence_text=evidence_text,
        correct_risk_level=correct_risk_level,
        why=why,
        created_at=created_at,
        joint_evidence_vector=joint_evidence_vector,
    )


def get_all_exemplars(driver: Driver) -> list[MemoryExemplar]:
    """Every stored exemplar, for direct Python-side Mahalanobis
    comparison (`retrieval_trigger.find_first_retrieval_trigger`) rather
    than Neo4j's own vector-index search; see this module's docstring
    for why."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (m:MemoryExemplar)
            RETURN m.exemplar_id AS exemplar_id,
                   m.scenario_id AS scenario_id,
                   m.seed AS seed,
                   m.zone_id AS zone_id,
                   m.evidence_text AS evidence_text,
                   m.correct_risk_level AS correct_risk_level,
                   m.why AS why,
                   m.created_at AS created_at,
                   m.embedding AS embedding
            """
        )
        rows = [dict(r) for r in result]
    return [
        MemoryExemplar(
            exemplar_id=row["exemplar_id"],
            scenario_id=row["scenario_id"],
            seed=row["seed"],
            zone_id=row["zone_id"],
            evidence_text=row["evidence_text"],
            correct_risk_level=row["correct_risk_level"],
            why=row["why"],
            created_at=row["created_at"],
            joint_evidence_vector=row["embedding"],
        )
        for row in rows
    ]


def wipe_all_exemplars(driver: Driver) -> None:
    """Testing/re-run convenience: deletes every MemoryExemplar node,
    never called by application code paths."""
    with driver.session() as session:
        session.run("MATCH (m:MemoryExemplar) DETACH DELETE m")
