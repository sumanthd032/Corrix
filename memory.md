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

---

## 2026-07-16 — Step 1: Foundations, Environment & Schemas Locked, complete

What was done: Before scaffolding, three foundational tooling choices not pinned by the three design docs were confirmed with the user: `pip` + `venv` + `requirements.txt` for backend Python dependency management (not Poetry or uv), Vite + React + TypeScript for the frontend (not plain JS or Next.js), and the official Python MCP SDK's `mcp.server.fastmcp.FastMCP` interface for the five MCP servers (not a separate FastMCP package or hand-rolled low-level SDK usage).

Repo structure created: `backend/app/{schemas,mcp_servers,simulation,detection,council,api}`, `backend/tests`, `backend/scripts`, `data/scenarios`, `frontend`. A FastAPI skeleton (`backend/app/main.py`) boots with a `/health` route and a `/ws` echo WebSocket, verified with a real local request. A Vite + React + TypeScript skeleton (`frontend/`) boots, type-checks clean, and its `App.tsx` performs a real fetch against the backend's `/health` endpoint on mount — the hello-world round trip is genuinely wired, not just two servers running independently. `backend/app/config.py` loads settings via `pydantic-settings` from a repo-root `.env`, resolved by absolute path so it works regardless of the process's working directory. `.env.example` documents every credential needed through Step 9 (Groq, Gemini, Neo4j, and the three ERO channel options), and `.gitignore` excludes `.env`, both Python and Node virtual environments/caches, and build output.

Every schema named in Step 1's key-tasks list was locked as a Pydantic model under `backend/app/schemas/`: `Zone` + `ZoneAdjacencyEdge` + `PlantLayout` (§7), `GasSensorReading` (§3) kept in a separate module and separate model from `ComplianceSignalReading` (§4, S1's procedural-compliance signal) per the doc's explicit instruction that these are structurally different phenomena, `PermitRecord` (§5), `ShiftRecord` (§6), `BadgePingEvent` (§8.2), `CVObservationEvent` (§9, with `source`/`correlation_source` as distinct typed fields, not a merged label), `AuditLogEntry` (§10), `ScenarioConfig` and its nested signal/ground-truth models (§12.1, `memory_split` wired in from the start), and `CouncilVerdict` (`CORRIX_PROJECT.md` §6.2) with `time_to_critical` modeled as `TimeToCriticalForecast` — a median/IQR-band/escalation-probability distribution, not a scalar, per the build plan's explicit Step 1 instruction (the real Monte Carlo computation of that distribution is Step 8 work; only the shape is locked now). Every model is tested in `backend/tests/test_schemas.py` by constructing it from the literal example JSON/YAML payload given in its source document — 10 tests, all passing, proving zero manual patching was needed.

Five MCP server stubs were scaffolded under `backend/app/mcp_servers/`: Sensor Stream, Permit/Shift, Regulatory Intelligence (one server covering RAG + knowledge graph + audit corpus, per the build plan's deliberate five-not-six consolidation), CV/Observation, and Worker Location. Each exposes placeholder tools returning stub data; `backend/tests/test_mcp_servers.py` boots each server and calls `list_tools()` to confirm it responds correctly — 5 tests, all passing.

The `data/scenarios/` folder convention was established: `README.md` documents the `ScenarioConfig` YAML shape and the `memory_split` (`population`/`held_out`) discipline, and `s1_anchor.example.yaml` transcribes the doc's own S1 example verbatim as a template, round-trip tested in `backend/tests/test_scenario_convention.py`. This is a template only — the real authored S1-S4 configs with multiple seed variants are Step 2 work.

The user provided real credentials for Groq, Gemini, and Neo4j AuraDB. The first paste was garbled (UI timestamps mixed into the pasted text, and one string labeled "gemini" was actually recognizable as a Neo4j AuraDB-format password by its `AQ.` prefix) — this was flagged back to the user rather than guessed at, consistent with `CLAUDE.md` Section 2's instruction to ask rather than assume, especially for credentials. The user resolved it by editing `.env` directly. `backend/scripts/verify_step1_credentials.py` (committed, no secrets in it) runs one real call against each service and prints only pass/fail. All three passed: a Groq chat completion (`llama-3.1-8b-instant`), a Gemini `generateContent` call, and a Neo4j `RETURN 1` query against the live AuraDB instance. Note for later steps: `gemini-2.5-flash`/`gemini-2.5-flash-lite` returned 404 (no longer available to new API keys) and `gemini-2.0-flash` returned 429 (quota exhausted on first call) against this specific key; `gemini-flash-latest` is the model alias that actually works and is what Step 4's Gemini failover path should default to, pending re-verification if the account's available models change.

Why: Step 1's stated goal is that every later step has a stable contract to build against, so workstreams don't block each other later. The tooling and package-choice questions were surfaced to the user rather than defaulted, per `CLAUDE.md` Section 2 ("ask, do not assume") applying to technical choices the three design docs don't pick between. The schema separation between the gas sensor model and the S1 compliance signal specifically preserves a deliberate design decision from `CORRIX_DATA_METHODOLOGY.md` §2 and §4: forcing S1 into a gas-ppm shape would misrepresent the real, verified anchor incident's actual mechanism.

Files touched: `backend/requirements.txt`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/schemas/*.py` (11 files), `backend/app/mcp_servers/*.py` (6 files), `backend/tests/*.py` (4 files), `backend/scripts/verify_step1_credentials.py`, `data/scenarios/README.md`, `data/scenarios/s1_anchor.example.yaml`, `.env.example`, `.gitignore`, `frontend/` (Vite scaffold plus a rewritten `App.tsx`/`App.css`).

External access: Real, verified calls succeeded against Groq (`llama-3.1-8b-instant`), Gemini (`gemini-flash-latest`), and a live Neo4j AuraDB Free instance (`neo4j+s://56c1c20f.databases.neo4j.io`). Credentials live only in the local, gitignored `.env`; `.env.example` has no real values.

Open questions or blockers: The remaining Section 3 requirements not yet needed are still open: ERO webhook channel choice (needed before Step 9), a Render/Railway account (Step 10), DGMS circular selection and verification against `dgms.gov.in` (needed before Step 5), and a webcam/sample clip for the CV pipeline (Step 6). None of these block Step 2.

Next action: Begin Step 2 of the build plan — the data simulation engine (OU-process gas simulator, procedural-compliance signal model, permit/shift/worker-location generators, the eight-zone plant layout with adjacency graph, and the scenario-config engine authoring S1-S4 with multiple seed variants).
