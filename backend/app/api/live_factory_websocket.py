"""Bring Your Own Factory: the live-factory WebSocket, per
CORRIX_REAL_DATA_BUILD_PLAN.md Steps 8, 18, and 25. A sibling to
app/api/websocket.py, not a rewrite: streams real ingested readings
(CSV replay, the live MQTT virtual-sensor path, or the OPC-UA virtual
SCADA path) instead of a precomputed scenario playback, scores gas
readings with the same z-score classifier the synthetic path uses
(app.detection.anomaly_scorer), and calls the exact same _run_council
(Step 7) when a zone crosses threshold. No Council, detection, or
regulatory logic is duplicated here.

The reading queue carries a mix of GasSensorReading, BadgePingEvent,
and PermitRecord for the MQTT path (CSV only ever produces
GasSensorReading): badge/permit readings update tracked worker
positions and active permits rather than triggering a convening
themselves, so a convening triggered by a gas anomaly can still cite
real permit/worker evidence gathered from the same live stream, not an
empty placeholder.

Baseline calibration deliberately does not reuse `score_series` as-is:
that function computes mean/std once from the *whole* series passed to
it, which is correct for a precomputed scenario run but wrong for a
live stream, where the series keeps growing. Recomputing it fresh on
every new reading would let the newest (possibly anomalous) reading
keep diluting its own baseline, and a real uploaded CSV is typically
far shorter than a scripted scenario's ~2000 ticks, so the naive
approach would often never trigger at all. Instead, each zone's
baseline is calibrated exactly once, from its first LIVE_BASELINE_TICKS
readings, then every later reading for that zone is scored against
that fixed reference (calibrate_baseline, classify_z_score), the same
calibrate-once-score-forever discipline anomaly_scorer.py's own
docstring documents and the synthetic path already relies on.

Protocol (JSON messages over one WebSocket connection):

Client -> server:
  {"type": "connect", "factory_id": "..."}
  {"type": "override", "note": "..."}      submit an override note
                                            while a convening is paused

Server -> client:
  {"type": "tick", "zoneRisk": {...}, "workers": {...}}
  {"type": "council_convening"} / "deliberating" / "verdict" / "ero_fired"
  {"type": "council_error", "message": "..."}
  {"type": "replay_complete"}
  {"type": "error", "message": "..."}      connection cannot proceed;
                                            the socket is then closed
"""

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.api.live_evidence import (
    format_permit_text,
    format_process_safety_text,
    format_shift_text,
    format_site_safety_text,
)
from app.api.websocket import _run_council
from app.config import get_settings
from app.detection.anomaly_scorer import AnomalyPoint, calibrate_baseline, classify_z_score
from app.ingestion.csv_ingest import replay_csv
from app.ingestion.csv_upload_store import load_uploaded_csv
from app.ingestion.mqtt_ingest import MqttReading, stream_mqtt
from app.ingestion.opcua_ingest import stream_opcua
from app.schemas import (
    BadgeEventType,
    BadgePingEvent,
    GasSignalConfig,
    PermitRecord,
    RiskLevel,
    ScenarioConfig,
    ScenarioGroundTruth,
    ScenarioSignals,
)
from app.simulation.plant_layout import load_plant_layout
from app.storage.factory_store import load_factory

logger = logging.getLogger(__name__)

LIVE_BASELINE_TICKS = 10
_INGEST_DONE = object()


def _minimal_scenario_config(zone_id: str, gas_type: str) -> ScenarioConfig:
    """A ScenarioConfig-shaped wrapper carrying only what
    app.api.live_evidence's formatters actually read
    (config.zone, config.signals.gas.gas_type) for a live factory's real
    reading, not a scripted scenario. Every other field is a
    structurally required but semantically unused placeholder."""
    return ScenarioConfig(
        scenario_id="live-factory",
        name="Live Factory Feed",
        seed=0,
        memory_split="population",
        duration_minutes=0,
        zone=zone_id,
        signals=ScenarioSignals(
            gas=GasSignalConfig(
                gas_type=gas_type,
                C_baseline=0.0,
                k=0.0,
                sigma=0.0,
                source_shape="ramp",
                a=0.0,
                t0_minute=0.0,
            )
        ),
        ground_truth=ScenarioGroundTruth(
            compound_risk_window_start_minute=0.0, incident_threshold_minute=0.0
        ),
    )


async def _run_ingestion_to_completion(
    file_bytes: bytes, column_map: dict, speed_multiplier: float, queue: asyncio.Queue
) -> None:
    try:
        await replay_csv(file_bytes, column_map, speed_multiplier, queue)
    finally:
        await queue.put(_INGEST_DONE)


