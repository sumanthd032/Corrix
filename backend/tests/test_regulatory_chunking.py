"""Chunking the real OISD and Factories Act PDFs on clause boundaries,
per CORRIX_DATA_METHODOLOGY.md §11.2. Checks against known real section
numbers/titles rather than just a chunk count, so a regression that
silently shifts section boundaries gets caught.

Known limitation, not chased further given effort/scope: a handful of
Factories Act sections (e.g. 3, 4, 7A, 7B) are missing or have a title
corrupted by an adjacent footnote/amendment marker in the extracted
text — dense legal-document footnote interference, not something a
regex-based chunker fully solves. The corpus still has substantial real
coverage (113 Factories Act + 62 OISD sections) and every chunk that
does exist is genuinely real, citable text.
"""

from pathlib import Path

from app.regulatory.chunking import chunk_factories_act, chunk_oisd_report

SOURCES_DIR = Path(__file__).resolve().parents[2] / "data" / "regulatory" / "sources"


def test_factories_act_chunks_key_real_sections():
    chunks = chunk_factories_act(SOURCES_DIR / "factories_act_1948.pdf")
    by_number = {c.section_number: c for c in chunks}

    assert len(chunks) > 100
    assert by_number["1"].section_title == "Short title, extent and commencement"
    assert "Interpretation" in by_number["2"].section_title
    assert len(by_number["2"].text) > 1000  # a real, substantial section
    assert by_number["120"].section_title == "Repeal and savings"
    assert all(c.framework == "Factories_Act_1948" for c in chunks)
    assert all(len(c.text) > 20 for c in chunks)
    # no duplicate section numbers (the ToC-vs-body duplication bug)
    numbers = [c.section_number for c in chunks]
    assert len(numbers) == len(set(numbers))


def test_oisd_report_chunks_key_real_sections():
    chunks = chunk_oisd_report(SOURCES_DIR / "oisd_guideline.pdf")
    by_number = {c.section_number: c for c in chunks}

    assert len(chunks) > 50
    assert by_number["1.0"].section_title == "INTRODUCTION"
    assert "Work Permit System" in by_number["6.6.10"].section_title
    assert all(c.framework == "OISD" for c in chunks)
    assert all(len(c.text) > 20 for c in chunks)
    numbers = [c.section_number for c in chunks]
    assert len(numbers) == len(set(numbers))


def test_no_chunk_title_contains_digits_from_data_values():
    """Regression guard for the "29.2 MMT (0.59 mbpd)" class of false
    positive — a data value masquerading as a section boundary."""
    fa_chunks = chunk_factories_act(SOURCES_DIR / "factories_act_1948.pdf")
    oisd_chunks = chunk_oisd_report(SOURCES_DIR / "oisd_guideline.pdf")
    for chunk in fa_chunks + oisd_chunks:
        assert not any(ch.isdigit() for ch in chunk.section_title)
