"""DGMS supplementary content, per CORRIX_PROJECT.md §7.3 — honestly
scoped, and honestly limited.

The selected circular, DGMS(Tech) Circular No. 04 of 2020 ("Preventing
of inflammable gas hazards in belowground coal mines," dated
27-02-2020), was selected and verified against dgms.gov.in's own
official circular index ("DGMS CIRCULARS FROM 2018 TO 2024",
dgms.gov.in/writereaddata/UploadFile/DGMScircularsfrom20182024_06122024.pdf,
page 88) — confirmed by the user as the circular to ingest.

Both the standalone circular PDF
(dgms.gov.in/writereaddata/UploadFile/DGMS_04637184121810426988.pdf) and
the compiled index's copy of it are scanned images with no extractable
text layer — pypdf's text extraction returns empty content for every
page of both. OCR was not performed for this build (a real, separate
piece of work, not attempted here). Rather than present a third party's
paraphrase of the circular's content as if it were independently
verified primary text — which would repeat exactly the kind of
unverified-citation risk this project's "radical honesty" positioning
exists to avoid — this Clause's `text` is limited to what's actually
verified directly from DGMS's own index: the circular's real number,
date, and subject line. It is real, checkable, and honestly scoped; it
is not a substitute for the full clause-level text OISD and the
Factories Act have. A production follow-up (§16 roadmap) would OCR the
source and re-chunk it properly.
"""

from app.regulatory.chunking import Chunk

DGMS_CIRCULAR_04_2020 = Chunk(
    clause_id="dgms_circular_04_2020",
    framework="DGMS",
    source_document="DGMS(Tech) Circular No. 04 of 2020, dated 27-02-2020",
    section_number="04-2020",
    section_title="Preventing of inflammable gas hazards in belowground coal mines",
    text=(
        "DGMS(Tech) Circular No. 04 of 2020, dated 27-02-2020. Subject: "
        "Preventing of inflammable gas hazards in belowground coal mines. "
        "Verified against the official DGMS circular index at dgms.gov.in "
        "(\"DGMS CIRCULARS FROM 2018 TO 2024\"). The circular's full body "
        "text is a scanned image with no extractable text layer in the "
        "source PDF; this entry is limited to its verified title, number, "
        "and date, not a full chunked clause — supplementary grounding "
        "only, per CORRIX_PROJECT.md §7.3, not a primary citation source."
    ),
)


def get_dgms_chunks() -> list[Chunk]:
    return [DGMS_CIRCULAR_04_2020]
