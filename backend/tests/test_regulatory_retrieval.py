"""The one retrieval layer's three query shapes, per Step 5's Definition
of Done: a real citation to a checkable section number, a correct
pattern-lookup answer, a correctly-flagged compliance deviation, and
honest DGMS-supplementary labeling — all against the live Neo4j
instance, not a mock."""

from pathlib import Path

import pytest
from neo4j import GraphDatabase

from app.config import get_settings
from app.regulatory.loader import ingest_all
from app.regulatory.retrieval import (
    answer_regulatory_question,
    check_compliance,
    lookup_incident_pattern,
)

SOURCES_DIR = Path(__file__).resolve().parents[2] / "data" / "regulatory" / "sources"


@pytest.fixture(scope="module")
def driver():
    settings = get_settings()
    d = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    ingest_all(d, SOURCES_DIR)
    yield d
    d.close()


def test_regulatory_qa_returns_real_checkable_citation(driver):
    result = answer_regulatory_question(
        driver, "What precautions are required for explosive or flammable gas?"
    )
    assert result["answer"] is not None
    top = result["citations"][0]
    assert top["framework"] == "Factories_Act_1948"
    assert top["section_number"] == "37"
    assert top["is_supplementary"] is False


def test_pattern_lookup_finds_hot_work_near_gas_recurrence(driver):
    result = lookup_incident_pattern(driver, "hot_work", "high")
    assert result["has_occurred_before"] is True
    entry_ids = {m["entry_id"] for m in result["matches"]}
    assert {"AL-0003", "AL-0008"}.issubset(entry_ids)


def test_pattern_lookup_returns_false_for_a_permit_type_with_no_history(driver):
    # cold_work never occurs in a low-hazard zone in the corpus
    result = lookup_incident_pattern(driver, "cold_work", "low")
    assert result["has_occurred_before"] is False
    assert result["matches"] == []


def test_compliance_check_flags_seeded_deviation_with_real_clause(driver):
    result = check_compliance(driver, "missing_lel_reading")
    assert result["deviation_flagged"] is True
    assert result["citation"]["framework"] == "OISD"
    assert result["citation"]["section_number"] == "6.6.10"


def test_compliance_check_does_not_flag_an_unseeded_deviation(driver):
    result = check_compliance(driver, "no_such_deviation_type")
    assert result["deviation_flagged"] is False


def test_dgms_scoped_question_returns_the_real_verified_circular_labeled_supplementary(driver):
    """DGMS(Tech) Circular No. 04 of 2020 was selected and verified
    against dgms.gov.in's own circular index (§7.3), confirmed by the
    user. A DGMS-scoped question must return it labeled
    is_supplementary=true, not as an unqualified primary citation."""
    result = answer_regulatory_question(
        driver, "preventing gas hazards in mines", framework="DGMS"
    )
    assert result["answer"] is not None
    assert result["citations"][0]["framework"] == "DGMS"
    assert result["citations"][0]["is_supplementary"] is True
    assert "04" in result["citations"][0]["section_number"]


def test_dgms_scoped_question_with_no_relevant_match_is_still_honest(driver):
    """A DGMS-scoped question far outside the one ingested circular's
    subject should not be forced into a false-positive match — Neo4j's
    vector search always returns its top-k nearest neighbors regardless
    of relevance, so this only confirms the framework filter itself
    still works with a single-document corpus, not topical relevance."""
    result = answer_regulatory_question(driver, "coke oven battery emissions", framework="DGMS")
    assert result["citations"][0]["framework"] == "DGMS"
    assert result["citations"][0]["is_supplementary"] is True
