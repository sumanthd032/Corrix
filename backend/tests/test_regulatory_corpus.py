"""Mocked near-miss/audit-log corpus: every entry validates and cites a
real, checkable clause from one of the actually-downloaded source PDFs,
per CORRIX_DATA_METHODOLOGY.md §10."""

from app.regulatory.chunking import chunk_factories_act, chunk_oisd_report
from app.regulatory.corpus import load_near_miss_corpus

SOURCES_DIR = (
    __import__("pathlib").Path(__file__).resolve().parents[2] / "data" / "regulatory" / "sources"
)


def test_corpus_loads_and_validates():
    records = load_near_miss_corpus()
    assert len(records) >= 8
    entry_ids = [r.audit_log_entry.entry_id for r in records]
    assert len(entry_ids) == len(set(entry_ids))


def test_every_cited_clause_exists_in_the_real_chunked_source():
    """The load-bearing honesty check: every required_checklist_ref must
    point at a section number that actually exists in the real PDF we
    chunked, not an invented citation."""
    fa_sections = {c.section_number for c in chunk_factories_act(SOURCES_DIR / "factories_act_1948.pdf")}
    oisd_sections = {c.section_number for c in chunk_oisd_report(SOURCES_DIR / "oisd_guideline.pdf")}

    for record in load_near_miss_corpus():
        ref = record.audit_log_entry.required_checklist_ref
        if record.audit_log_entry.source_framework.value == "Factories_Act_1948":
            assert any(f"§{num}" in ref or f"§{num} " in ref for num in fa_sections), ref
        elif record.audit_log_entry.source_framework.value == "OISD":
            assert any(f"§{num}" in ref for num in oisd_sections), ref


def test_pattern_lookup_seed_data_covers_hot_work_near_gas():
    """The doc's own example pattern-lookup question is "has a hot-work-
    near-gas pattern occurred before" — confirm the corpus actually has
    matching seed data for it to find."""
    records = load_near_miss_corpus()
    hot_work_in_gas_zone = [
        r for r in records
        if r.permit_type == "hot_work" and r.zone_hazard_class == "high"
    ]
    assert len(hot_work_in_gas_zone) >= 2  # AL-0003 and AL-0008, a real recurrence
