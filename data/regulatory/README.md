# Regulatory source documents

Real, public, government-sourced documents — downloaded as-is, not generated. Per `CORRIX_DATA_METHODOLOGY.md` §11 and `CORRIX_PROJECT.md` §17.

## Sources actually retrieved

- **`sources/oisd_guideline.pdf`** — downloaded from the exact `oisd.gov.in` URL logged in `CORRIX_PROJECT.md` §17. It is the **"Report of the Working Group on Safety in the Indian Petroleum Sector"**, facilitated by the Oil Industry Safety Directorate (OISD) for the Ministry of Petroleum & Natural Gas. 188 pages, with numbered sections (e.g. §6.1 "History of Industrial Incidents", §7.5 "Compliance with Standard Operating Procedures (SOP)").

  **Correction against the design docs' assumption:** `CORRIX_DATA_METHODOLOGY.md` §10's illustrative citation format (`OISD-STD-XXX §4.2`) assumed the source would be a numbered OISD engineering standard. The document actually hosted at the logged URL is this Working Group report, not a numbered standard — the design docs never verified the specific document at that URL beyond confirming it was a real OISD-facilitated PDF. The mocked near-miss/audit-log corpus (`data/regulatory/near_miss_corpus.yaml`) cites this document by its real title and real section numbers instead of the illustrative `OISD-STD-XXX` format, since that format doesn't correspond to anything in the actual source.

- **`sources/factories_act_1948.pdf`** — the India Code bitstream URL logged in `CORRIX_PROJECT.md` §17 (`indiacode.nic.in/bitstream/123456789/1530/1/A1948-63.pdf`) returned an "Invalid URL or Argument(s)" HTML error page, not a PDF — that link is stale. Retrieved instead from the DGMS-hosted mirror also logged in the same section (`dgms.gov.in/writereaddata/UploadFile/The_Factories_Act-1948.pdf`), which returned the real 60-page Act text (confirmed: numbered sections starting "1. Short title, extent and commencement" through the full text, "ACT NO. 63 OF 1948").

## DGMS circular(s)

Not yet selected. Per `CORRIX_PROJECT.md` §7.3 and `CLAUDE.md` §3, the specific DGMS circular(s) to ingest as supplementary corpus content must be selected and verified against `dgms.gov.in` with the user before ingestion — not picked unilaterally. Open until that happens.
