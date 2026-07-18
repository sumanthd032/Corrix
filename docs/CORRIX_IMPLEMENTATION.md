# Corrix: Implementation and Workflow

This document explains what Corrix actually is as built: every major component, how the pieces fit together, and the end-to-end runtime workflow from selecting a scenario to a verdict landing on screen. It describes the system as implemented, not the design intent. For the product vision and the reasoning behind each decision, see `CORRIX_PROJECT.md`; for the exact data and simulation formulas, see `CORRIX_DATA_METHODOLOGY.md`; for setup and running, see the root `README.md`.

## 1. What Corrix is

Corrix is an industrial safety intelligence platform. It fuses five normally-siloed data streams (gas and process sensors, permit-to-work records, shift schedules, computer-vision site observation, and worker location) into one reasoning layer that detects **compound risk**: dangerous combinations of individually-ordinary conditions that no single system would flag on its own. When a compound risk is detected, a five-agent AI Safety Council convenes, reaches an explainable verdict, forecasts time-to-critical, computes a risk-aware evacuation route, and can fire a real emergency notification, all surfaced on a command-center dashboard.

The core thesis: a rising gas reading is routine, a hot-work permit is routine, but a hot-work permit in a zone where gas is trending up right before a shift changeover is a compound risk, and the failure mode Corrix exists to close is that no existing system correlates those facts in time.

## 2. Architecture at a glance

The system is organized in layers, each a distinct part of the codebase:

1. **Data and Simulation** (`backend/app/simulation/`) produces physics-informed synthetic sensor, permit, shift, and worker-location data per scenario, plus a real computer-vision inference path (`backend/app/cv/`).
2. **MCP Tool Layer** (`backend/app/mcp_servers/`) exposes each data subsystem as a Model Context Protocol server. Each Safety Council agent is scoped to only the server(s) its real-world counterpart would have, so the compound-risk thesis is enforced at the architecture level, not just narratively.
3. **Compound Risk Detection Engine** (`backend/app/detection/`) runs the fast statistical and rule-based path, an independent joint-evidence novelty detector, a Monte Carlo time-to-critical forecaster, and risk-aware evacuation routing.
4. **The Safety Council** (`backend/app/council/`) is a LangGraph state machine: four evidence agents plus a synthesizing Chair, human-interruptible mid-reasoning.
5. **Regulatory Intelligence** (`backend/app/regulatory/`) is a Neo4j GraphRAG substrate over real OISD, Factories Act 1948, and DGMS source text, serving RAG chat, historical pattern lookup, and compliance checks through one interface.
6. **Specialized Outputs**: the geospatial heatmap, the alert and explanation feed, the Incident Intelligence Report generator (`backend/app/reporting/`), and the Emergency Response Orchestrator (`backend/app/emergency/`).
7. **Evaluation Harness** (`backend/app/evaluation/`) scores the whole pipeline against a labeled scenario library, including a held-out split for the self-improving memory loop and confidence-calibration reporting.
8. **Frontend** (`frontend/`) is a React command-center UI: a live deck.gl heatmap with a toggleable 3D plant view, the Council convening as a 3D scene, and full motion design.

An exported diagram of this architecture lives at `docs/assets/architecture_diagram.png` (and `.svg`).

## 3. Backend components

### 3.1 Schemas (`backend/app/schemas/`)

Every data shape in the system is a Pydantic model, so nothing downstream hand-writes JSON: `zone`, `sensor`, `compliance`, `permit`, `shift`, `worker_location`, `cv_observation`, `audit_log`, `scenario`, and `verdict`. The verdict schema models `time_to_critical` as a distribution (median, IQR band, escalation probability), not a scalar, and carries a `trigger_reason` field (`rule_threshold`, `novelty`, or `memory_retrieval`) recording which path convened the Council.

### 3.2 Simulation (`backend/app/simulation/`)

