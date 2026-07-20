"""The Virtual Sensor Simulator's backend half, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 19: the thing that replaces
hardware in the pitch. A user's slider/toggle/button touch
(app/api/virtual_sensor.py) calls set_gas_target/publish_badge_event/
publish_permit; each active gas channel then ticks itself
independently, moving toward its target with the same Ornstein-
Uhlenbeck jitter app/simulation/gas_process.step already uses for the
synthetic scenarios, and publishes the result over the real MQTT
broker (Step 17) on corrix/{factory_id}/{zone_id}/{gas|badge|permit},
for app/ingestion/mqtt_ingest.py (Step 18) to consume downstream,
indistinguishable from any other MQTT publisher.

`step()` is imported and called unmodified, per the build plan's own
instruction not to reimplement the OU math. Here `dt` represents one
publish tick (TICK_SECONDS), not literal minutes as the scripted
scenario engine uses it, and CHANNEL_K/CHANNEL_SIGMA are tuned for
that tick cadence rather than copied from any GasSignalConfig: a live
interactive control needs visible movement within a couple of seconds,
not the minutes a scripted scenario ramps over. This is a difference in
tuning parameters for a different caller, not a change to the process
itself.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import numpy as np
import paho.mqtt.client as mqtt

from app.config import get_settings
from app.schemas import BadgeEventType, PermitStatus
from app.simulation.gas_process import step

logger = logging.getLogger(__name__)

TICK_SECONDS = 1.5
TICK_DT = 1.0  # one tick, not one minute; see module docstring
CHANNEL_K = 0.3
CHANNEL_SIGMA = 0.15

# Realistic ambient starting points per gas type, so a newly-touched
# channel visibly climbs toward the user's target instead of starting
# there, per CORRIX_REAL_DATA.md section 3.2.
AMBIENT_BASELINE = {"O2": 20.9, "CO": 0.5, "H2S": 0.0, "LEL": 0.0}


@lru_cache
def _get_publisher_client() -> mqtt.Client:
    settings = get_settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    client.loop_start()
    return client


def _publish(topic: str, payload: dict) -> None:
    _get_publisher_client().publish(topic, json.dumps(payload))


@dataclass
class VirtualGasChannel:
    factory_id: str
    zone_id: str
    gas_type: str
    target_value: float
    current_value: float
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng())
    task: "asyncio.Task | None" = None


_channels: dict[tuple[str, str, str], VirtualGasChannel] = {}


async def _run_channel_loop(channel: VirtualGasChannel) -> None:
    topic = f"corrix/{channel.factory_id}/{channel.zone_id}/gas"
    try:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            channel.current_value = step(
                channel.current_value,
                CHANNEL_K,
                channel.target_value,
                0.0,
                CHANNEL_SIGMA,
                TICK_DT,
                channel.rng,
            )
            _publish(
                topic,
                {
                    "gas_type": channel.gas_type,
                    "concentration": round(channel.current_value, 4),
                    "unit": "ppm",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(
            "virtual_sensor_publisher: channel loop for %s/%s/%s failed: %s",
            channel.factory_id,
            channel.zone_id,
            channel.gas_type,
            exc,
        )


async def set_gas_target(
    factory_id: str, zone_id: str, gas_type: str, target_concentration: float
) -> None:
    """Called when a user moves a gas slider. Creates the channel (and
    starts its own independent background publishing task) on first
    touch; a later call just retargets the same channel, letting its
    already-running task carry the value there with jitter instead of
    jumping straight to it."""
    key = (factory_id, zone_id, gas_type)
    channel = _channels.get(key)
    if channel is None:
        channel = VirtualGasChannel(
            factory_id=factory_id,
            zone_id=zone_id,
            gas_type=gas_type,
            target_value=target_concentration,
            current_value=AMBIENT_BASELINE.get(gas_type, 0.0),
        )
        channel.task = asyncio.create_task(_run_channel_loop(channel))
        _channels[key] = channel
    else:
        channel.target_value = target_concentration


def stop_gas_channel(factory_id: str, zone_id: str, gas_type: str) -> None:
    """Cancels and forgets a channel's background task. Not on any
    application code path yet; exists so tests (and, later, a factory
    disconnect handler) can stop a channel from publishing forever."""
    channel = _channels.pop((factory_id, zone_id, gas_type), None)
    if channel is not None and channel.task is not None:
        channel.task.cancel()


async def publish_badge_event(factory_id: str, zone_id: str, badge_id: str, entering: bool) -> None:
    """A badge toggle publishes a single BadgePingEvent immediately, no
    background channel: a badge crossing a zone boundary is a discrete
    event, not a continuous process."""
    _publish(
        f"corrix/{factory_id}/{zone_id}/badge",
        {
            "badge_id": badge_id,
            "event_type": (
                BadgeEventType.ZONE_ENTRY.value if entering else BadgeEventType.ZONE_EXIT.value
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def publish_permit(factory_id: str, zone_id: str, permit_type: str) -> None:
    """A permit button publishes a single PermitRecord immediately, no
    background channel: a permit being issued is a discrete event."""
    now = datetime.now(timezone.utc)
    _publish(
        f"corrix/{factory_id}/{zone_id}/permit",
        {
            "permit_id": f"P-{now.strftime('%Y%m%d%H%M%S')}-{zone_id}",
            "type": permit_type,
            "issued_by": "virtual-sensor-panel",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=4)).isoformat(),
            "status": PermitStatus.ACTIVE.value,
        },
    )
