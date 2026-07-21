# Corrix

### The correlation layer industrial safety never had

Corrix is an AI-powered industrial safety intelligence platform. It fuses five normally-siloed data streams, gas and process sensors, permit-to-work records, shift schedules, computer-vision site observation, and worker location, into one reasoning layer that detects compound risk: dangerous combinations of individually-ordinary conditions that no single system would flag alone. When a compound risk is detected, a five-agent AI Safety Council convenes, reaches an explainable verdict with cited regulatory grounding, forecasts time-to-critical, computes a risk-aware evacuation route, and can fire a real emergency notification. All of it surfaces on a live command-center dashboard.

This document describes the project as built. For the exact data and simulation formulas, see `CORRIX_DATA_METHODOLOGY.md`. For the original brief, see `PROBLEM_STATEMENT.md`. For setup and running, see the repository `README.md`.

---

## 1. The problem

A modern plant runs five or more safety systems that are each individually competent and collectively blind to each other:

| System | What it sees | What it is blind to |
|---|---|---|
| Gas / IoT sensors | Gas concentration per zone | Whether a work permit is active nearby |
| SCADA | Process control parameters | Permit status, human activity in the zone |
| Permit-to-work | Who is authorized to do what, where, when | Live sensor conditions in that zone |
| CCTV | Visual record of activity | Sensor readings, permit status |
| Shift and maintenance logs | Historical work record | Real-time correlation with current conditions |

Danger routinely emerges from the intersection of two or more of these, not from any one crossing a threshold on its own. A rising gas reading is routine. A hot-work permit is routine. A hot-work permit in a zone where gas is trending up, right before a shift changeover, with a worker present, is a compound risk that no single system is built to catch, because no single system holds all four facts at once.

### The anchor incident, cited accurately

On 8 June 2025, eight workers at the Visakhapatnam Steel Plant were killed when entrapped gases inside a ladle of molten steel triggered a sudden explosion during a routine casting operation at Steel Melting Shop 2. A preliminary investigation by the Chief Inspector of Factories, Andhra Pradesh, attributed the explosion to gas entrapped in the liquid steel. The signal existed in the physical system. No layer connected it to the fact that a lifting and casting operation was actively underway in that exact location, at that exact moment.

The official problem statement describes a January 2025 coke-oven incident at the same plant. Our research could not independently verify that framing; the closest verified match is the June 2025 ladle event described above, confirmed across multiple outlets including The Wire. Corrix cites the version that checks out. This correction is deliberate and is part of the project's honesty posture.

---

## 2. What Corrix does

### Detection: three independent triggers

Any of three paths can convene the Safety Council. Whichever fires earliest wins, and every verdict records which one did (`trigger_reason`).

1. **Rule and threshold.** Rolling z-score anomaly scoring per zone plus a deterministic permit-conflict rule table. Fast and fully auditable. Also serves as the evaluation baseline.
2. **Joint-evidence novelty.** A Mahalanobis-distance model over the full joint evidence vector, fit on normal-day runs. It escalates statistically unusual combinations that match no scripted pattern, so the system is not limited to a memorized list of scenarios.
3. **Memory retrieval.** Similarity against stored past misses. It catches the sub-threshold recurrence the other two paths would let pass.

### Reasoning: the Safety Council

Five specialized agents orchestrated as a LangGraph state machine:

| Agent | Perspective | Data access |
|---|---|---|
| Process Safety Engineer | Is the physical condition abnormal? | Sensor Stream MCP server only |
| Permit Control Officer | Is authorized work compatible with conditions? | Permit/Shift MCP server only |
| Shift Operations | Is human-factors risk elevated right now? | Permit/Shift MCP server only |
| Site Safety Observer | Does site observation corroborate or contradict? | CV/Observation and Worker Location servers only |
| Chair | What is the compound verdict? | All four agents' structured reports |

Each agent can query only the data source its real-world counterpart would have. No single agent sees the whole picture, so compound risk emerges from fusion at the architecture level, not just in the narrative. This mirrors, deliberately, the same silo structure that caused the real anchor incident.

Before the Chair rules, the graph pauses for 8 seconds. This is a real LangGraph interrupt: a Safety Officer can inject a note into checkpointed state and the Chair incorporates it. Inference runs on Groq first with automatic Gemini failover; if both providers fail, the system returns an honestly-labeled rule-based fallback verdict with zero stated confidence rather than a fabricated judgment.

Corrix is a decision-support system, not an autonomous control system. It notifies and documents. It never shuts down equipment or overrides a human.

### Foresight: attached to every verdict