- `gas_process.py`: an Ornstein-Uhlenbeck baseline plus an injectable leak/accumulation source term (ramp, step-decay, ramp-with-plateau shapes), stepped by Euler-Maruyama. The same `step()` function is reused by the Monte Carlo forecaster.
- `compliance_process.py`: S1's procedural-compliance signal, a deliberately separate model from the gas process.
- `permit_generator.py`, `shift_generator.py`, `worker_location_generator.py`: seeded generators for the other evidence streams.
- `plant_layout.py`: loads the eight-zone plant and its adjacency graph from `data/layout/plant_layout.json`.
- `scenario_engine.py`: runs a scenario config end to end, deterministically from its seed, producing all evidence streams for the run.
- `open_challenge.py`: assembles valid, unscripted evidence combinations on demand for the live Open Challenge.

### 3.3 Detection (`backend/app/detection/`)

Three independent paths can convene the Council:

- **Rule and threshold** (`trigger.py`, `anomaly_scorer.py`, `permit_conflict.py`): rolling z-score anomaly detection plus a deterministic permit-conflict checker. This is also the Evaluation Harness baseline.
- **Joint-evidence novelty** (`novelty_detector.py`, `novelty_training.py`, `joint_evidence.py`): a Mahalanobis-distance model fit on the negative-control ("normal day") runs. It scores the full joint evidence vector, so it can escalate a statistically unusual combination that matches no scripted pattern, catching what nobody wrote down.
- **Memory retrieval** (`retrieval_trigger.py`): similarity against stored past misses, the path that lets the self-improving memory loop catch a sub-threshold recurrence (scenario S5).

Also here: `time_to_critical.py` (Monte Carlo rollout reusing the simulator's `step()`) and `evacuation_routing.py` (Dijkstra over the zone adjacency graph, with edge weights inflated for other elevated-risk zones so the route avoids them).

### 3.4 The Safety Council (`backend/app/council/`)

`graph.py` builds a LangGraph state machine. Four evidence-agent nodes (Process Safety Engineer, Permit Control Officer, Shift Operations, Site Safety Observer) run concurrently, each calling only its own bound MCP tools (`agents.py`); their outputs feed the Chair node (`chair.py`), which synthesizes the verdict. `interrupt_before=["chair"]` gives the Safety Officer Override a real pause point: the graph genuinely stops before the Chair runs, a human note is written into checkpointed state, and resuming incorporates it. `llm_client.py` is the Groq-primary, Gemini-fallback inference layer with bounded retry and a concurrency semaphore. If both providers fail, `chair.py` returns a deterministic, honestly-labeled fallback verdict (confidence 0.0, defaulted to HIGH, explanation stating synthesis was unavailable) rather than crashing.

### 3.5 MCP servers (`backend/app/mcp_servers/`)

Five inward-facing servers (`sensor_stream`, `permit_shift`, `worker_location`, `cv_observation`, `regulatory_intelligence`) the Council consumes as a client, plus one outward-facing server (`corrix_risk.py`) that exposes Corrix's own compound-risk verdicts back out over MCP, so any external MCP client (a judge's own Claude or Gemini session, for example) can query the live risk state directly.

### 3.6 Regulatory Intelligence (`backend/app/regulatory/`)

A unified Neo4j GraphRAG layer over real government source documents (`data/regulatory/sources/`): the Factories Act 1948, an OISD guideline, and a verified DGMS circular. `chunking.py` splits the PDFs at clause boundaries, `embeddings.py` computes local `sentence-transformers` (all-MiniLM-L6-v2) vectors, and `loader.py` ingests zones, equipment, permit types, chunked clauses, and a near-miss corpus into Neo4j with all graph edges wired. `retrieval.py` serves three query shapes over the same substrate: RAG chat ("what does the regulation say"), pattern lookup ("has this happened before"), and compliance checks against a mocked inspection log. DGMS results are honestly labeled supplementary.

### 3.7 Memory loop (`backend/app/memory/`)

`exemplar_store.py` stores each evaluation miss as a structured exemplar (evidence state, correct verdict, why) in the same Neo4j substrate. On a new convening, the retrieval trigger surfaces the most similar past misses, and the Chair receives them as `memory_context`. The before/after improvement is measured only on a held-out scenario split that never contributed exemplars, so it is a generalization result, not memorization.

### 3.8 Outputs

