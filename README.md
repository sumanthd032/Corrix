<div align="center">

<h1>CORRIX</h1>

### The correlation layer industrial safety never had

**AI-powered industrial safety intelligence that detects _compound risk_: dangerous combinations of ordinary-looking conditions that no single sensor, system, or team would flag alone.**

<br>

[![Tests](https://img.shields.io/badge/tests-415%20passing-2ea44f?style=flat-square)](#testing)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](#technology)
[![Node](https://img.shields.io/badge/Node-22-5FA04E?style=flat-square&logo=nodedotjs&logoColor=white)](#technology)
[![License](https://img.shields.io/badge/license-proprietary-8a97a8?style=flat-square)](#license)
[![Status](https://img.shields.io/badge/status-deployed-2dd4e8?style=flat-square)](#deployment)

<br>

**Backend**&nbsp;
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=flat-square&logo=neo4j&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036?style=flat-square)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=flat-square&logo=googlegemini&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-000000?style=flat-square)
![MQTT](https://img.shields.io/badge/MQTT-660066?style=flat-square)
![YOLO](https://img.shields.io/badge/YOLO11-111F68?style=flat-square)

**Frontend**&nbsp;
![React](https://img.shields.io/badge/React_19-20232A?style=flat-square&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_v4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)
![deck.gl](https://img.shields.io/badge/deck.gl-000000?style=flat-square)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=flat-square&logo=threedotjs&logoColor=white)

<br>

[Overview](#overview) · [Capabilities](#capabilities) · [Architecture](#architecture) · [Quick start](#quick-start) · [Real vs. simulated](#what-is-real-vs-simulated) · [Documentation](#documentation)

</div>

---

## Overview

A rising gas reading is routine. A hot-work permit is routine. A hot-work permit in a zone where gas is trending up, right before a shift changeover, with a worker present, is a **compound risk** that no single safety system catches, because no single system holds all four facts at once. This is the exact failure mode behind the June 2025 Visakhapatnam Steel Plant incident that anchors this project.

Corrix closes that gap. It fuses five normally-siloed streams, gas and process sensors, permit-to-work records, shift schedules, computer vision, and worker location, into one reasoning layer. When the combination turns dangerous, a five-agent AI Safety Council convenes, rules with an explainable, regulation-cited verdict, forecasts time-to-critical, draws a risk-aware evacuation route, and can fire a real emergency notification. Alongside the built-in scenarios, a **Bring Your Own Factory** path lets any facility onboard its own zones and stream live data over MQTT into the same engine.

---

## Capabilities

| Capability | What it does |
|---|---|
| **The Safety Council** | Five agents on a LangGraph state machine (Process Safety Engineer, Permit Control Officer, Shift Operations, Site Safety Observer, and a synthesizing Chair). Each agent can only query the data source its real-world counterpart would have, so compound risk emerges from fusion by construction. |
| **Three detection triggers** | Rule/threshold, a joint-evidence novelty detector that catches unscripted combinations, and memory retrieval against stored past misses. Any one convenes the Council; the verdict records which fired. |
| **Safety Officer Override** | A real human-in-the-loop interrupt: the Council pauses 8 seconds for a human note before the Chair rules. |
| **Time-to-Critical forecasting** | A per-zone probability band via Monte Carlo rollout over the simulator's own physics, not a bare countdown. |
| **Interactive what-if mitigation** | Test an intervention (isolate the source, add ventilation, suspend the permit) and see the predicted change in time-to-critical before acting. |
| **Risk propagation + evacuation** | Predicts where a compound risk could spread across the plant's adjacency graph, and routes evacuation around other unsafe zones. |
| **Grounded regulatory citations** | Every verdict cites the specific OISD, Factories Act 1948, or DGMS clause it is grounded in, retrieved from a live Neo4j GraphRAG substrate. |
| **Self-improving memory loop** | Learns from its own past misses, with the improvement measured only on a held-out set it never trained on (30% to 0% miss rate). |
| **Geospatial command center** | A live deck.gl heatmap with isometric and real 3D plant views, live worker markers, and the Council convening rendered as a 3D scene. |
| **Counterfactual Replay** | A synchronized split-screen showing what a legacy single-signal system would have seen versus what Corrix catches, with real lead time. |
| **Emergency Response Orchestrator** | Fires a real notification with a timestamped, SHA-256-hashed evidence snapshot on a CRITICAL verdict, plus a one-click PDF Incident Report. |
| **Bring Your Own Factory** | An onboarding wizard captures zones, the adjacency graph, workforce, and permits; live data then flows in over MQTT, CSV historian replay, or virtual sensors, into the same reasoning engine. |
| **Corrix as an MCP provider** | The live compound-risk state is exposed back out over the Model Context Protocol, so any external agent can query it directly. |

---

## Architecture

```mermaid
flowchart TB
    subgraph SRC["1a · Scripted demo · simulated streams"]
        direction LR
        GAS["Gas and process<br/>sensors"]
        PER["Permit-to-work"]
        SHF["Shift schedules"]
        CVS["Computer vision<br/>(real YOLO)"]
        LOC["Worker location"]
    end

    subgraph BYO["1b · Bring your own factory · live"]
        direction LR
        WIZ["Onboarding wizard<br/>zones + adjacency graph"]
        MQT["MQTT broker · CSV replay ·<br/>virtual sensors"]
    end

    MCP["2 · MCP Tool Layer<br/>one server per data source"]

    subgraph DET["3 · Compound-Risk Detection"]
        direction LR
        RULE["Rule + threshold"]
        NOV["Joint-evidence<br/>novelty detector"]
        MEM["Memory retrieval"]
    end

    subgraph CNCL["4 · Safety Council · LangGraph, agents siloed by construction"]
        direction LR
        A1["Process Safety<br/>Engineer"]
        A2["Permit Control<br/>Officer"]
        A3["Shift<br/>Operations"]
        A4["Site Safety<br/>Observer"]
        CHAIR{{"Chair<br/>synthesizes · 8 s human override"}}
    end

    REG[("5 · Regulatory Intelligence<br/>Neo4j GraphRAG<br/>OISD · Factories Act · DGMS")]

    subgraph OUT["6 · Verdict enrichment + response"]
        direction LR
        FC["Time-to-critical ·<br/>evacuation route ·<br/>risk propagation · what-if"]
        CIT["Grounded regulatory<br/>citations"]
        ERO["Emergency Response<br/>hashed-evidence email"]
        RPT["Incident Report<br/>PDF"]
    end

    UI["Command Center UI + Live Command Center<br/>heatmap · 3D plant · Council · alerts"]
    EXT["Corrix as MCP provider<br/>external clients query live risk"]

    SRC --> MCP
    BYO --> MCP
    MCP --> DET
    MCP -. "agents query own server" .-> CNCL
    DET -- "trigger" --> CNCL
    A1 --> CHAIR
    A2 --> CHAIR
    A3 --> CHAIR
    A4 --> CHAIR
    CHAIR --> REG
    CHAIR --> OUT
    REG --> CIT
    OUT --> UI
    DET --> UI
    CHAIR --> EXT

    classDef accent stroke:#2dd4e8,stroke-width:2px;
    class CHAIR,REG accent;
```

A print-ready one-page version lives at [`docs/corrix_architecture.pdf`](docs/corrix_architecture.pdf). The full layer-by-layer description, data strategy, and evaluation methodology are in [`docs/CORRIX_PROJECT.md`](docs/CORRIX_PROJECT.md).

---

## Technology

**Backend** &nbsp;·&nbsp; Python 3.13 · FastAPI · LangGraph · the official MCP SDK · Groq (primary inference) with Gemini (fallback) · Neo4j AuraDB with native vector search (GraphRAG) · sentence-transformers (local embeddings) · Ultralytics YOLO11 (computer vision) · paho-mqtt (live ingestion) · Playwright/Chromium (PDF generation) · NumPy and pandas.

**Frontend** &nbsp;·&nbsp; React 19 · TypeScript · Vite · Tailwind CSS v4 · deck.gl (2D geospatial) · React Three Fiber (3D) · Framer Motion (animation) · Zustand (state).

---

## Prerequisites

- **Python 3.13**, **Node.js 22** with npm, and **Git**
- For the full live backend (optional for the visual demo):
  - A **Groq** API key ([free tier](https://console.groq.com))
  - A **Gemini** API key ([free tier](https://aistudio.google.com/app/apikey))
  - A **Neo4j AuraDB Free** instance ([free tier](https://neo4j.com/cloud/aura-free/)): connection URI, username, password
  - Optionally, SMTP credentials for the Emergency Response Orchestrator's email alerts

### What is not in this repository

These are intentionally excluded from git (see `.gitignore`); the setup steps below regenerate or supply each one.

| Not in git | What it is | How you get it |
|---|---|---|
| `.env` | Your real API keys and credentials | Copy `.env.example` to `.env` and fill it in (step 2) |
| `backend/.venv/`, `frontend/node_modules/` | Dependency environments | Recreated by the setup steps |
| `frontend/dist/` | Production frontend build | `npm run build` (only for the Docker path) |
| `backend/runs/`, `backend/*.pt`, `backend/datasets/` | Trained CV weights and training data | The CV pipeline falls back to a base YOLO11n model, auto-downloaded on first use. Retraining is optional: `backend/scripts/train_ppe_model.py` |
| `data/swat/` | The access-restricted real SWaT dataset | Not needed to run Corrix; its validation result is committed at `data/evaluation/swat_validation.json` |

Everything else the app needs at runtime is committed: the scenario library, the plant layout, the regulatory source PDFs and corpus, and the precomputed evaluation results, all under `data/`.

---

## Quick start

```bash
git clone https://github.com/sumanthd032/Corrix.git
cd Corrix
```

### Option A: visual demo, no credentials needed (fastest)

The frontend runs as a complete visual demo on built-in data, with no backend and no API keys.

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`) and select **Launch live demo**. The top-bar indicator reads **Backend offline**, which is expected without a backend, and the dashboard runs on representative data.

### Option B: full live system

**1. Backend environment**

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install --force-reinstall --no-deps opencv-python-headless==5.0.0.93
python -m playwright install chromium
```

> The second `pip install` is not optional. `ultralytics` pulls in the GUI build of OpenCV, which overwrites the headless build and breaks Linux/Docker environments that lack `libGL`. Re-asserting the headless build last keeps every environment working.

**2. Credentials**

```bash
# from the repo root
cp .env.example .env      # Windows: copy .env.example .env
```

Set `GROQ_API_KEY`, `GEMINI_API_KEY`, and the three `NEO4J_*` values at minimum. The ERO email settings are optional; without them the app runs and simply does not send alerts. **Never commit `.env`.**

**3. Populate Neo4j (one time, idempotent)**

```bash
cd backend
python scripts/setup_neo4j.py
```

**4. Run the backend**

```bash
uvicorn app.main:app --reload --port 8000
```

Confirm with `curl http://localhost:8000/health`.

**5. Run the frontend**

```bash
cd frontend
npm install     # if not already done
npm run dev
```

Open `http://localhost:5173`. It must be port **5173**, the only development origin the backend's CORS allows; if Vite picks another port, free 5173 or set `CORRIX_EXTRA_CORS_ORIGIN` in `.env`. After launching the demo, the top-bar indicator reads **LIVE**.

---

## Testing

```bash
cd backend
pytest
```

**415 tests** cover schemas, simulation, every detection path, the Council graph and its silos, regulatory ingestion and retrieval, the MCP servers (including a real external-client round trip), the evaluation harness, calibration, the memory loop, evacuation routing, the ERO, and the Incident Report generator. Tests that make real Groq/Gemini or Neo4j calls skip cleanly on a genuine rate limit rather than failing.

---

## Deployment

The deployed instance is a **single service**: the backend serves the API, the WebSocket, and the built frontend from one FastAPI process. The `Dockerfile` builds exactly that.

```bash
# from the repo root
docker build -t corrix .
docker run -p 8000:8000 --env-file .env corrix
```

Then open `http://localhost:8000`. Run `python scripts/setup_neo4j.py` once against the Neo4j instance the deployed app uses. A live instance runs at `https://corrix.duckdns.org` on free-tier hardware; the first scenario after a cold start takes 20 to 30 seconds while models warm.

---

## What is real vs. simulated

Corrix is deliberate about this, and it is part of the strategy.

**Genuinely real** &nbsp;·&nbsp; the LLM reasoning (Groq/Gemini), the Neo4j GraphRAG substrate and its retrieval, the regulatory source text, the computer-vision inference (a real YOLO forward pass), the MCP integration in both directions, the MQTT ingestion path, the Monte Carlo forecaster, the evaluation methodology, and the SWaT external validation.

**Calibrated simulation** &nbsp;·&nbsp; the gas, permit, shift, and worker-location streams, because no public real Indian plant SCADA dataset exists. The gas simulator uses an Ornstein-Uhlenbeck process, and its noise-to-signal ratio (0.043 to 0.055) was validated to fall inside the real SWaT industrial dataset's observed range (0.012 to 0.117).

The in-app **Behind the Data** page (top bar) explains all of this visually.

---

## Project structure

```
Corrix/
├── backend/
│   ├── app/
│   │   ├── api/           FastAPI routes, scenario + live-factory WebSockets, what-if
│   │   ├── council/       The Safety Council (LangGraph, agents, Chair, LLM client)
│   │   ├── cv/            Computer-vision inference (YOLO)
│   │   ├── detection/     Anomaly scoring, novelty, forecasting, evacuation, propagation
│   │   ├── emergency/     Emergency Response Orchestrator
│   │   ├── evaluation/    Evaluation harness, calibration, SWaT validation
│   │   ├── ingestion/     Bring Your Own Factory: MQTT, CSV replay, virtual sensors
│   │   ├── mcp_servers/   The five inward + one outward MCP servers
│   │   ├── memory/        Self-improving memory exemplar store
│   │   ├── regulatory/    Neo4j GraphRAG ingestion and retrieval
│   │   ├── reporting/     PDF Incident Report generator
│   │   ├── schemas/       Pydantic models (single source of truth for data shapes)
│   │   ├── simulation/    Physics-informed data generators and scenario engine
│   │   └── state/         Live risk state and incident alert state
│   ├── scripts/           Setup, evaluation, training, and diagnostic scripts
│   └── tests/             415 tests
├── frontend/
│   └── src/               Components, Zustand store, WebSocket hooks, plant layout
├── data/                  Scenarios, plant layout, regulatory sources, evaluation results
├── docs/                  Problem statement, project doc, data methodology, architecture
└── Dockerfile             Single-service production image
```

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/PROBLEM_STATEMENT.md`](docs/PROBLEM_STATEMENT.md) | The official brief, formatted verbatim |
| [`docs/CORRIX_PROJECT.md`](docs/CORRIX_PROJECT.md) | The full project: features, data strategy, evaluation, architecture |
| [`docs/CORRIX_DATA_METHODOLOGY.md`](docs/CORRIX_DATA_METHODOLOGY.md) | Exact data and simulation formulas |
| [`docs/corrix_architecture.pdf`](docs/corrix_architecture.pdf) | One-page architecture diagram |

---

## Troubleshooting

- **The top bar shows "Backend offline"**: the backend is not reachable. Confirm it is on port 8000 and the frontend on 5173; the dashboard runs on representative data until it reconnects.
- **`ImportError: libGL.so.1` (Linux/Docker)**: the OpenCV headless step was skipped; re-run the `--force-reinstall --no-deps opencv-python-headless` line.
- **Regulatory chat or pattern lookup returns nothing on the live backend**: Neo4j was not populated; run `python scripts/setup_neo4j.py`.
- **A Council convening returns a low-confidence "fallback" verdict**: both LLM providers were rate-limited or unreachable; this is the intended graceful degradation, not a crash.

---

## License

Proprietary. All rights reserved. Not licensed for reuse or redistribution without permission.