async def live_factory_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        connect_msg = await websocket.receive_json()
    except WebSocketDisconnect:
        return

    factory_id = connect_msg.get("factory_id") if connect_msg.get("type") == "connect" else None
    if not factory_id:
        await websocket.send_json(
            {"type": "error", "message": "Expected a connect message with a factory_id."}
        )
        await websocket.close()
        return

    profile = load_factory(factory_id)
    if profile is None:
        await websocket.send_json(
            {"type": "error", "message": f"No factory found for id {factory_id}"}
        )
        await websocket.close()
        return

    reading_queue: "asyncio.Queue[MqttReading]" = asyncio.Queue()

    if profile.data_source == "csv":
        uploaded = load_uploaded_csv(factory_id)
        if uploaded is None:
            await websocket.send_json(
                {"type": "error", "message": "No CSV has been uploaded for this factory yet."}
            )
            await websocket.close()
            return
        file_bytes, column_map, speed_multiplier = uploaded
        ingest_task = asyncio.create_task(
            _run_ingestion_to_completion(file_bytes, column_map, speed_multiplier, reading_queue)
        )
    elif profile.data_source == "mqtt":
        settings = get_settings()
        ingest_task = asyncio.create_task(
            stream_mqtt(factory_id, settings.mqtt_broker_host, settings.mqtt_broker_port, reading_queue)
        )
    elif profile.data_source == "opcua":
        settings = get_settings()
        ingest_task = asyncio.create_task(stream_opcua(settings.opcua_endpoint_url, reading_queue))
    else:
        await websocket.send_json(
            {
                "type": "error",
                "message": (
                    f"Data source {profile.data_source!r} is not yet supported over "
                    "this connection; only csv, mqtt, and opcua are implemented."
                ),
            }
        )
        await websocket.close()
        return

    layout = load_plant_layout(factory_id)
    all_zone_ids = [z.zone_id for z in layout.zones]

    incoming: "asyncio.Queue[dict]" = asyncio.Queue()

    async def receiver() -> None:
        try:
            while True:
                msg = await websocket.receive_json()
                await incoming.put(msg)
        except WebSocketDisconnect:
            await incoming.put({"type": "__disconnect__"})

    receiver_task = asyncio.create_task(receiver())

    zone_risk_state: dict[str, RiskLevel] = {zid: "SAFE" for zid in all_zone_ids}
    readings_by_zone: dict[str, list[float]] = {}
    zone_baselines: dict[str, tuple[float, float]] = {}
    triggered_zones: set[str] = set()
    worker_positions: dict[str, str] = {}
    permits_by_id: dict[str, PermitRecord] = {}

    try:
        while True:
            reading = await reading_queue.get()
            if reading is _INGEST_DONE:
                await websocket.send_json({"type": "replay_complete"})
                break

            try:
                msg = incoming.get_nowait()
                if msg.get("type") == "__disconnect__":
                    break
                await incoming.put(msg)  # not for us here; _run_council's override wait sees it
            except asyncio.QueueEmpty:
                pass

            if isinstance(reading, BadgePingEvent):
                if reading.event_type == BadgeEventType.ZONE_EXIT:
                    worker_positions.pop(reading.badge_id, None)
                else:
                    worker_positions[reading.badge_id] = reading.zone_id
                await websocket.send_json(
                    {"type": "tick", "zoneRisk": zone_risk_state, "workers": dict(worker_positions)}
                )
                continue

            if isinstance(reading, PermitRecord):
                permits_by_id[reading.permit_id] = reading
                await websocket.send_json(
                    {"type": "tick", "zoneRisk": zone_risk_state, "workers": dict(worker_positions)}
                )
                continue

            zone_id = reading.zone_id
            values = readings_by_zone.setdefault(zone_id, [])
            values.append(reading.concentration)

            if zone_id not in zone_baselines:
                if len(values) < LIVE_BASELINE_TICKS:
                    await websocket.send_json(
                        {"type": "tick", "zoneRisk": zone_risk_state, "workers": dict(worker_positions)}
                    )
                    continue
                zone_baselines[zone_id] = calibrate_baseline(
                    values, baseline_ticks=LIVE_BASELINE_TICKS
                )

            mean, std = zone_baselines[zone_id]
            z_score = max(-1000.0, min(1000.0, (reading.concentration - mean) / std))
            risk_level = classify_z_score(z_score)
            point = AnomalyPoint(
                index=len(values) - 1,
                value=reading.concentration,
                z_score=z_score,
                risk_level=risk_level,
            )

            zone_risk_state[zone_id] = risk_level
            await websocket.send_json(
                {"type": "tick", "zoneRisk": zone_risk_state, "workers": dict(worker_positions)}
            )

            if zone_id in triggered_zones or risk_level not in ("HIGH", "CRITICAL"):
                continue
            triggered_zones.add(zone_id)

            config = _minimal_scenario_config(zone_id, reading.gas_type.value)
            raw_evidence = {
                "process_safety_engineer": format_process_safety_text(config, point),
                "permit_control_officer": format_permit_text(
                    config, list(permits_by_id.values()), reading.timestamp
                ),
                "shift_operations": format_shift_text(
                    profile.shift_pattern, zone_id, reading.timestamp
                ),
                "site_safety_observer": format_site_safety_text(worker_positions, zone_id),
            }

            try:
                await _run_council(
                    websocket,
                    incoming,
                    zone_id=zone_id,
                    trigger_reason="rule_threshold",
                    raw_evidence=raw_evidence,
                    scenario_id=None,
                    memory_context=None,
                    layout=layout,
                    zone_risk=dict(zone_risk_state),
                    worker_positions=dict(worker_positions),
                )
            except Exception as exc:
                logger.error("Live factory Council convening failed unexpectedly: %s", exc)
                await websocket.send_json(
                    {
                        "type": "council_error",
                        "message": "The Safety Council could not complete its deliberation.",
                    }
                )
    finally:
        receiver_task.cancel()
        ingest_task.cancel()
