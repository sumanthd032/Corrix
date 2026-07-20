import logging
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.evaluation import router as evaluation_router
from app.api.factory import router as factory_router
from app.api.incident_report import router as incident_report_router
from app.api.assistant import router as assistant_router
from app.api.regulatory_chat import router as regulatory_chat_router
from app.api.replay import router as replay_router
from app.api.send_alert import router as send_alert_router
from app.api.what_if import router as what_if_router
from app.api.websocket import scenario_websocket
from app.api.live_factory_websocket import live_factory_websocket

app = FastAPI(title="Corrix Backend")

# Allowed browser origins for the REST API.
#  - Local dev is always allowed (Vite on 5173).
#  - When the frontend is hosted separately (e.g. on Vercel) and the backend
#    elsewhere (e.g. an AWS/Cloudflare-Tunnel host), set CORRIX_EXTRA_CORS_ORIGIN
#    to the frontend origin(s), comma-separated for more than one, e.g.
#    "https://corrix.vercel.app,https://corrix-staging.vercel.app".
#  - CORRIX_CORS_ORIGIN_REGEX optionally matches dynamic origins such as
#    Vercel preview deployments, e.g. "https://.*\\.vercel\\.app".
# (The single-service deployment serves the frontend same-origin and needs
# none of this; CORS only applies to cross-origin browser requests.)
allowed_origins = ["http://localhost:5173"]
extra_origins = os.environ.get("CORRIX_EXTRA_CORS_ORIGIN", "")
allowed_origins += [o.strip() for o in extra_origins.split(",") if o.strip()]
origin_regex = os.environ.get("CORRIX_CORS_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(evaluation_router)
app.include_router(factory_router)
app.include_router(replay_router)
app.include_router(incident_report_router)
app.include_router(regulatory_chat_router)
app.include_router(what_if_router)
app.include_router(assistant_router)
app.include_router(send_alert_router)


@app.on_event("startup")
def _warm_models() -> None:
    """Preload the local sentence-transformers embedding model in a background
    thread a moment after startup, so the first regulatory query does not pay
    the one-time model-load cost live in front of a user. Best-effort: any
    failure is logged and ignored, and it never blocks startup or the request
    path.

    The novelty detector is deliberately not warmed here. It is fit lazily on
    first use and cached for the process; warming it in the background races
    the request-path build of the same model (they do not share the in-flight
    computation, so both rebuild and contend for CPU), which made the first
    scenario slower, not faster, especially on a reloading dev server."""
    import threading

    def _load() -> None:
        try:
            from app.regulatory.embeddings import get_embedding_model

            get_embedding_model()
        except Exception:
            logging.getLogger(__name__).warning("Embedding-model warmup skipped.")

    threading.Thread(target=_load, daemon=True).start()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "corrix-backend"}


@app.websocket("/ws")
async def websocket_echo(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"echo: {message}")
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/scenario")
async def scenario_ws(websocket: WebSocket) -> None:
    await scenario_websocket(websocket)


@app.websocket("/ws/live-factory")
async def live_factory_ws(websocket: WebSocket) -> None:
    await live_factory_websocket(websocket)


# The built frontend (`npm run build` in frontend/, producing
# frontend/dist/) is served by this same process in production, so the
# public Render instance is one service, not two, and the frontend talks
# to its own backend same-origin with no CORS involved. Mounted last and
# guarded on the directory actually existing, so local backend-only
# development (no frontend build present) is unaffected: the Vite dev
# server on 5173 keeps serving the frontend as it always has.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
