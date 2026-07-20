import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.evaluation import router as evaluation_router
from app.api.incident_report import router as incident_report_router
from app.api.assistant import router as assistant_router
from app.api.regulatory_chat import router as regulatory_chat_router
from app.api.replay import router as replay_router
from app.api.what_if import router as what_if_router
from app.api.websocket import scenario_websocket

app = FastAPI(title="Corrix Backend")

# The dev frontend (Vite on 5173) and the deployed frontend (built and
# served by this same process, see the static mount below) are the only
# two origins this backend ever needs to answer; CORS only matters for
# the former; same-origin requests, including the deployed instance,
# never go through it at all.
dev_origins = ["http://localhost:5173"]
extra_origin = os.environ.get("CORRIX_EXTRA_CORS_ORIGIN")
if extra_origin:
    dev_origins.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=dev_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(evaluation_router)
app.include_router(replay_router)
app.include_router(incident_report_router)
app.include_router(regulatory_chat_router)
app.include_router(what_if_router)
app.include_router(assistant_router)


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
