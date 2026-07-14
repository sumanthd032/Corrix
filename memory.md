# Corrix — Project Memory

This is an append-only log of what has actually happened on this project. It is a record, not a plan. For rules on how to work, see `CLAUDE.md`. For what is being built and why, see `docs/CORRIX_PROJECT.md`, `docs/CORRIX_DATA_METHODOLOGY.md`, and `docs/CORRIX_BUILD_PLAN.md`.

Entries are added after each completed step or major task, in order, and are never edited or removed. If something recorded here later turns out to be wrong, a new entry corrects it. Nothing below this line is fabricated or assumed. It reflects only what was actually done, checked, or decided.

Entry format:

```
## [date] — [step or task]
What was done:
Why:
Files touched:
External access (APIs, services, accounts):
Open questions or blockers:
Next action:
```

---

## 2026-07-15 — Project setup: design documents and working infrastructure

What was done: The three core design documents were written and refined through several rounds of review: `docs/CORRIX_PROJECT.md` (product design and architecture), `docs/CORRIX_DATA_METHODOLOGY.md` (data generation and simulation methodology), and `docs/CORRIX_BUILD_PLAN.md` (ten-step build sequence). An external validation pass was applied against the official problem statement, which produced several corrections: an anchor-incident date and mechanism correction (the real, verifiable Visakhapatnam Steel Plant incident is dated June 8, 2025 and involves a molten steel ladle, not the January 2025 coke oven framing in the brief), agent information silos in the Safety Council (each agent scoped to only its own MCP data source), a held-out validation split for the self-improving memory loop, a Joint-Evidence Novelty Detector to catch compound-risk patterns beyond the brief's named examples and beyond the five scenarios built, and consolidation of six brief sub-directions into four integrated pillars rather than six disconnected modules. A factual error was also caught and corrected during review: an earlier draft claimed the brief names six specific compound-risk patterns, when it actually names three (maintenance and gas co-occurrence, confined space entry, hot work near elevated gas) across its six illustrative categories. Several dangling internal section references left over from earlier drafts were also found and fixed. `CLAUDE.md` and this file were created to govern how implementation proceeds from here.

Why: The user is building this project end to end with Claude Code and asked for design work to be genuinely rigorous rather than a restatement of the hackathon brief's own example list, on the reasoning that most competing teams will build close to that list and differentiation needs to come from real technical and narrative substance. The user also asked, separately, for an execution framework so that implementation work is traceable, ask-first rather than assumption-driven, and produces a UI held to a high, explicit quality bar rather than a default AI-generated look.

Files touched: `docs/CORRIX_PROJECT.md`, `docs/CORRIX_DATA_METHODOLOGY.md`, `docs/CORRIX_BUILD_PLAN.md`, `CLAUDE.md` (new), `memory.md` (new, this file).

External access: None. No API keys, external services, or accounts have been used yet. The git repository was checked and confirmed initialized on branch `main` with no commits. The global git identity was checked and confirmed present (name and email configured).

Open questions or blockers: Before Step 1 of the build plan can proceed, the user needs to provide or confirm the following, listed in `CLAUDE.md` Section 3: a Groq API key, a Gemini API key, a Neo4j AuraDB Free instance and its credentials, a choice of webhook channel for the Emergency Response Orchestrator (Slack, Discord, or SMTP), a Render or Railway account for the eventual public demo instance, confirmation of which specific DGMS circular(s) to ingest, and a webcam or sample video clip for the computer vision pipeline when Step 6 is reached. None of these block writing code that does not yet call external services, but Step 1's Definition of Done explicitly requires a real successful call against Groq, Gemini, and Neo4j, so they will be needed early.

Next action: Make an initial git commit covering the existing design documents and this new working infrastructure, then begin Step 1 of the build plan (repository scaffolding, schema definitions, MCP server stubs) once the required credentials are available.