- **Time-to-Critical forecast.** A Monte Carlo rollout reusing the simulator's own calibrated process model, producing a probability band ("68% chance of CRITICAL within 15 to 22 minutes"), not a falsely-precise countdown.
- **Risk-aware evacuation routing.** Dijkstra over the zone adjacency graph with edge weights inflated for other elevated zones, so the route avoids them on the way to the nearest safe assembly point.
- **Spatial risk propagation.** A blast-radius search estimating where the compound risk could migrate if uncontained, decaying by hop distance and weighted by each neighbour's hazard class.
- **What-if mitigation.** Test an intervention live. Physics-changing interventions re-run the real forecaster with a reduced source term; procedural interventions leave the physics unchanged and say so honestly.
- **Grounded regulatory citations.** Every verdict cites the specific OISD, Factories Act 1948, or DGMS clause it rests on, retrieved from the live knowledge graph. DGMS results are labeled supplementary.

### Regulatory Intelligence

One Neo4j GraphRAG substrate over real government source documents serves three query shapes through one interface: RAG chat ("what does the regulation say"), historical pattern lookup ("has this happened before"), and compliance checks against a mocked inspection log. Sources: the Factories Act 1948 full text, a real OISD guideline document, and a verified DGMS circular, chunked at clause boundaries with local sentence-transformer embeddings.

### Computer vision

A YOLO11 model fine-tuned on the open Construction-PPE dataset runs real inference on site footage, detecting people and PPE classes. The zone and badge correlation on top of a detection is checked against the simulated worker-location stream and is labeled as such in the schema itself, with `source` and `correlation_source` as distinct typed fields.

### Emergency response

On a CRITICAL verdict the Emergency Response Orchestrator fires a real notification carrying a timestamped, SHA-256-hashed evidence snapshot and the computed evacuation route. For any verdict, a one-click Incident Report generates a real PDF with the full evidence snapshot and, when fired, the ERO delivery hash.

### The command center

A React dashboard in a dark, instrument-grade command-center style: a deck.gl geospatial heatmap with flat, isometric, and real 3D plant views, gas-dispersion particles, pulsing risk borders, live worker markers, an animated evacuation route, the Council convening rendered as a 3D scene, a telemetry strip, a live alert feed, the regulatory chat drawer, and a full-viewport critical-alert takeover. Every risk state pairs color with a distinct shape for colorblind accessibility.

### Bring your own factory

Alongside the scripted demo, a second front door lets anyone onboard their own facility and drive the same engine with live data:

1. **Onboard.** A wizard captures the factory identity, zones with hazard classes, the adjacency graph (drawn in an interactive editor; this is the exact input the evacuation router and propagation model consume), workforce, shifts, and permit types.
2. **Connect.** Stream live readings over MQTT into a real broker, subscribe to a real OPC-UA server, replay a CSV historian export, or run the built-in virtual sensor publisher. No hardware is required, and every simulated device is labeled as simulated. Live external inputs pass through a character-allow-list sanitizer before reaching any agent, and the virtual sensor routes are rate-limited.
3. **Same engine.** The Council, detection triggers, forecaster, and router are the same objects the scripted demo calls. The data changes; the reasoning does not.

### Corrix as an MCP provider

Every internal data subsystem is an MCP server the Council consumes as a client, and the compound-risk state is exposed back out as an MCP server of its own. Any external MCP client can query the live risk picture directly, using the same protocol the Council uses internally.

---

## 3. Data strategy and honesty

No public dataset of real Indian plant SCADA, gas-sensor, or permit data exists. Every team addressing this problem faces the identical constraint. Corrix responds with a physics-informed, externally-validated simulation methodology, disclosed openly inside the product rather than hidden.

| Component | Status |
|---|---|
| LLM reasoning (Groq, Gemini failover) | Real |
| Neo4j GraphRAG substrate and retrieval | Real |
| Regulatory source text (OISD, Factories Act 1948, DGMS) | Real |
| Computer-vision inference (YOLO11 forward pass) | Real |
| MCP integration, both directions | Real |
| Monte Carlo forecaster and evaluation methodology | Real |
| MQTT and OPC-UA ingestion paths (broker, topics, subscriptions, parsing) | Real protocols, software publishers |
| Gas and process sensor streams | Simulated, physics-informed OU model |
| Permit-to-work and shift records | Simulated, mirroring real schemas |
| Worker location / badge-ping stream | Simulated, zone-level granularity |
| Near-miss and inspection-log corpus | Mocked, labeled illustrative |

Gas concentration follows a mean-reverting Ornstein-Uhlenbeck process with an injectable source term for scripted events. The simulator's noise-to-signal ratio (0.043 to 0.055) was validated to fall inside the range measured from the real SWaT industrial control system dataset (0.012 to 0.117). Full formulas and parameters are in `CORRIX_DATA_METHODOLOGY.md`.