- **Emergency Response Orchestrator** (`backend/app/emergency/orchestrator.py`): on a CRITICAL verdict, fires a real notification (SMTP email as configured), attaches a timestamped, hashed evidence snapshot, and records the fired state.
- **Incident Report generator** (`backend/app/reporting/incident_report.py`): renders an HTML-to-PDF incident report via Playwright/Chromium, including the evidence snapshot and, if fired, the ERO delivery hash.

### 3.9 API (`backend/app/api/`)

`main.py` is the FastAPI app. `websocket.py` (`/ws/scenario`) streams a scenario playback frame by frame, convenes the Council live at the trigger tick, handles the 8-second override window, fires the ERO, and pushes verdicts. `evaluation.py`, `replay.py`, and `incident_report.py` are REST endpoints for the Evaluation Report, Counterfactual Replay timelines, and PDF generation. In a production build, `main.py` also serves the built frontend as static files, so the deployed instance is a single service.

### 3.10 Evaluation (`backend/app/evaluation/`)

`harness.py` scores baseline versus full pipeline across the whole scenario library. `calibration.py` produces a reliability diagram bucketing held-out verdicts by stated confidence against empirical accuracy. `swat_validation.py` compares the simulator's noise characteristics against the real SWaT industrial dataset. The precomputed results are committed under `data/evaluation/` and read by the live Evaluation Report.

## 4. Frontend components (`frontend/src/`)

- `App.tsx`: layout shell, the boot sequence gate, the ambient backdrop, and the critical-verdict takeover.
- `components/BootSequence.tsx`: a skippable, once-per-session cinematic HUD intro naming the real subsystems as they "initialize."
- `components/PlantHeatmap.tsx`: the deck.gl geospatial heatmap with three view modes (Flat / Isometric / 3D), gas-dispersion particles, pulsing risk borders, worker markers, and an animated evacuation route.
- `components/PlantScene3D.tsx`: a real React Three Fiber 3D plant view (orbit-controllable, risk-colored extruded zones with bloom, worker markers, animated evacuation route), toggled from the heatmap; the 2D view stays the default.
- `components/CouncilPanel.tsx` and `CouncilScene3D.tsx`: the Safety Council, with the convening rendered as a 3D scene (agent nodes streaming signal particles to a central Chair that recolors to the verdict risk level).
- `components/CriticalTakeover.tsx`: a full-viewport pulsing-red alert moment the instant a verdict first resolves CRITICAL.
- `components/AlertFeed.tsx`, `RegulatoryChatDrawer.tsx`, `RiskBadge.tsx`, `TopControlBar.tsx`, `CounterfactualReplayModal.tsx`, `EvaluationReportModal.tsx`: the alert feed, regulatory chat, colorblind-safe risk badges, scenario/control bar, and the two data modals, all with a Framer Motion pass.
- `store/useCorrixStore.ts`: Zustand state. `lib/useScenarioSocket.ts`: the WebSocket hook that drives the store from live backend messages and falls back to mock data when the backend is unreachable.
- `data/mockData.ts`: per-scenario mock bundles so the frontend runs as a full visual demo with no backend at all.

## 5. The end-to-end runtime workflow

A live run proceeds as follows:

1. **Connection.** The frontend opens a WebSocket to `/ws/scenario`. If it connects, the store enters `live` mode; if not, it stays in `mock` mode and everything still renders from `data/mockData.ts`.
2. **Scenario start.** Selecting a scenario sends a `start` message. The backend precomputes the full playback: it runs the scenario engine deterministically from the seed, producing all evidence streams, and decides the single trigger tick by checking all three detection paths (rule/threshold, novelty, retrieval-similarity) and taking whichever fires earliest.
3. **Playback.** The backend streams `tick` frames minute by minute. Each frame carries the per-zone risk levels and current worker positions; the heatmap animates from them.
4. **Convening.** At the trigger tick, the backend sends `council_convening`. The four evidence agents run concurrently, each querying only its own MCP data source, and the frontend shows the 3D convening scene.
5. **Override window.** The graph pauses for 8 seconds before the Chair (a real LangGraph interrupt). A Safety Officer can submit a note, which is written into checkpointed state; otherwise it resolves automatically.
6. **Verdict.** The Chair synthesizes the verdict (risk level, confidence, compound flag, explanation, recommended action) and the backend attaches the Monte Carlo time-to-critical forecast and, for HIGH/CRITICAL, the risk-aware evacuation route. The `verdict` message updates the Council panel, the heatmap route overlay, and the risk colors.
7. **Escalation.** On CRITICAL, the Emergency Response Orchestrator fires a real notification with a hashed evidence snapshot, the frontend shows the critical takeover, and the ERO indicator updates. An Incident Report PDF can be downloaded for any verdict.

