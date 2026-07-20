# Ingestion adapters

Adapters that feed real data into the live-factory pipeline
(`app/api/live_factory_websocket.py`), one per data source declared on
a `FactoryProfile.data_source`.

## CSV (`csv_ingest.py`, `csv_upload_store.py`)

Replays an uploaded historian CSV in chronological order. No external
service required.

## MQTT (`mqtt_ingest.py`, coming in Step 18)

**Broker:** defaults to the public Eclipse test broker,
`test.mosquitto.org:1883` (`app.config.Settings.mqtt_broker_host`/
`mqtt_broker_port`), for early development. This is a real broker,
just not one we operate: fine for building and testing the client
code, not something to depend on for the final demo, since it is a
shared, third-party service with no uptime guarantee to us.

**Before the final demo:** point `MQTT_BROKER_HOST`/`MQTT_BROKER_PORT`
(in `.env`) at a broker we control instead, either:

- A local Mosquitto via Docker: `docker run -p 1883:1883 eclipse-mosquitto`, then
  `MQTT_BROKER_HOST=localhost`.
- A small hosted broker (e.g. a free-tier CloudAMQP/HiveMQ Cloud instance),
  if the demo needs to run somewhere other than one machine with Docker.

Verify connectivity with `python scripts/verify_mqtt_broker.py` after
changing brokers, before wiring any adapter code against it.

## OPC-UA (coming in Phase 5, optional)

Not yet built. See `CORRIX_REAL_DATA_BUILD_PLAN.md` Phase 5.