---

## 4. Evaluation

All numbers come from the committed evaluation results in `data/evaluation/`, produced by the harness in `backend/app/evaluation/`, and are shown in-product with nothing smoothed over.

| Result | Value |
|---|---|
| Lead time over the legacy single-signal baseline (S2, S3) | +5 minutes |
| Held-out false-negative rate, before and after the memory loop | 30% to 0% |
| Precision, rule/threshold baseline | 100% (recall 80%) |
| Simulator noise-to-signal vs real SWaT range | 0.043 to 0.055, inside 0.012 to 0.117 |

Methodology safeguards:

- The scenario library is split into a memory-population set and a held-out set. The memory loop's improvement is reported only on held-out cases it never trained on, so it is a generalization result, not memorization.
- Negative controls are generated in matched volume to positive runs, so the false-positive rate is not cherry-picked.
- A confidence-calibration reliability diagram compares stated confidence against empirical accuracy.
- Disclosed trade-off: the full pipeline's overall recall trails the simple baseline on the current run, because the novelty path sometimes convenes the Council on evidence that is real but not yet dramatic enough for the Chair to call HIGH. This is reported, not hidden.
- The Open Challenge draws one of several pre-validated but unrehearsed evidence combinations live, proving the novelty path on a pattern nobody scripted for that run.

---

## 5. Architecture

Six layers, each a distinct part of the codebase. The one-page diagram lives at `corrix_architecture.pdf`.

1. **Ingestion, two front doors.** The scripted scenario engine (`backend/app/simulation/`) and the live BYOF path (`backend/app/ingestion/`, wizard, MQTT, OPC-UA, CSV replay, virtual sensors).
2. **MCP tool layer** (`backend/app/mcp_servers/`). One server per data source; each Council agent is scoped to only its own.
3. **Compound-risk detection** (`backend/app/detection/`). The three triggers, plus the forecaster, evacuation router, and propagation model.
4. **The Safety Council** (`backend/app/council/`). The LangGraph state machine, agents, Chair, and the failover LLM client.
5. **Regulatory Intelligence** (`backend/app/regulatory/`). Neo4j GraphRAG ingestion and retrieval over the real source documents.
6. **Response and surfaces.** The Emergency Response Orchestrator (`backend/app/emergency/`), the Incident Report generator (`backend/app/reporting/`), the FastAPI/WebSocket API (`backend/app/api/`), and the React command center (`frontend/`).

---

## 6. Technology

| Layer | Choice | Why |
|---|---|---|
| Agent orchestration | LangGraph | Native checkpointing and interrupts, which the Safety Officer Override requires structurally |
| Tool and data access | Model Context Protocol | One standard boundary for every data source, and the same protocol exposes Corrix back out |
| LLM inference | Groq primary, Gemini failover | Sub-second first tokens for a live convening; failover is automatic and tested |
| Knowledge substrate | Neo4j AuraDB with native vector search | One database serves both the knowledge graph and the RAG corpus |
| Computer vision | Ultralytics YOLO11, fine-tuned on Construction-PPE | Real inference on real footage, open dataset, license-compatible |
| Live ingestion | MQTT (paho-mqtt), OPC-UA (asyncua), WebSockets | The protocols real plants run; no hardware required to prove the integration |
| Backend | Python 3.13, FastAPI | Native WebSocket support, fast to build and test |
| Frontend | React 19, TypeScript, Vite, Tailwind v4, deck.gl, React Three Fiber, Framer Motion, Zustand | The command-center UI, 2D and 3D |
| Reports | Playwright/Chromium HTML-to-PDF | Real PDFs with the evidence snapshot |

---

## 7. Status

Built, tested, and deployed. The backend suite is 465 tests covering schemas, simulation, every detection path, the Council graph and its silos, regulatory ingestion and retrieval, the MCP servers including a real external-client round trip, the evaluation harness, calibration, the memory loop, evacuation routing, the ERO, the Incident Report generator, and the full BYOF ingestion path. A live instance runs at `https://corrix.duckdns.org` on free-tier hardware (the first scenario after a cold start takes 20 to 30 seconds while models warm).

---

## 8. Repository documentation

| Document | Covers |
|---|---|
| `README.md` | Setup, quick start, deployment |
| `docs/PROBLEM_STATEMENT.md` | The official brief, formatted verbatim |
| `docs/CORRIX_PROJECT.md` | This document |
| `docs/CORRIX_DATA_METHODOLOGY.md` | Exact data and simulation formulas |
| `docs/corrix_architecture.pdf` | The one-page architecture diagram |
| `docs/corrix_project_report.pdf` | The full project report |
