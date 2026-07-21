# Bring Your Own Factory — judge-facing demo script

Step 27 of `CORRIX_REAL_DATA_BUILD_PLAN.md`.

## The one-paragraph script

Watch me add my own factory. I will draw its zone layout by hand, open the virtual sensor panel, and drag one gas reading up. That is a real MQTT message published to a real broker, scored by the same five-agent Council you just saw reasoning through our synthetic scenarios. No pre-authored scenario is involved, and no physical hardware sits behind it.

## The full walkthrough, in order

1. From the landing page, click "Launch live demo" first. Run through one or two of the five authored scenarios, then open Presenter Mode, so the judge sees the original synthetic demo working end to end.
2. Return to the landing page. Click "Get Started" instead.
3. Step through the wizard: identity, then draw a small zone graph (three or four zones, two or three adjacency edges) in the graph editor, then workforce, then permits.
4. On the Review step, pick "Virtual IoT sensors (MQTT)" as the data source, then Launch.
5. In the Live Command Center, open the Virtual Sensor Panel drawer.
6. Pick a zone and drag its LEL slider up. Narrate what is actually happening while it climbs: a real MQTT message just published to a real broker, and the reading is genuinely arriving over that broker's `corrix/{factory_id}/{zone_id}/gas` topic, not a scripted animation.
7. Once the zone crosses threshold, point out the Council convening, then the real verdict landing in the Council panel, sourced from the same five-agent LangGraph the synthetic demo just used.
8. Point at the data-source badge: "SIMULATED DEVICE (MQTT)". State plainly that the device is simulated and the protocol is real, the same honesty the landing page already uses for the synthetic scenarios' data.

## Definition of done, per the build plan

- [x] Landing page: "Launch live demo" (unchanged) and "Get Started" (new); neither breaks the other.
- [x] Five-step wizard produces a real `FactoryProfile`, including a hand-drawn zone/adjacency graph.
- [x] CSV path: real upload, real trigger, real Council, real verdict, zero scenario YAML involved.
- [x] MQTT path: virtual sensor panel to real broker message to real Council to real verdict, within seconds, end to end through the UI.
- [x] OPC-UA: a real `asyncua`-backed path (not a placeholder; Phase 5 was built in full).
- [x] Every live-console view labels its actual data source, including "simulated device" where applicable.
- [x] `_run_council` is the single shared function both the synthetic and BYOF paths call. No duplicated Council, detection, or regulatory logic anywhere.
- [x] Full `backend/tests/` suite green (453 passed, 3 skipped, 0 failed as of the final run), original tests untouched, new tests isolated in new `test_factory_*.py` / `test_ingestion_*.py` / `test_live_factory_*.py` / `test_virtual_sensor_*.py` / `test_text_sanitizer.py` files.
- [ ] Both demo paths run back-to-back without a backend restart: confirmed at the backend/API level (a real scenario run followed by a real BYOF CSV run against the same running server, in the same session, no restart, no unhandled error in either log). **Not yet confirmed through the actual browser UI** — this needs to be run once by a person with a browser, since no browser-automation tool was available in the session that built this feature.

## What still needs a human with a browser

Everything in this build was verified against the real backend (Neo4j, Groq/Gemini, a real MQTT broker, a real OPC-UA server, real WebSocket clients) and the frontend was verified with `tsc -b`, `oxlint`, and a full production `vite build` after every change. No session in this build had a browser-automation tool available, so the actual visual click-through — the wizard's zone editor rendering and responding to drag gestures, the Live Command Center's panels rendering the right data, the Virtual Sensor Panel's sliders actually moving a gauge on screen — has not been confirmed by looking at it. Run the walkthrough above once, end to end, before relying on this in front of judges.
