"""One-off verification for Step 17 of the Bring Your Own Factory build
plan: confirms the configured MQTT broker (app.config.Settings.
mqtt_broker_host/port) is reachable before any adapter code is written
against it. Publishes a uniquely-tagged test message and confirms a
subscriber on the same topic receives that exact payload.

Run from backend/: python scripts/verify_mqtt_broker.py
"""

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paho.mqtt.client as mqtt

from app.config import get_settings

TOPIC = "corrix/verify-mqtt-broker/test"
TIMEOUT_SECONDS = 10.0


def main() -> None:
    settings = get_settings()
    expected_payload = f"corrix-broker-check-{uuid.uuid4()}"
    received: list[str] = []

    def on_message(_client, _userdata, message) -> None:
        received.append(message.payload.decode("utf-8"))

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = on_message
    subscriber.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    subscriber.subscribe(TOPIC)
    subscriber.loop_start()

    time.sleep(1.0)  # let the subscription actually register before publishing

    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    publisher.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    publisher.loop_start()
    publisher.publish(TOPIC, expected_payload)

    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline and not received:
        time.sleep(0.2)

    publisher.loop_stop()
    publisher.disconnect()
    subscriber.loop_stop()
    subscriber.disconnect()

    if not received:
        print(
            f"FAILED: no message received on {settings.mqtt_broker_host}:"
            f"{settings.mqtt_broker_port} within {TIMEOUT_SECONDS}s"
        )
        sys.exit(1)

    if received[0] != expected_payload:
        print(f"FAILED: payload mismatch. Expected {expected_payload!r}, got {received[0]!r}")
        sys.exit(1)

    print(
        f"OK: published and received a matching message via "
        f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port} on topic {TOPIC!r}."
    )


if __name__ == "__main__":
    main()
