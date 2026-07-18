# Corrix

An AI-powered industrial safety intelligence platform. Full product design, architecture, and reasoning live in `docs/CORRIX_PROJECT.md`; the exact data/simulation methodology is in `docs/CORRIX_DATA_METHODOLOGY.md`; the build sequence is in `docs/CORRIX_BUILD_PLAN.md`. This file covers running the project locally and deploying it, nothing else.

## Prerequisites

- Python 3.13
- Node.js 22 and npm
- A Groq API key (free tier)
- A Gemini API key (free tier)
- A Neo4j AuraDB Free instance (URI, username, password)
- Optionally, SMTP credentials, a Slack webhook, or a Discord webhook for the Emergency Response Orchestrator

## Local development

### Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
pip install --force-reinstall --no-deps opencv-python-headless==5.0.0.93
python -m playwright install chromium   # needed for the Incident Report PDF generator
```

The second `pip install` line is not optional: `ultralytics` hard-depends on plain `opencv-python` regardless of what else is installed, which silently overwrites `opencv-python-headless`'s files with the GUI build's. That's fine on Windows/macOS dev machines (nothing actually breaks), but the GUI build needs `libGL.so.1`, which a minimal Linux container doesn't have, and it will not import at all there without this step re-asserting the headless build last.

Copy `.env.example` to `.env` at the repo root and fill in real values (Groq, Gemini, Neo4j at minimum; the app runs without ERO credentials configured, it just won't send alerts). Never commit `.env`.

```
cd backend
uvicorn app.main:app --reload --port 8000
```

Confirm it's up: `curl http://localhost:8000/health` should return `{"status":"ok","service":"corrix-backend"}`.

### Frontend

```
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173` (the only origin the backend's CORS policy allows in development; if Vite picks a different port because 5173 is taken, either free up 5173 or set `CORRIX_EXTRA_CORS_ORIGIN` in `.env` to whatever origin it actually used).

### Tests

```
cd backend
pytest
```

Several tests make real Groq/Gemini calls and real Neo4j reads; they skip cleanly on a genuine rate limit rather than failing (see `backend/tests/conftest.py`).

## Production build and deployment

The deployed instance is a single service: the backend serves both the API/WebSocket and the built frontend from one FastAPI process (`backend/app/main.py` mounts `frontend/dist` as static files once it exists), so there is no CORS to configure and no second service to run. This exact shape is what `Dockerfile` builds and what has been verified locally (a real browser session against the backend's own port alone, with the frontend served from it, live data flowing end to end).

### Deploying to Render

1. Push this repository to GitHub (or GitLab/Bitbucket).
2. In Render, choose **New > Blueprint** and point it at the repository. Render reads `render.yaml` and creates one Docker-runtime web service on the free plan.
3. Render will prompt for the environment variables marked `sync: false` in `render.yaml`: `GROQ_API_KEY`, `GEMINI_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and the ERO variables if the Emergency Response Orchestrator should fire on the public instance. Fill in the real values there, not in any committed file.
4. Deploy. Render builds the image from `Dockerfile` (which builds the frontend, then the backend, then bakes both into one image) and runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`. `healthCheckPath: /health` in `render.yaml` is what Render polls to confirm the service is actually up.
5. Once live, open the assigned `onrender.com` URL. The free plan spins the instance down after inactivity; visit it once yourself a few minutes before a demo or judging session so the cold start (roughly 30-60 seconds) happens before anyone else is watching.

### Building and running the image locally, without Render

```
docker build -t corrix .
docker run -p 8000:8000 --env-file .env corrix
```

Then open `http://localhost:8000`. This is the same image Render builds; testing it locally first is the fastest way to catch a deployment problem before it happens on Render's infrastructure.

### Why `data/evaluation/*.json` is committed

Those files are real, precomputed Evaluation Harness and memory-loop results (see `memory.md`'s Step 8-10 entries for exactly how each was generated and verified), not build output. The live `/api/evaluation/report` endpoint reads them directly at request time and has no fallback if they're missing, so they're tracked in git deliberately rather than gitignored as regenerable artifacts: the deployed instance needs them to answer that endpoint at all, and they're exactly the numbers already shown in `docs/pitch_deck.html` and `docs/demo_script.md`. `data/swat/` (the real, access-restricted SWaT dataset used to generate `swat_validation.json` once, offline) stays gitignored; nothing at runtime reads it directly.
