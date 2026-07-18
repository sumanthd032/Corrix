<div align="center">

# Corrix

### The Correlation Layer Industrial Safety Never Had

AI-powered industrial safety intelligence that detects **compound risk**: dangerous combinations of ordinary-looking conditions that no single sensor, system, or team would flag alone.

</div>

---

## What Corrix does

Indian heavy industry runs five or more safety systems that are each individually competent and collectively blind to each other. A rising gas reading is routine. A hot-work permit is routine. A hot-work permit in a zone where gas is trending up, right before a shift changeover, is a compound risk that no single system is built to catch. Corrix fuses gas and process sensors, permit-to-work records, shift schedules, computer-vision site observation, and worker location into one reasoning layer that catches these combinations before they become incidents, with full explainable reasoning and minutes of lead time.

## Key features

- **The Safety Council**: five specialized AI agents (Process Safety Engineer, Permit Control Officer, Shift Operations, Site Safety Observer, and a synthesizing Chair), orchestrated as a LangGraph state machine. Each agent can only query the data source its real-world counterpart would have, so the compound-risk thesis is enforced by the architecture, not just claimed.
- **Joint-Evidence Novelty Detector**: catches compound risks that match no scripted pattern, proven live via the **Open Challenge**, which draws an unrehearsed evidence combination and runs it in front of the audience.
- **Self-improving memory loop**: learns from its own past misses, with the improvement measured only on a held-out set it never trained on (a generalization result, not memorization).
- **Live Time-to-Critical forecasting**: a per-zone probability band via Monte Carlo rollout, not a bare countdown.
- **Geospatial command center**: a live deck.gl heatmap with a toggleable real 3D plant view, live worker-location markers, and risk-aware evacuation routing that avoids other unsafe zones.
- **Counterfactual Replay**: a synchronized split-screen showing what a legacy single-signal system would have seen versus what Corrix catches, with real lead time.
- **Regulatory Intelligence**: a Neo4j GraphRAG layer over real OISD, Factories Act 1948, and DGMS source text, answering "what does the regulation say," "has this pattern happened before," and compliance checks through one interface.
- **Emergency Response Orchestrator**: fires a real notification with a timestamped, hashed evidence snapshot on a CRITICAL verdict, and a one-click PDF Incident Report.
- **Safety Officer Override**: a real human-in-the-loop interrupt: the Council pauses mid-reasoning for a human note before the Chair decides.
- **Corrix as an MCP provider**: the compound-risk state is exposed back out over MCP, so any external agent can query it directly.

For the full picture of how everything is built and how a run flows end to end, see **[`docs/CORRIX_IMPLEMENTATION.md`](docs/CORRIX_IMPLEMENTATION.md)**.

## Documentation map

| Document | What it covers |
|---|---|
| [`docs/CORRIX_IMPLEMENTATION.md`](docs/CORRIX_IMPLEMENTATION.md) | What is built, every component, and the end-to-end runtime workflow |
| [`docs/CORRIX_PROJECT.md`](docs/CORRIX_PROJECT.md) | Product vision, architecture, and the reasoning behind every decision |
| [`docs/CORRIX_DATA_METHODOLOGY.md`](docs/CORRIX_DATA_METHODOLOGY.md) | Exact data and simulation formulas |
| [`docs/CORRIX_BUILD_PLAN.md`](docs/CORRIX_BUILD_PLAN.md) | The ten-step build sequence |
| [`docs/demo_script.md`](docs/demo_script.md) | A timed, rehearsed live-demo script |
| [`docs/pitch_deck.html`](docs/pitch_deck.html) | The pitch deck (open in a browser) |

## Technology stack

**Backend:** Python 3.13, FastAPI, LangGraph, the official MCP SDK, Groq (primary inference) with Gemini (fallback and multimodal), Neo4j AuraDB with native vector search (GraphRAG), sentence-transformers (local embeddings), Ultralytics YOLO11n (computer vision), Playwright/Chromium (PDF generation).

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, deck.gl (2D geospatial), React Three Fiber (3D), Framer Motion (animation), Zustand (state).

---

## Prerequisites

