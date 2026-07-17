from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.evaluation import router as evaluation_router
from app.api.incident_report import router as incident_report_router
from app.api.replay import router as replay_router
from app.api.websocket import scenario_websocket

app = FastAPI(title="Corrix Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(evaluation_router)
app.include_router(replay_router)
app.include_router(incident_report_router)


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
