"""Chunk the real OISD and Factories Act PDFs on clause/section
boundaries, per CORRIX_DATA_METHODOLOGY.md §11.2 — not fixed-token
windows, so a retrieved chunk is a coherent clause a human (or a judge)
could look up and check directly.

Both source documents use their own real numbering convention, so each
gets its own boundary regex rather than one generic splitter:

- The Factories Act, 1948 numbers top-level sections as a plain integer
  optionally suffixed with a letter for later-inserted sections (e.g.
  "7A.", "7B."), followed immediately by a title-cased heading and a
  period/em-dash — e.g. "1. Short title, extent and commencement.—(1)...".
  Sub-clause markers like "(a)", "(i)", or bracketed amendment markers
  like "1[(ii)" don't match this shape, so they don't fragment a section.
- The OISD Working Group report numbers sections with decimal notation
  under Part B/C (e.g. "6.1", "7.5"), per its own table of contents.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

FACTORIES_ACT_SECTION_RE = re.compile(
    r"^(\d{1,3}[A-Z]{0,2})\.\s+([A-Z][^.\n]{2,120}?)[.—–\-]",
    re.MULTILINE,
)

OISD_SECTION_RE = re.compile(
    r"^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+([A-Z][^\n]{2,120})$",
    re.MULTILINE,
)


@dataclass
class Chunk:
    clause_id: str
    framework: str
    source_document: str
    section_number: str
    section_title: str
    text: str


def extract_pages(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    return [page.extract_text() for page in reader.pages]


def _strip_repeated_boilerplate(pages: list[str], boilerplate_lines: list[str]) -> str:
    cleaned_pages = []
    for page in pages:
        lines = page.split("\n")
        lines = [ln for ln in lines if ln.strip() not in boilerplate_lines]
        cleaned_pages.append("\n".join(lines))
    return "\n".join(cleaned_pages)


def _leading_int(section_number: str) -> int:
    match = re.match(r"\d+", section_number)
    return int(match.group()) if match else 0


_FOOTNOTE_WORDS = {
    "subs", "ins", "omitted", "renumbered", "substituted", "inserted",
    "sub", "numbered", "non",
}


def _is_plausible_title(title: str) -> bool:
    """Reject matches whose "title" is actually a data value or a legal-
    amendment footnote marker (e.g. "2. Subs. by Act 20 of 1987...", a
    Schedule's disease-list entry) rather than a real section heading:
    real headings don't contain digits, aren't a single short
    amendment-editing word, and are mostly alphabetic."""
    if any(ch.isdigit() for ch in title):
        return False
    first_word = title.split()[0].rstrip(".").lower() if title.split() else ""
    if first_word in _FOOTNOTE_WORDS:
        return False
    letters = sum(1 for ch in title if ch.isalpha())
    return letters >= 7


def _filter_monotonic(matches_with_numbers: list[tuple]) -> list[int]:
    """Keep only matches whose leading section number doesn't fall back
    below the highest number seen so far — this is what filters out a
    Schedule's independently-numbered list (e.g. the Third Schedule's
    disease list restarting at 1) or trailing footnote markers, both of
    which appear after the real numbered sections and would otherwise be
    indistinguishable from a real clause boundary by shape alone."""
    kept_indices = []
    highest_seen = 0
    for idx, num in matches_with_numbers:
        if num >= highest_seen:
            kept_indices.append(idx)
            highest_seen = num
    return kept_indices


def _dedup_keep_longest(chunks: list[Chunk]) -> list[Chunk]:
    """The Factories Act's front-matter "ARRANGEMENT OF SECTIONS" table
    of contents lists every section title in the same shape a real
    section boundary has, so a handful of sections get matched twice —
    once as a near-empty ToC line, once as the real body text. Keep
    whichever match has the longer text per section number; the ToC
    mention is always short, the real section never is."""
    best: dict[str, Chunk] = {}
    for chunk in chunks:
        existing = best.get(chunk.section_number)
        if existing is None or len(chunk.text) > len(existing.text):
            best[chunk.section_number] = chunk
    return list(best.values())


BODY_START_ANCHOR = "ACT NO. 63 OF 1948"


def chunk_factories_act(pdf_path: Path) -> list[Chunk]:
    pages = extract_pages(pdf_path)
    full_text = "\n".join(pages)

    # The PDF opens with an "ARRANGEMENT OF SECTIONS" table of contents
    # that lists every section number and title in the exact same shape
    # a real section boundary has, and — critically — in the same
    # monotonically increasing 1..120 order the real body also uses.
    # Chunking the whole document let the ToC's sequence win the
    # monotonic filter and silently swallowed most of the real body
    # sections (whose restart from 1 looked like a rollback). Slicing
    # off everything before the Act's actual enacting text removes the
    # ToC from consideration entirely, rather than trying to out-clever
    # a filter that can't distinguish two structurally-identical
    # increasing sequences.
    body_start = full_text.find(BODY_START_ANCHOR)
    if body_start != -1:
        full_text = full_text[body_start:]

    all_matches = list(FACTORIES_ACT_SECTION_RE.finditer(full_text))
    plausible = [
        (i, m) for i, m in enumerate(all_matches) if _is_plausible_title(m.group(2).strip())
    ]
    numbered = [(i, _leading_int(m.group(1))) for i, m in plausible]
    keep = set(_filter_monotonic(numbered))
    matches = [m for i, m in enumerate(all_matches) if i in keep]

    chunks: list[Chunk] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        section_number = match.group(1)
        section_title = match.group(2).strip()
        text = full_text[start:end].strip()
        if len(text) < 20:
            continue
        chunks.append(
            Chunk(
                clause_id=f"factories_act_1948_s{section_number}",
                framework="Factories_Act_1948",
                source_document="The Factories Act, 1948",
                section_number=section_number,
                section_title=section_title,
                text=text,
            )
        )
    return _dedup_keep_longest(chunks)


def _oisd_sort_key(section_number: str) -> tuple:
    return tuple(int(p) for p in section_number.split("."))


def _find_chapter_anchors(matches: list) -> list:
    """Real top-level chapters in this report are numbered "N.0" (e.g.
    "1.0 INTRODUCTION", "6.0 OBSERVATIONS & DELIBERATIONS"). An early
    executive-summary/statistics section contains numeric values shaped
    just like subsection numbers (e.g. "29.2 MMT (0.59 mbpd)..."),
    appearing in the text *before* the real chapter structure — which
    poisons a simple monotonic filter applied to all matches at once,
    rejecting real later chapters because a bogus larger number appeared
    earlier. Anchoring on ".0" chapter headers first, then keeping only
    a strictly increasing integer sequence of them, sidesteps that: the
    statistics section doesn't happen to contain any "N.0"-shaped values.
    """
    dot_zero = [
        (i, m) for i, m in enumerate(matches)
        if m.group(1).endswith(".0") and _is_plausible_title(m.group(2).strip())
    ]
    numbered = [(i, int(m.group(1).split(".")[0])) for i, m in dot_zero]
    keep = set(_filter_monotonic(numbered))
    return [m for i, m in dot_zero if i in keep]


def chunk_oisd_report(pdf_path: Path) -> list[Chunk]:
    pages = extract_pages(pdf_path)
    boilerplate = {
        "(Confidential)",
        "Report of the Working Group on Safety in Indian Petroleum Sector",
    }
    full_text = _strip_repeated_boilerplate(pages, list(boilerplate))

    all_matches = list(OISD_SECTION_RE.finditer(full_text))
    chapter_anchors = _find_chapter_anchors(all_matches)
    chapter_bounds = [(m.start(), int(m.group(1).split(".")[0])) for m in chapter_anchors]
    chapter_bounds.append((len(full_text), None))

    matches = []
    for i in range(len(chapter_bounds) - 1):
        chapter_start, chapter_num = chapter_bounds[i]
        chapter_end, _ = chapter_bounds[i + 1]
        in_chapter = [
            m for m in all_matches
            if chapter_start <= m.start() < chapter_end
            and int(m.group(1).split(".")[0]) == chapter_num
            and _is_plausible_title(m.group(2).strip())
        ]
        matches.extend(in_chapter)

    chunks: list[Chunk] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        section_number = match.group(1)
        section_title = match.group(2).strip()
        text = full_text[start:end].strip()
        if len(text) < 20:
            continue
        chunks.append(
            Chunk(
                clause_id=f"oisd_wg_report_s{section_number}",
                framework="OISD",
                source_document="Report of the Working Group on Safety in the Indian Petroleum Sector (OISD)",
                section_number=section_number,
                section_title=section_title,
                text=text,
            )
        )
    return _dedup_keep_longest(chunks)