- **Python 3.13**
- **Node.js 22** and npm
- **Git**
- For the full live backend (optional for the visual demo, see below):
  - A **Groq** API key ([free tier](https://console.groq.com))
  - A **Gemini** API key ([free tier](https://aistudio.google.com/app/apikey))
  - A **Neo4j AuraDB Free** instance ([free tier](https://neo4j.com/cloud/aura-free/)): connection URI, username, password
  - Optionally, SMTP credentials for the Emergency Response Orchestrator's email alerts

## What is NOT in this repository

Several folders are intentionally excluded from git (see `.gitignore`). After cloning, you will not have these, and the steps below tell you how each is regenerated or supplied:

| Not in git | What it is | How you get it |
|---|---|---|
| `.env` | Your real API keys and credentials | Copy `.env.example` to `.env` and fill it in (step 2) |
| `backend/.venv/` | Python virtual environment | Recreated by the setup steps |
| `frontend/node_modules/` | Frontend dependencies | Recreated by `npm install` |
| `frontend/dist/` | Production frontend build | Recreated by `npm run build` (only needed for the single-service/Docker path) |
| `backend/runs/`, `backend/*.pt`, `backend/datasets/` | Trained CV model weights and training data | The CV pipeline automatically falls back to a base YOLO11n model (auto-downloaded on first use). Retraining is optional and documented in `backend/scripts/train_ppe_model.py` |
| `data/swat/` | The access-restricted real SWaT industrial dataset | Not needed to run Corrix. It was used once, offline, to generate `data/evaluation/swat_validation.json`, which **is** committed |

Everything else the app needs at runtime **is** committed: the scenario library (`data/scenarios/`), the plant layout (`data/layout/`), the regulatory source PDFs and corpus (`data/regulatory/`), and the precomputed evaluation results (`data/evaluation/`).

---

## Quick start

### Clone

```bash
git clone <your-repo-url> Corrix
cd Corrix
```

### Option A: Visual demo, no credentials needed (fastest)

The frontend runs as a complete visual demo on built-in mock data, with no backend and no API keys. This is the quickest way to see the full UI, including the 3D plant view, the Council convening, and every scenario.

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`). The indicator in the bottom-left will read "mock data", which is expected without a backend.

### Option B: Full live system

This runs the real backend: real LLM reasoning, real Neo4j GraphRAG, and live scenario streaming.

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

> The second `pip install` is not optional. `ultralytics` pulls in the GUI build of OpenCV, which overwrites the headless build. On Windows/macOS nothing breaks, but it matters for Linux/Docker where the GUI build needs system libraries that are not present. Re-asserting the headless build last keeps both environments working.

**2. Credentials**

Copy the example env file to a real one at the **repository root** and fill in your values:

```bash
# from the repo root
cp .env.example .env      # Windows: copy .env.example .env
```

Set `GROQ_API_KEY`, `GEMINI_API_KEY`, and the three `NEO4J_*` values at minimum. The ERO (email alert) settings are optional; without them the app runs fine and simply does not send alerts. **Never commit `.env`.**

**3. Populate Neo4j (one time)**

A fresh AuraDB instance is empty. This loads the regulatory corpus and sets up the memory schema (idempotent, safe to re-run):

```bash
cd backend
python scripts/setup_neo4j.py
```

**4. Run the backend**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Confirm it is up: `curl http://localhost:8000/health` returns `{"status":"ok","service":"corrix-backend"}`.

**5. Run the frontend**

In a second terminal:

```bash
cd frontend
npm install     # if not already done
npm run dev
```

Open `http://localhost:5173`. It must be port **5173**, the only origin the backend's CORS policy allows in development. If Vite picks a different port because 5173 is busy, free up 5173, or set `CORRIX_EXTRA_CORS_ORIGIN` in `.env` to the origin Vite actually used. The bottom-left indicator should now read "backend live".

---

## Running the tests

```bash
cd backend
pytest
```

There are 382 tests. Some make real Groq/Gemini calls and real Neo4j reads; they skip cleanly on a genuine rate limit rather than failing.

## Production build and deployment

The deployed instance is a **single service**: the backend serves both the API/WebSocket and the built frontend from one FastAPI process, so there is no CORS to configure and nothing to run separately. This is exactly what the `Dockerfile` builds.

Build and run the production image locally:

```bash
# from the repo root
docker build -t corrix .
docker run -p 8000:8000 --env-file .env corrix
```

Then open `http://localhost:8000`.

To deploy to Render: push to GitHub, choose **New > Blueprint** in Render and point it at the repo (it reads `render.yaml`), and enter the real secrets (`GROQ_API_KEY`, `GEMINI_API_KEY`, `NEO4J_*`, and the ERO variables if wanted) through Render's dashboard when prompted. Remember to run `python scripts/setup_neo4j.py` once against the Neo4j instance the deployed app will use. The free plan cold-starts after inactivity, so visit the URL once a minute or two before any demo.

## Project structure

```
Corrix/
├── backend/
│   ├── app/
│   │   ├── api/           FastAPI routes and the scenario WebSocket
│   │   ├── council/       The Safety Council (LangGraph, agents, Chair, LLM client)
│   │   ├── cv/            Computer-vision inference (YOLO)
│   │   ├── detection/     Anomaly scoring, novelty, forecasting, evacuation routing
│   │   ├── emergency/     Emergency Response Orchestrator
│   │   ├── evaluation/    Evaluation harness, calibration, SWaT validation
│   │   ├── mcp_servers/   The five inward + one outward MCP servers
│   │   ├── memory/        Self-improving memory exemplar store
│   │   ├── regulatory/    Neo4j GraphRAG ingestion and retrieval
│   │   ├── reporting/     PDF Incident Report generator
│   │   ├── schemas/       Pydantic models (single source of truth for data shapes)
│   │   ├── simulation/    Physics-informed data generators and scenario engine
│   │   └── state/         Live risk state and incident alert state
│   ├── scripts/           Setup, evaluation, training, and diagnostic scripts
│   └── tests/             382 tests
├── frontend/
│   └── src/
│       ├── components/    Heatmap, 3D plant scene, Council, modals, chat, boot sequence
│       ├── store/         Zustand state
│       ├── lib/           WebSocket hook and helpers
│       └── data/          Mock data and the plant layout
├── data/                  Scenarios, plant layout, regulatory sources, evaluation results
├── docs/                  Design docs, implementation doc, demo script, pitch deck
├── Dockerfile             Single-service production image
└── render.yaml            Render deployment blueprint
```

## Troubleshooting

- **Frontend shows "mock data" instead of "backend live"**: the backend is not reachable. Confirm it is running on port 8000 and that the frontend is on port 5173.
- **`ImportError: libGL.so.1` (Linux/Docker)**: the OpenCV headless step was skipped; re-run the `--force-reinstall --no-deps opencv-python-headless` line.
- **Regulatory chat or pattern lookup returns nothing on the live backend**: Neo4j was not populated; run `python scripts/setup_neo4j.py`.
- **A Council convening returns a low-confidence "fallback" verdict**: both LLM providers were rate-limited or unreachable; this is the intended graceful degradation, not a crash. Check your Groq/Gemini quota.