Two special live flows sit alongside this: **Counterfactual Replay** (a synchronized scrubber comparing a legacy single-signal track against Corrix's compound-aware track, showing real lead time) and the **Open Challenge** (drawing one of several curated-but-unrehearsed evidence combinations and running it live through the novelty path).

## 6. Data and what is real versus simulated

Corrix is explicit about this, and it is part of the strategy. Committed to the repo under `data/`:

- `data/scenarios/`: five authored positive scenarios (S1-S5) and 25 negative controls, as seeded YAML configs.
- `data/layout/plant_layout.json`: the eight-zone plant and adjacency graph.
- `data/regulatory/sources/`: the real government PDF source documents.
- `data/regulatory/corpus/near_miss_corpus.yaml`: the near-miss corpus.
- `data/evaluation/*.json`: the precomputed, real Evaluation Harness, memory-loop, and SWaT-validation results.

**Genuinely real:** the LLM reasoning (real Groq/Gemini inference), the Neo4j GraphRAG substrate and its retrieval, the regulatory source text, the computer-vision inference (a real YOLO forward pass), the MCP integration in both directions, the Monte Carlo forecaster, the evaluation methodology, and the SWaT external validation.

**Calibrated simulation:** the sensor, permit, shift, and worker-location data streams, because no public real Indian plant SCADA dataset exists. The simulator's noise-to-signal ratio was validated to fall within the range measured from the real SWaT industrial dataset.

## 7. Headline evaluation results

From the committed `data/evaluation/` results, as shown in the pitch deck and demo script:

- Baseline (rule/threshold only): recall 80%, precision 100%, false-positive rate 0%.
- Full pipeline (+ novelty, real Council): recall 60%, precision 100%, false-positive rate 0% on that run. The lower recall is a disclosed finding, not hidden: the novelty path sometimes convenes the Council on evidence real but not yet dramatic enough for the Chair to call HIGH.
- Self-improving memory loop, held-out only: false-negative rate 30% to 0%, with a disclosed rise in false-positive rate (20% to 50%) on held-out negative controls.
- Counterfactual lead time: Corrix escalates 5 minutes ahead of the legacy track on S2 and S3, 1 minute on S4, and level on S1 (an honest, disclosed no-gap case).
- SWaT validation: the simulator's noise-to-signal ratio (0.043-0.055) falls within SWaT's own observed range (0.012-0.117).

## 8. Technology stack

- **Backend:** Python 3.13, FastAPI, LangGraph (Council orchestration), the official MCP SDK, Groq (primary inference) with Gemini (fallback and multimodal), Neo4j AuraDB with native vector search (GraphRAG), sentence-transformers (local embeddings), Ultralytics YOLO11n (computer vision), Playwright/Chromium (PDF generation), NumPy and pandas.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, deck.gl (2D geospatial), React Three Fiber with drei and postprocessing (3D), Framer Motion (animation), Zustand (state), lucide-react (icons).
- **Deployment:** a multi-stage Docker image serving both the API and the built frontend from one process, deployable to Render via `render.yaml`.

## 9. Testing

The backend has 382 passing tests under `backend/tests/`, covering schemas, simulation, every detection path, the Council graph and its silos, the cached-fallback path, regulatory ingestion and retrieval, the MCP servers (including a real external-client round trip), the evaluation harness, calibration, the memory loop, evacuation routing, the ERO, and the Incident Report generator. Tests that make real Groq/Gemini calls skip cleanly on a genuine rate limit rather than failing.
