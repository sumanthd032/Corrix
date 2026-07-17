# Regulatory source documents

Real, public, government-sourced documents, downloaded as-is, not generated. Per `CORRIX_DATA_METHODOLOGY.md` §11 and `CORRIX_PROJECT.md` §17.

## Sources actually retrieved

- **`sources/oisd_guideline.pdf`**: downloaded from the exact `oisd.gov.in` URL logged in `CORRIX_PROJECT.md` §17. It is the **"Report of the Working Group on Safety in the Indian Petroleum Sector"**, facilitated by the Oil Industry Safety Directorate (OISD) for the Ministry of Petroleum & Natural Gas. 188 pages, with numbered sections (e.g. §6.1 "History of Industrial Incidents", §7.5 "Compliance with Standard Operating Procedures (SOP)").

  **Correction against the design docs' assumption:** `CORRIX_DATA_METHODOLOGY.md` §10's illustrative citation format (`OISD-STD-XXX §4.2`) assumed the source would be a numbered OISD engineering standard. The document actually hosted at the logged URL is this Working Group report, not a numbered standard; the design docs never verified the specific document at that URL beyond confirming it was a real OISD-facilitated PDF. The mocked near-miss/audit-log corpus (`data/regulatory/near_miss_corpus.yaml`) cites this document by its real title and real section numbers instead of the illustrative `OISD-STD-XXX` format, since that format doesn't correspond to anything in the actual source.

- **`sources/factories_act_1948.pdf`**: the India Code bitstream URL logged in `CORRIX_PROJECT.md` §17 (`indiacode.nic.in/bitstream/123456789/1530/1/A1948-63.pdf`) returned an "Invalid URL or Argument(s)" HTML error page, not a PDF; that link is stale. Retrieved instead from the DGMS-hosted mirror also logged in the same section (`dgms.gov.in/writereaddata/UploadFile/The_Factories_Act-1948.pdf`), which returned the real 60-page Act text (confirmed: numbered sections starting "1. Short title, extent and commencement" through the full text, "ACT NO. 63 OF 1948").

## DGMS circular

Selected and verified against `dgms.gov.in`'s own official circular index, **"DGMS CIRCULARS FROM 2018 TO 2024"** (`dgms.gov.in/writereaddata/UploadFile/DGMScircularsfrom20182024_06122024.pdf`), confirmed by the user: **DGMS(Tech) Circular No. 04 of 2020, dated 27-02-2020**, subject *"Preventing of inflammable gas hazards in belowground coal mines"*, on-theme with the compound-risk gas scenarios (S2/S3/S4).

**A real limitation, disclosed rather than worked around:** both the standalone circular PDF (`dgms.gov.in/writereaddata/UploadFile/DGMS_04637184121810426988.pdf`) and the compiled index's copy of it are scanned images with no extractable text layer; `pypdf` returns empty text for every page of both. OCR was not performed for this build. Rather than present a third party's summary of the circular's content (found via web search, not independently verified against the primary document) as if it were confirmed primary text, the ingested `Clause` for this circular is limited to what's actually verified directly from DGMS's own index: its real circular number, date, and subject line (see `backend/app/regulatory/dgms.py`). It is real and checkable; it is not full clause-level text the way the OISD and Factories Act corpus is. A production follow-up would OCR the source and chunk it properly (`CORRIX_PROJECT.md` §16 roadmap).

Every DGMS-framework result from the retrieval layer carries `is_supplementary: true`, never presented as a primary citation.
