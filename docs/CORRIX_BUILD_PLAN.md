# Corrix — 10-Step Build Plan
### From zero to a fully working, fully differentiated prototype

This document turns `CORRIX_PROJECT.md` (what we're building and why) and `CORRIX_DATA_METHODOLOGY.md` (exactly how the data works) into an executable sequence. Read those two first if you haven't — this doc assumes their content and doesn't re-explain it.

This version reflects two rounds of review. The first was external validation against the problem statement (see `CORRIX_PROJECT.md`): several new tasks were folded in, and a full 3D "Digital Twin" visualization mode was cut — the single largest optional time investment in the original plan for a payoff no judging criterion specifically rewards. It's now a roadmap item, not a build task. The second was a deliberate decluttering pass: a **Joint-Evidence Novelty Detector** was added (Step 8) because it closes a real gap — everything before it only recognized scripted patterns — but adding it meant looking hard for what to cut so the product doesn't grow into an unfocused pile of features. Three things came out: the Cost-of-Inaction calculator (Step 7, cut — generic, didn't showcase anything distinctive), a sixth "multi-zone cascade" scenario (Step 2/8, cut — redundant once the novelty detector exists), and the Quality & Compliance Audit Agent / Incident Pattern Intelligence as *separate* modules with *separate* MCP servers and UI panels — consolidated into one "Regulatory Intelligence" pillar (still covers both brief bullets, same underlying Neo4j data, five MCP servers instead of six, one interface instead of three).

---

## 0. How to Use This Plan

There's no fixed deadline, and this document does not estimate durations — the build is being driven end-to-end with Claude Code, and hour/day counts stop being a useful planning unit under that arrangement. What still matters, and what this document is actually for:

- **The order.** Later steps depend on earlier ones in specific ways, noted per step.
- **What can run out of order.** Several steps have no real dependency on each other and can be picked up in any sequence, or interleaved — noted per step as "independent of."
- **The Definition of Done (DoD).** Every step ends with one. An unmet DoD means the next unit of work is closing that gap, not starting the next step — that discipline is what keeps an open-ended timeline from quietly producing a half-finished product, which is a real risk without day-count pressure to force the issue.

| # | Step | Depends on | Independent of |
|---|---|---|---|
| 1 | Foundations, environment, schemas locked | — | — |
| 2 | Data simulation engine | 1 | 5, 6 |
| 3 | Core detection layer (fast path) | 1, 2 | 5, 6 |
| 4 | The Safety Council (multi-agent core) | 1 (can start against hand-fed sample data) | 5, 6 |
| 5 | Regulatory Intelligence (Neo4j GraphRAG) | 1 | 2, 3, 4, 6 |
| 6 | Computer vision & real inference | 1 | 2, 3, 4, 5 |
| 7 | Cinematic frontend dashboard | 1 (shell can start against mocks); full wiring needs 3, 4 | 5, 6 (until wiring) |
| 8 | Flagship differentiators | 2, 3, 4, 5 | — |
| 9 | Full integration — all four pillars live, hardening | 3–8 | — |
| 10 | Visual polish, deck, rehearsal, packaging | 9 | — |

---

## Step 1 — Foundations, Environment & Schemas Locked

**Goal:** every later step has a stable contract to build against, so workstreams don't block each other later.

**Key tasks:**
- Repo structure: `/backend`, `/frontend`, `/data/scenarios`, `/docs` (already has our three planning docs).
- FastAPI skeleton (WebSocket-capable) + React skeleton, both booting with a "hello world" round trip.
- Acquire free API keys: **Groq**, **Gemini**, and a **Neo4j AuraDB Free** instance — verify each with one real test call, not just a saved key.
- Lock every data schema from `CORRIX_DATA_METHODOLOGY.md` as actual Pydantic models: zone definition + adjacency graph, sensor reading, compliance signal, permit record, shift record, **worker-location/badge-ping event**, CV/site-observation event (with `source`/`correlation_source` fields), audit-log entry, Council verdict (including `time_to_critical` as a distribution, not a scalar).
- Scaffold the MCP servers as empty stubs: Sensor Stream, Permit/Shift, Regulatory Intelligence (RAG + Knowledge Graph + audit corpus, one server), CV/Observation, **Worker Location** — five, deliberately consolidated (Section 0).
- `.env`/secrets handling, `scenarios/` folder convention for versioned YAML configs (including the `memory_split` field from the start, per `CORRIX_DATA_METHODOLOGY.md` §12.5 — cheaper to bake in now than retrofit later).

**Definition of Done:**
- FastAPI and React skeletons run locally.
- A real request succeeds against Groq, Gemini, and the Neo4j AuraDB instance.
- Every schema above exists as a typed model, imported by name (not hand-written JSON) anywhere it's later used.
- All five MCP server stubs boot and respond to a basic tool-list call.

---

## Step 2 — Data Simulation Engine

**Goal:** every scenario in the library produces deterministic, seeded, schema-valid synthetic data, per `CORRIX_DATA_METHODOLOGY.md` §3–§8 and §12.

**Key tasks:**
- Implement the OU-process gas simulator (Euler–Maruyama stepping, §3.2) with the three source-term shapes (ramp / step-decay / ramp-with-plateau, §3.3). Build `step()` as a standalone, reusable function — it gets called again in Step 8 as the Monte Carlo forecaster's engine, so it shouldn't be buried inline.
- Implement the procedural-compliance signal model for S1 (§4) — this is *not* the same code path as the gas simulator; keep them structurally separate, as designed.
- Implement permit and shift generators (§5, §6), including background "routine traffic" so the plant doesn't look artificially quiet outside a scenario.
- Implement the **worker-location/badge-ping generator** (§8.2) — zone-level pings, consistent with each scenario's scripted permit/shift context.
- Author the eight-zone plant layout JSON **including the zone-adjacency edge list** (§7) — needed by Step 8's evacuation routing, cheaper to author alongside the zone data now than retrofit later.
- Build the scenario-config engine: YAML → simulator parameters → seeded, reproducible output, with the `memory_split: population|held_out` field wired through from Step 1. Author configs for **S1, S2, S3, S4** first (the core/brief-named scenarios), with multiple seed variants per scenario per §12.5. S5 lands in Step 8 alongside the memory-loop feature it exists to demonstrate.
- Author matched-volume negative-control (`N1..Nk`) configs, also multi-seed and split.

**Definition of Done:**
- `run_scenario("S1", seed=X)` (and S2–S4) produces identical output on repeat runs with the same seed.
- Output validates against the Step 1 schemas with zero manual patching.
- A quick plot of each scenario's signal (gas ppm or compliance score) visibly matches the intended shape (ramp/step/plateau) described in the methodology doc.
- Worker-location pings for a scenario are consistent with that scenario's permit/zone context (a worker with an active permit in Z1 actually shows up in Z1).
- Negative-control runs exist in volume equal to positive runs, and every scenario instance carries a valid `memory_split` value.

---

## Step 3 — Core Detection Layer (Fast Path)

**Goal:** the cheap, explainable first pass that (a) triggers the Council and (b) doubles as the Evaluation Harness's baseline comparison — build it once, it serves both purposes.

**Key tasks:**
- Rolling z-score anomaly scorer per zone, consuming Step 2's simulated stream.
- Deterministic permit-conflict rule table (hot-work + high-hazard zone + elevated anomaly = conflict, etc.).
- Wire both into the Sensor Stream and Permit/Shift MCP servers stubbed in Step 1, so they're real tools now, not empty stubs.
- Define the event-trigger condition that will later convene the Safety Council (Step 4): anomaly score or permit-conflict crossing a configured threshold.

**Definition of Done:**
- Running S1–S4 through the anomaly scorer alone produces a HIGH/CRITICAL flag *at some point* in each run (accuracy against ground truth isn't judged yet — that's Step 8's Evaluation Harness).
- The permit-conflict checker correctly flags at least one scripted conflict (e.g., hot-work permit + rising gas zone).
- Both are callable as real MCP tools, verified with a manual test call, not just unit tests.

---

## Step 4 — The Safety Council (Multi-Agent Core)

**Goal:** the product's central intelligence, and — after validation review — the step where a real architectural correction lands: **agents must not share a single evidence context.**

**Key tasks:**
- Build the LangGraph state machine: four evidence agents (Process Safety Engineer, Permit Control Officer, Shift Operations, Site Safety Observer) + Chair synthesis node, event-triggered.
- **Scope each agent's MCP tool access to only its own data source(s)**, not a shared context: Process Safety Engineer → Sensor Stream MCP only; Permit Control Officer → Permit/Shift MCP only; Shift Operations → Permit/Shift MCP (roster/changeover data only); Site Safety Observer → CV/Observation + Worker Location MCP only. **Only the Chair node receives all four agents' structured outputs.** This is the fix for the identified flaw where a shared context would let any single agent notice the compound pattern alone, undermining the whole "only fusion catches it" thesis — verify this by construction, not just by convention (i.e., don't give an agent a tool it shouldn't have and rely on the prompt to tell it not to use it).
- Integrate Groq as the primary inference backbone (latency-critical path); integrate Gemini as secondary/multimodal + automatic failover (never load-balanced 50/50 — Gemini's free tier is materially tighter, see `CORRIX_PROJECT.md` §7.1).
- Prompt-engineer each persona against **hand-fed sample payloads first** — don't wait for Step 2/3 to be fully wired; a hardcoded S1-shaped JSON blob is enough to start.
- Implement the verdict schema exactly as specified in `CORRIX_PROJECT.md` §6.2. `time_to_critical` is a stub (simple placeholder) at this stage — the real Monte Carlo version lands in Step 8, once Step 2's `step()` function exists to reuse.
- Implement the Safety Officer Override as a real LangGraph interrupt/checkpoint, not a UI-only pause.

**Definition of Done:**
- Feeding a hand-crafted S1 evidence payload through the graph produces a plausible, well-formed four-agent + Chair verdict in a few seconds.
- **Verify the silo constraint directly:** confirm the Process Safety Engineer agent's tool set literally does not include permit, shift, or CV/worker-location tools (and so on for each agent) — this should be checkable by inspecting the agent's bound tool list, not just by reading its prompt.
- The same graph produces sensible, *differently-reasoned* verdicts on hand-crafted S2/S3/S4 payloads — proving the prompts generalize, not just fit one scripted case.
- Triggering an override mid-run demonstrably pauses the graph, accepts a human note, and the Chair's final output visibly incorporates it.
- Gemini failover verified by deliberately exhausting or blocking the Groq path once and confirming the graph still resolves.

**Independent of:** Steps 2 and 3's *live* stream (start against hand-fed mocks); Steps 5 and 6 entirely.

---

## Step 5 — Regulatory Intelligence (Neo4j GraphRAG)

**Goal:** one fully real data subsystem serving three of the brief's capabilities (RAG Q&A, pattern lookup, compliance checking) through a single interface and a single Neo4j AuraDB instance — not three separate agents. Covers all three regulatory frameworks the brief's Evaluation Focus actually names.

**Key tasks:**
- Design the graph schema: equipment–permit–zone–incident node/edge types.
- Download the real source PDFs (OISD, Factories Act 1948 — URLs in `CORRIX_PROJECT.md` §17) and chunk on clause/section boundaries, not fixed token windows (`CORRIX_DATA_METHODOLOGY.md` §11).
- **Select and verify specific DGMS circular(s) against `dgms.gov.in`**, and ingest them as supplementary corpus content, clearly tagged as such — per the honest-scoping rationale in `CORRIX_PROJECT.md` §7.3. Don't skip the verification step; don't cite a DGMS document that hasn't actually been checked.
- Load all chunks into Neo4j's native vector index (2026.01+ `SEARCH` clause) alongside the graph nodes — one database, not a ChromaDB/NetworkX split.
- Author the mocked near-miss/audit-log corpus (`CORRIX_DATA_METHODOLOGY.md` §10), each entry referencing a real clause number (OISD, Factories Act, or the newly-added DGMS material).
- Build **one** retrieval layer serving three query shapes against the same substrate: vector similarity for regulatory Q&A, graph traversal for "has this combination happened before," and a compliance-check mode that matches a mocked audit-log entry against a live-retrieved checklist and flags a deviation. All three exposed via a single Regulatory Intelligence MCP server — resist the urge to build three separate agents for three query shapes over the same data.

**Definition of Done:**
- A test question against the same chat interface returns: (a) an answer with a citation to a real, checkable OISD/Factories Act/DGMS section number, (b) a correct answer to a pattern-lookup question ("has a hot-work-near-gas pattern occurred before") from the mocked near-miss corpus, and (c) at least one correctly-flagged seeded compliance deviation (e.g., `missing_required_signature`) with a correct real-clause reference — all through the one interface, not three.
- A test question specifically scoped to DGMS returns a correctly-labeled "supplementary" answer, not a fabricated primary citation.

**Independent of:** Steps 2, 3, 4, 6 entirely — document sourcing and chunking has zero code dependency on any other step.

---

## Step 6 — Computer Vision & Real Inference

**Goal:** the second genuinely real subsystem, with the real/simulated split encoded in the data itself, per `CORRIX_DATA_METHODOLOGY.md` §9.

**Key tasks:**
- Fine-tune (or evaluate zero-shot first, fine-tune if needed) YOLO26 or YOLOv11 on the open Ultralytics Construction-PPE dataset.
- Build the live inference pipeline: webcam or sample-clip input → real bounding-box detections, timestamped as produced.
- Build the scripted correlation layer on top, now checked against the Step 2 **worker-location/badge-ping stream** rather than an implied badge system — e.g., "no matching badge-ping in Zone 1" — with `source: "real_inference"` / `correlation_source: "simulated"` encoded directly in the event schema, not just a UI label.
- Wrap as the CV/Observation MCP server; wire its output as the Site Safety Observer agent's evidence source (Step 4), alongside the Worker Location MCP server it also has access to.

**Definition of Done:**
- Live inference runs at acceptable FPS on actual demo hardware (test on the machine that will be used live, not a dev workstation with a better GPU).
- A detection event correctly carries both `source` and `correlation_source` fields, correctly valued, and the correlation check is actually querying the worker-location stream (not a hardcoded guess).
- The Site Safety Observer agent visibly changes its assessment when a CV event is present vs. absent, on an otherwise identical evidence payload.

**Independent of:** Steps 2, 3, 4, 5 entirely.

---

## Step 7 — Cinematic Frontend Dashboard

**Goal:** the command-center UI from `CORRIX_PROJECT.md` §11 — a first-class deliverable, not a wrapper.

**Key tasks:**
- Build the design system: color palette, typography, glassmorphism, against static/mock data first. **Bake in the colorblind-accessible design from the start** — pair every risk-state color with a distinct icon/shape, not color alone — cheaper to build in than retrofit after the palette is used everywhere.
- deck.gl geospatial heatmap with live zone-state color transitions (green→yellow→orange→red, eased, never instant) plus the isometric view toggle. **No 3D Digital Twin mode** — cut from scope (Section 0 above).
- **Live worker-location markers** on the map (Step 2's stream), with jitter so co-located workers are visually distinct.
- **Risk-aware evacuation route overlay** — highlighted path rendering, wired to Step 8's routing output once that lands.
- Safety Council live-reasoning panel (the five-icon "Council in session" moment) + Alert & Explanation feed.
- Regulatory RAG Assistant chat drawer.
- Top control bar: scenario selector, Counterfactual Replay toggle (wired fully in Step 8), an **Open Challenge** trigger (Step 8) for the novelty-detector demo moment, Incident Report download, ERO trigger indicator, Safety Officer Override control (wired to Step 4's real interrupt).
- Swap mock data for the live WebSocket stream once Steps 3 and 4 are running.

**Definition of Done:**
- The full shell renders correctly against mock data before any backend is wired — this de-risks Steps 3/4 running late.
- Once wired: picking a scenario, watching the simulator stream, the Council convene and render its reasoning live, and the heatmap update (with worker markers moving) — all work end-to-end in the browser for at least one scenario (S1).
- The Override control demonstrably pauses/resumes a live Council run from the UI.
- Risk-state colors are distinguishable without relying on color alone (verify with a colorblind-simulation filter, not just by eye).

**Independent of:** Steps 5 and 6, until live-data wiring — the shell work starts immediately against mocks.

---

## Step 8 — Flagship Differentiators

**Goal:** the features that make Corrix more than "a dashboard with alerts" — this is where the project's actual competitive edge lives, and where most of the validation-driven rigor fixes land.

**Key tasks:**
- **Joint-Evidence Novelty Detector** (`CORRIX_PROJECT.md` §6.7, `CORRIX_DATA_METHODOLOGY.md` §13): fit a lightweight density/reconstruction model (start with the simplest thing that works — a Mahalanobis-distance score against a fitted distribution — before reaching for an autoencoder) on the joint evidence vector across all `memory_split: population` negative-control runs from Step 2. Wire it as a second, independent trigger path into the Council alongside the existing rule/threshold trigger from Step 3, tagging novelty-triggered verdicts with `trigger_reason: "novelty"` rather than a named scenario.
- **The Open Challenge demo capability:** extend the scenario engine (already config-driven, Step 2) so a valid evidence combination can be assembled live from a small set of exposed parameters (zone, permit type, gas trend, timing) rather than only from the five pre-authored configs. Pre-generate and validate a curated set of unscripted-but-known-good combinations for this — genuinely unrehearsed per demo run, not a live system with zero safety net.
- **Counterfactual Replay Engine:** deterministic "legacy/siloed" path alongside the live Corrix path, synchronized scrubber UI, across all scenarios.
- **Evaluation Harness:** batch script running the Step 3 baseline vs. the full Step 4 pipeline across the complete scenario library (S1–S5 + negative controls, multi-seed — author **S5 now**, per `CORRIX_DATA_METHODOLOGY.md` §12.3), computing precision/recall, false-negative rate, and lead time against the code-level ground truth (§14.1). Feed results into the in-app Evaluation Report tab as charts, not a spreadsheet screenshot.
- **Confidence calibration reliability diagram** (`CORRIX_DATA_METHODOLOGY.md` §14.2) — bucket verdicts by stated confidence, compute empirical accuracy per bucket, plot against the diagonal. This reuses the harness's existing ground-truth data; it's an additional computation, not a new subsystem.
- **Time-to-Critical forecaster:** replace Step 4's stub with the real Monte Carlo rollout (§3.6) — N forward paths from the live simulator's own `step()` function, reporting a median + interquartile band, not a point estimate.
- **Self-improving memory loop, with the held-out split enforced:** store Evaluation Harness misses from `memory_split: population` runs as exemplars in the Neo4j vector index; retrieve the 1–2 most similar past misses at Chair synthesis time; **re-run the harness on the `held_out` subset only**, before and after the memory loop is populated, and keep both result sets. This before/after comparison, measured on cases the loop never saw, is the actual proof — not a demo trick.
- **Risk-aware evacuation routing:** Dijkstra over the Step 2 zone-adjacency graph, risk-weighted (`CORRIX_DATA_METHODOLOGY.md` §8.3), triggered on HIGH/CRITICAL, feeding Step 7's route overlay and attached to the ERO output (Step 9).
- **SWaT validation script:** the statistical-comparison procedure from `CORRIX_DATA_METHODOLOGY.md` §15, producing the calibration table/plot for the deck and the Evaluation Report tab.

**Definition of Done:**
- The novelty detector convenes the Council on at least one genuinely unscripted combination (not any of S1–S5, not a held-out seed variant of one) that no rule/threshold in Step 3 would have caught alone — that's the actual proof it does something the five authored scenarios don't.
- At least 5 curated Open Challenge combinations run cleanly end-to-end, each correctly flagged and explained with `trigger_reason: "novelty"`.
- Evaluation Report tab shows real, computed numbers (not placeholders) for both baseline and full pipeline, across the whole scenario library, including the calibration reliability diagram.
- Counterfactual Replay works end-to-end, scrubbing correctly, on at least S1 plus one more scenario.
- The Time-to-Critical forecast updates live, shows a band (not a point), and the band visibly tightens as a scenario progresses toward its scripted threshold.
- A documented, reproducible false-negative-rate change exists between the pre-memory-loop and post-memory-loop harness runs, **computed only on the held-out subset** — save both result files, don't just remember the numbers.
- A CRITICAL verdict produces a valid evacuation route that visibly avoids any other currently-unsafe zone in the test case.
- The SWaT comparison table is generated by a runnable script, not hand-typed.

---

## Step 9 — Full Integration: All Four Pillars Live, ERO, Hardening

**Goal:** one running app where all four pillars (`CORRIX_PROJECT.md` §8 — covering all six official sub-directions) and every flagship feature work together, reliably, repeatedly.

**Key tasks:**
- Emergency Response Orchestrator: real webhook (Slack/Discord/email) firing on CRITICAL, timestamped/hashed evidence snapshot, **the Step 8 evacuation route attached**, auto-attached to the Incident Intelligence Report.
- Incident Intelligence Report generator (HTML→PDF).
- Wire S5 (silent near-miss) fully into the live pipeline, not just the offline harness.
- Stand up Corrix's outward-facing MCP server (the "dual-role MCP" story, `CORRIX_PROJECT.md` §7.2) — test with an actual external MCP client call, not just a code review.
- Regression pass: every scenario **and** every negative control run 5–10 times back to back, checking for consistent, reliable triggering.
- **Measure actual LLM call volume against free-tier limits** during a realistic demo run-through (3 scenarios + Q&A) and confirm it stays comfortably under Groq's 30 RPM — this was a calculation in `CORRIX_PROJECT.md` §7.1, this step is where it becomes a measurement.
- Build and test the cached-fallback path for LLM API latency/failure during a live run.
- Cross-device/responsiveness check (tablet/laptop, not just the presenter's machine).

**Definition of Done:**
- All four pillars are demonstrably live, in the same running app, in a single sitting.
- The ERO fires a real, visible notification during a test run, with a valid evacuation route attached.
- Regression pass shows consistent triggering across repeated runs for every scenario.
- Deliberately blocking the primary LLM path mid-run still resolves to a sensible fallback, tested at least once.
- An external MCP client can successfully query Corrix's exposed risk-state endpoint.
- Measured call volume from a realistic demo run stays within free-tier headroom, with margin.

---

## Step 10 — Visual Polish, Pitch Deck, Rehearsal & Packaging

**Goal:** package everything built into something that reads as finished, not assembled — and prove it works live, repeatedly, before it has to.

**Key tasks:**
- Signature visual moments: particle-based gas-dispersion overlay, pulsing zone borders, the "Council in session" animation polish, worker-marker and evacuation-route rendering polish.
- Export the architecture diagram (from `CORRIX_PROJECT.md` §5's mermaid source), record the demo video.
- Build the pitch deck directly from `CORRIX_PROJECT.md`'s differentiator list (§9) and judging-criteria mapping (§14) — the source material already exists, this step is assembly and rehearsal, not fresh writing.
- Write and rehearse the demo script; insert the real Evaluation Report numbers from Step 8 (not placeholders), including the held-out-set memory-loop result and the calibration diagram.
- **Rehearse the Open Challenge moment specifically** — run it against several of the curated unscripted combinations from Step 8, confirm it resolves cleanly within demo time, and have a clear, honest line ready for what "unrehearsed" actually means here (curated-random, not zero safety net — Section 6.7).
- Deploy the public read-only Render/Railway instance for async judge exploration (per `CORRIX_PROJECT.md` §7.1) and keep it warmed before it's needed.
- Reserve a final buffer for bug fixes only — no new features once this step starts.

**Definition of Done:**
- At least two full, live-demo run-throughs, including a deliberately induced failure and graceful recovery, and at least one full run-through of the Open Challenge moment.
- Deck finalized with real numbers, not placeholders.
- Architecture diagram, demo video, and build/deploy instructions packaged and ready.
- Public demo instance deployed, reachable, and pre-warmed.

---

## What Was Deliberately Cut, and Why

Consistent with the principle that an open-ended timeline should still have a finish line: this plan does **not** include a full 3D "Digital Twin" (CesiumJS) visualization mode. It was the single largest optional time investment in the original version of this plan, no judging criterion specifically rewards it over what deck.gl + isometric already delivers, and the validation pass found several higher-value, cheaper fixes (agent silos, worker-location data, held-out validation, evacuation routing, calibration reporting) that were a better use of the same effort. It remains a documented, credible roadmap item (`CORRIX_PROJECT.md` §16) — a real next step once the core product is proven, not a feature the core product's success depends on.
