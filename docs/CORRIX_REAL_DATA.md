# Corrix — "Bring Your Own Factory" (BYOF)
### Hardware-free build plan — real protocols, real reasoning engine, zero physical sensors

---

## 0. What changed from the first draft, and why

I re-read the repo (`Root.tsx`, `App.tsx`, `LandingPage.tsx`, `useCorrixStore.ts`, `useScenarioSocket.ts`,
`data/plantLayout.ts`, `app/main.py`, `app/api/websocket.py`, `app/api/live_scenario.py`,
`app/api/live_evidence.py`, `app/simulation/scenario_engine.py`, `app/simulation/gas_process.py`,
`app/simulation/plant_layout.py`, `app/schemas/*.py`, `app/council/graph.py`, `app/detection/*.py`,
`app/mcp_servers/sensor_stream.py`) against your uploaded `CORRIX_LIVE_FACTORY_BUILD_PLAN.md`, and everything
in it is accurate — the schemas, the file paths, the reuse points all check out against the real code. The
only thing that needs to change is **how "Connect live IoT" and "Connect SCADA" actually get built**, since
you've confirmed: no physical hardware, ESP32s, or gas sensors — this stays 100% software.

That doesn't shrink the feature. It changes *what plays the role of the device*, not what the pipeline does
once data arrives. The distinction that matters for judges:

> **MQTT and OPC-UA are protocols, not hardware.** A real Mosquitto broker doesn't know or care whether the
> bytes on a topic came from a $5 microcontroller or from a Python coroutine you wrote. The broker, the topic
> hierarchy, the message parsing, the Council convening on the other end — all real. The only thing you're
> supplying instead of a physical sensor is the *publisher*, and you're allowed to write that publisher
> yourself because you don't have a rig. This is exactly what SCADA vendors' own test/demo tooling does
> (Siemens, Rockwell demo servers; `asyncua`'s bundled OPC-UA demo server) to prove an integration without
> wiring up a real plant floor.

So the plan below keeps every architectural claim from your original doc (§0's framing — *"same reasoning
engine, second front door"* — is still your strongest pitch line) and replaces only Phase B's MQTT/OPC-UA
adapters with a **Virtual Factory Simulator** that judges can see and touch, instead of a bare publisher
script. Everything else — schemas, endpoints, wizard, dashboard reuse, safety rails, build order — carries
over unchanged.

---

## 1. Non-negotiables (unchanged from your original plan)

- **Nothing about the existing synthetic flow changes.** `Root.tsx → LandingPage → onLaunch → App.tsx →
  /ws/scenario` stays byte-for-byte as-is. "Launch live demo," `BootSequence`, `DemoIntro`, `PresenterMode`,
  the five scenarios, the Open Challenge — untouched.
- **The new flow is a fully separate branch off `Root.tsx`**, triggered by a new "Get Started" button on the
  landing page, so nothing here can regress the demo you already have passing 400+ backend tests.
- **Reuse, don't fork, the reasoning stack.** The Council (`app/council/`), the detection engine
  (`app/detection/`), the regulatory GraphRAG, the evacuation router, the ERO must be the *same* Python
  objects the synthetic path calls. If you catch yourself copy-pasting `app/council/graph.py` or
  `app/detection/trigger.py`, stop — the interface boundary is in the wrong place.
- **NEW: every simulated device is labeled as simulated, everywhere.** No screen, log line, or demo script
  claims real hardware exists. This is a design decision, not a limitation — say so out loud to judges the
  same way the landing page is already upfront about synthetic vs. real data.

---

## 2. Product shape: what "Get Started" walks the user through

```
Landing Page
 ├─ "Launch live demo"   → existing synthetic flow (untouched)
 └─ "Get Started"        → NEW: Factory Onboarding Wizard (5 steps) → NEW: Live Command Center
```

**Step 1 — Factory identity.** Name, industry vertical (steel / chemical / refinery / mining / cement /
other — reuses the existing regulatory-framework selection), location (drives DGMS vs. OISD vs. Factories
Act relevance downstream).

**Step 2 — Zones & layout (build this well — it's the wizard's best "wow" moment).** User adds zones one at
a time: name, hazard class (`low`/`medium`/`high`, same enum as `app/schemas/zone.py`), confined-space flag,
assembly-point flag. Then connects zones with an adjacency graph — the same `ZoneAdjacencyEdge` structure
your evacuation router already consumes. Render as a small SVG node-graph editor: drag zone nodes, click-drag
to draw an edge. Not cosmetic — this *is* the exact input `find_evacuation_route` and
`predict_risk_propagation` need, so the user is directly authoring the graph your algorithms run on.

**Step 3 — Workforce & shifts.** Worker count, badge/ID prefix (or CSV roster upload: name, badge ID,
default zone), shifts per day and changeover times — maps onto `ShiftRecord` and `BadgePingEvent`.

**Step 4 — Processes & permits in use.** Multi-select from the existing `PermitType` enum (`hot_work`,
`cold_work`, `confined_space_entry`, `lifting_operation`, `electrical_isolation`) plus free-text "other,"
stored but flagged `unmapped_permit_type` so the Council always receives a value it recognizes.

**Step 5 — Connect data.** Three cards: **Upload historian CSV**, **Connect Virtual IoT (MQTT)**, **Connect
Virtual SCADA (OPC-UA)**. All three are clearly labeled — see §3.

**Review & Launch** → creates a `FactoryProfile`, routes into a Live Command Center that reuses the existing
dashboard shell (`PlantHeatmap`, `CouncilPanel`, `AlertFeed`, `TelemetryStrip`) now rendering this factory's
real zones and real streamed evidence instead of a scenario.

---

## 3. The hardware-free data-source strategy (this replaces §3 of your original doc)

| Path | What plays "the device" | Build cost | Live-demo value | Verdict |
|---|---|---|---|---|
| **CSV / historian upload** | A file the user brings | Low | Low — judges can't watch it happen live | **Build first.** Safety net: proves the pipeline accepts arbitrary real data, works for every judge regardless of what's in the room. |
| **Virtual IoT via MQTT** | Your own **Virtual Sensor Simulator panel** publishing over a real MQTT broker | Medium | **Very high** — a judge drags a slider, watches a value climb, and sees your dashboard react and the real Council convene, within seconds | **Build second — flagship.** The broker, protocol, topic hierarchy, and downstream reasoning are all genuinely real; only the "device" is a UI panel instead of silicon. |
| **Virtual SCADA / OPC-UA** | `asyncua`'s free, open-source demo server, running locally with simulated nodes | Medium-high | Lower live-demo value, high credibility on paper — OPC-UA is what real plants (Siemens, Rockwell, Honeywell, ABB) actually speak | **Build third if time allows.** A real OPC-UA server with simulated nodes is architecturally identical to talking to a real historian — you're proving the *client*, which is the hard/valuable part, without needing a vendor license. |

**Bottom line:** MQTT is the best live-demo answer because judges can cause an effect themselves and watch it
propagate through a real reasoning pipeline — *proof by direct manipulation* is more convincing than a real
sensor would be, because a judge trusts their own hand on the slider more than they'd trust a device they
can't verify. OPC-UA is the best enterprise-credibility answer. CSV is the unglamorous guarantee that the
feature works no matter what.

### 3.1 The Virtual Sensor Simulator panel — the thing that replaces hardware in the pitch

Instead of a bare terminal script, build a small web panel (own route, or a tab inside the wizard's Step 5
MQTT card) that looks and behaves like a physical sensor's control surface:

- A gauge/slider per gas type (O2, CO, H2S, LEL) per zone, draggable to set a target concentration.
- A toggle per worker badge: "badge enters zone X" / "badge exits zone X."
- A button: "issue hot-work permit in zone X."
- Each control publishes an MQTT message on the appropriate topic the instant it's touched.

This panel is the entire "hardware" story. A judge moving a slider and watching your dashboard react in real
time, with the real Council convening behind it, is the moment that sells the feature — arguably *more*
convincing than a physical sensor, because the judge caused the exact reading themselves and can immediately
verify cause → effect with no possibility of a rigged demo.

### 3.2 Realistic noise, not a clean ramp

Don't publish the slider value verbatim. Reuse `app/simulation/gas_process.py`'s `step()` (the
Ornstein-Uhlenbeck process already validated against SWaT in your methodology doc) so that whatever the
slider is set to becomes the process's `C_baseline` / `S_t` target, and the publisher ticks the OU process
toward it with real sensor-like jitter, instead of publishing a suspiciously smooth staircase. A technical
judge who has looked at real sensor data will notice — and trust — the difference. This is genuinely zero
new math: it's the same function your synthetic scenarios already call, imported into a new caller.

### 3.3 Multiple independent virtual devices, not one script pretending to be everything

Run the simulator as several independent publishers, one per (zone, sensor-type) pair, each on its own topic
(`corrix/{factory_id}/{zone_id}/gas`, `.../badge`, `.../permit`). This is what actually sells "five siloed
data streams fused into one picture," which is core to Corrix's pitch — a single script publishing
everything on one topic doesn't demonstrate that; several small independent publishers do.

### 3.4 Label it honestly, everywhere

Every place the UI shows live-factory data gets a small, permanent tag: **"Simulated device · real MQTT
protocol"** (or "· real OPC-UA server," or "· uploaded CSV"). This costs nothing and reads as more credible
to a technical judge than silence would — it's a direct extension of the "radical honesty" positioning your
landing page already uses for simulated vs. real scenario data. Reuse the existing `ConnectionPill.tsx`
pattern for this rather than inventing a new component.

---

## 4. Backend build plan

### Phase A — Factory profile & dynamic plant layout (unchanged from original)

1. New schema `backend/app/schemas/factory.py`:
   ```python
   class FactoryProfile(BaseModel):
       factory_id: str
       name: str
       industry: str
       location: str | None = None
       layout: PlantLayout            # reuse existing Zone/PlantLayout models as-is
       permit_types_in_use: list[str]
       shift_pattern: list[ShiftRecord]
       data_source: Literal["csv", "mqtt", "opcua"]
       created_at: datetime
   ```
   No new zone/adjacency models needed — `app/schemas/zone.py` already has the exact shape.

2. New endpoint module `backend/app/api/factory.py`:
   - `POST /api/factory` — create profile from wizard payload; validate zone IDs unique, every adjacency
     edge references a real zone; persist.
   - `GET /api/factory/{factory_id}` — fetch for the dashboard shell.
   - `PATCH /api/factory/{factory_id}/data-source` — switch/reconfigure ingestion later.
   - Storage: reuse Neo4j/AuraDB you already run for the regulatory graph and memory loop
     (`app/memory/exemplar_store.py`'s `get_shared_driver()` pattern). A `Factory` node with `HAS_ZONE` edges
     to `Zone` nodes is a cheap, natural extension — zero new infrastructure, survives a backend restart.

3. Make plant-layout loading factory-aware without touching existing call sites:
   ```python
   # app/simulation/plant_layout.py
   def load_plant_layout(factory_id: str | None = None) -> PlantLayout:
       if factory_id is None:
           return _load_static_demo_layout()   # existing @lru_cache path, unchanged
       return _load_factory_layout_from_neo4j(factory_id)
   ```
   Every existing caller keeps calling `load_plant_layout()` with no argument, completely unaffected.

### Phase B — Ingestion adapters (`backend/app/ingestion/`, new package) — the hardware-free version

All three adapters share one job: produce the *same* schema objects the scenario engine already produces
(`GasSensorReading`, `PermitRecord`, `ShiftRecord`, `BadgePingEvent`) and push them onto an `asyncio.Queue`
that a streaming loop drains — mirroring `PlaybackFrame`/`ScenarioPlayback` in `app/api/live_scenario.py` so
downstream code barely notices the difference.

1. **`csv_ingest.py`** — accepts an uploaded CSV against a column mapping collected in wizard Step 5
   ("which column is timestamp / zone / gas concentration / gas type"), replays rows in chronological order
   at a configurable speed multiplier (1x = real historian pace, 30x = watchable-in-a-demo pace), yielding
   `GasSensorReading` objects exactly as `run_gas_process` does today.

2. **`mqtt_ingest.py` + `virtual_sensor_publisher.py`** — the flagship path, fully hardware-free:
   - **Broker:** run a local Mosquitto broker (via Docker, or Render's free tier / a public test broker like
     `test.mosquitto.org` for the hackathon demo) — this is a real broker either way, nothing about it is
     simulated.
   - **`mqtt_ingest.py`** — subscriber side. Use `paho-mqtt` (tiny, well-worn, no new heavy dependency).
     Subscribes to `corrix/{factory_id}/#`, parses each message into the matching schema object, timestamps
     it, pushes to the queue. A payload validation failure is logged and dropped, never crashes the stream —
     copy the same defensive try/except pattern `app/api/websocket.py` already uses around ERO firing.
   - **`virtual_sensor_publisher.py`** — publisher side, replacing the physical device. A small
     FastAPI/WebSocket-backed service (or just a route on the existing backend) that:
     - Exposes the control surface described in §3.1 to the frontend simulator panel.
     - On each user interaction (slider move, badge toggle, permit button), updates that channel's target
       value and lets a background loop tick `gas_process.step()` toward it (§3.2), publishing the resulting
       reading to the correct topic on a fixed interval (e.g., every 1–2s) — this is what makes many
       concurrent virtual devices (§3.3) trivial: one async task per (zone, sensor) pair, each independently
       ticking and publishing.
   - Topic convention, documented for the user: `corrix/{factory_id}/{zone_id}/gas`,
     `corrix/{factory_id}/{zone_id}/badge`, `corrix/{factory_id}/{zone_id}/permit`. Worth namedropping
     **Sparkplug B** in the pitch as the real industrial-MQTT convention this loosely follows — credibility
     line, not a hard dependency.

3. **`opcua_ingest.py`** — adapter interface `connect(endpoint_url, node_ids) -> AsyncIterator[GasSensorReading]`,
   implemented against `asyncua`'s free, open-source **demo server**, run locally:
   ```python
   # backend/scripts/virtual_scada_server.py
   from asyncua import Server
   # spins up a real OPC-UA server on localhost with a handful of simulated nodes,
   # values driven by the same gas_process.step() function as the MQTT publisher
   ```
   This is a genuine OPC-UA server — real protocol, real client code on your side — with simulated node
   values instead of a live PLC behind it, which is precisely the same relationship the MQTT path has to
   hardware. If time is short, fall back to the honestly-labeled placeholder: "Enterprise SCADA connector —
   spec available, contact us to integrate with your historian." Never fabricate a fake OPC-UA response and
   present it as a live server; that's exactly what your own landing page's honesty stance would flag if a
   competitor did it.

### Phase C — The live streaming endpoint (unchanged from original)

New `app/api/live_factory_websocket.py`, a sibling to `app/api/websocket.py`, not a rewrite:

```
Client -> server:  {"type": "connect", "factory_id": "..."}
Server -> client:  {"type": "tick", "zoneRisk": {...}, "workers": {...}}     # same shape as scenario ticks
                    {"type": "council_convening"} / "deliberating" / "verdict" / "ero_fired"  # identical
```

Trigger logic reuses `app/detection/trigger.py`, `app/detection/novelty_detector.py`, and
`app/detection/retrieval_trigger.py` exactly as `precompute_playback` does today, except it scores the live
queue incrementally as readings arrive (`anomaly_scorer.score_series` already works over any list of floats —
call it over a rolling window instead of a whole precomputed run).

When a trigger fires, call the **same** `_convene_council`-shaped logic in `app/api/websocket.py`: build
`raw_evidence` text via `format_process_safety_text`, `format_permit_text`, `format_shift_text`,
`format_site_safety_text` from `app/api/live_evidence.py` (check whether they need any changes at all before
assuming a fork is necessary — they already take generic config/data), invoke `build_council_graph()`, run
evacuation routing and risk propagation, ground in the regulatory GraphRAG, fire the ERO on `CRITICAL`. If
this reuse doesn't fall out cleanly, spend an hour refactoring `_convene_council` into a shared,
source-agnostic function both paths call — worth it over duplicating ~150 lines.

### Phase D — Safety rails specific to real user input (unchanged, still applies)

- **Sanitize before it reaches an LLM prompt.** User-supplied zone names, "other" permit descriptions, and
  free text from the wizard flow into `raw_evidence` strings sent to Groq/Gemini inside the Council. Strip
  anything that looks like a prompt-injection attempt before interpolation — call this out to judges as a
  deliberate decision, not an oversight.
- **Rate-limit the MQTT bridge** per factory so a runaway virtual publisher can't flood a Council convening
  loop — same concern applies even though the publisher is yours, since a slider dragged rapidly could
  otherwise spam messages.
- **Validate CSV uploads** against expected column count/types before parsing; reject with a clear error.

---

## 5. Frontend build plan

1. **Router-lite state machine in `Root.tsx`** (no `react-router-dom` needed):
   ```
   type View = 'landing' | 'onboarding' | 'demo-console' | 'live-console'
   ```
   `LandingPage` gets a second button, `onGetStarted`, next to the existing `onLaunch`.

2. **`OnboardingWizard.tsx`** (new) — five-step form, Framer-Motion step transitions (already a dependency),
   local `useState` step state. Steps 1–4 are controlled forms. Step 2's zone/adjacency graph editor is the
   one genuinely new interactive component — plain SVG + `onMouseDown/Move/Up` handlers, no deck.gl or
   Three.js needed, bundle size unchanged.

3. **Make the dashboard shell zone-agnostic.** `frontend/src/data/plantLayout.ts` currently hardcodes
   `PLANT_ZONES` with hand-placed polygons for 8 zones. For the live-factory path, generate a layout from the
   user's zone count/adjacency at runtime (simple force-directed or grid-packing layout — legible and
   non-overlapping is enough). Gate behind the existing `PlantZone` type so `PlantHeatmap.tsx` needs minimal
   changes — same type, different source function.

4. **`useLiveFactorySocket.ts`** (new, sibling to `useScenarioSocket.ts`) — connects to
   `/ws/live-factory/{factory_id}`, drives the same Zustand store actions already in `useCorrixStore.ts`
   (`applyLiveTick`, `startLiveConvening`, `applyLiveDeliberating`, `applyLiveVerdict`, `applyEroFired`). The
   store doesn't know or care whether a tick came from a scenario replay or a live MQTT stream — almost no
   store changes needed, only a new socket hook speaking the same message shapes.

5. **`VirtualSensorPanel.tsx`** (new) — the control surface from §3.1: per-zone gas sliders, badge toggles,
   permit buttons. Publishes directly to the backend's publisher route/WebSocket on interaction. This is
   your best visual alongside the zone editor — build it with the same polish.

6. **Live Command Center** = `App.tsx`'s existing layout (`TopControlBar`, `TelemetryStrip`, `PlantHeatmap`,
   `CouncilPanel`, `AlertFeed`), rendered against the live-factory store slice, Boot Sequence replaced with a
   short "your factory is now live" confirmation instead of the scripted scenario intro.

7. **A visible, honest badge** in the live console — "LIVE FACTORY DATA · SIMULATED DEVICE (MQTT)" /
   "· UPLOADED CSV" / "· SIMULATED DEVICE (OPC-UA)" — reusing the existing `ConnectionPill.tsx` pattern. This
   is the frontend half of §3.4 and should never be optional or hideable.

---

## 6. Suggested build order

1. **Backend: `FactoryProfile` schema + `POST/GET /api/factory`** — nothing else works without this.
2. **Backend: CSV ingestion adapter + a static test upload** — proves schema-reuse end-to-end fastest, no
   broker or simulator dependency required.
3. **Frontend: wizard steps 1–4 + review screen**, posting to the new endpoint. Build the zone/adjacency
   graph editor here — best visual, do it early while you have energy for polish.
4. **Backend: live-factory WebSocket + reuse of `_convene_council`**, wired to the CSV replay path first —
   highest-risk integration point (proving the *same* Council code runs on non-scenario input), validate
   before adding MQTT complexity.
5. **Frontend: `useLiveFactorySocket` + Live Command Center** reusing `App.tsx`'s panels against the CSV
   path.
6. **Backend: `virtual_sensor_publisher.py` + `mqtt_ingest.py`.** This is your flagship live moment — budget
   real time here. Get one gas slider → one MQTT message → one dashboard tick working end to end before
   adding more channels.
7. **Frontend: `VirtualSensorPanel.tsx`** + wizard Step 5's three data-source cards.
8. **Backend: multiple concurrent virtual devices** (§3.3) — one async publisher task per zone/sensor pair.
9. **OPC-UA: `virtual_scada_server.py`** via `asyncua`'s demo server, or the honestly-labeled placeholder if
   time runs out.
10. **Safety rails (§4 Phase D)** + a short judge-facing demo script: *"watch me add my own factory, open the
    virtual sensor panel, drag one gas slider, and see the real five-agent Council reason about it in
    real time — over a real MQTT broker, with zero pre-authored scenario involved and zero physical
    hardware."*

---

## 7. What NOT to build (protect remaining hackathon time)

- No general-purpose multi-tenant auth/account system. One factory profile per session/browser proves the
  concept; user accounts are an unrelated engineering project.
- No attempt at a production OPC-UA client against real vendor hardware — no judge will have a Siemens
  historian to hand, and `asyncua`'s demo server proves the same architectural point for a fraction of the
  effort.
- Don't let the zone/adjacency graph editor become a full CAD tool. Draggable circles and click-drawn edges
  are enough.
- Don't duplicate the Council, detection engine, or regulatory grounding into a "real-data version." If
  you're writing a second copy of `app/council/`, `app/detection/`, or `app/regulatory/`, stop and refactor
  the interface boundary instead.
- Don't build more than one virtual-device UI. One well-built `VirtualSensorPanel.tsx` covering gas, badges,
  and permits is enough — resist the urge to build separate panels per sensor type.

---

## 8. Definition of done

- [ ] Landing page has both "Launch live demo" (unchanged) and "Get Started" (new); neither can break the
      other.
- [ ] A user can complete the 5-step wizard and land in a Live Command Center rendering their own zones and
      adjacency graph, not the static 8-zone layout.
- [ ] At least one real ingestion path (CSV, minimum) drives a real trigger → real Council convening → real
      verdict, end to end, with zero scenario YAML involved.
- [ ] The MQTT flagship path: a judge drags a slider on `VirtualSensorPanel.tsx`, a real MQTT message
      publishes over a real broker, and a verdict appears on the dashboard within seconds.
- [ ] Every live-console screen visibly and honestly labels its data source, including that the device is
      simulated where applicable — never silent, never overstated.
- [ ] No existing test in `backend/tests/` regresses; new tests live under
      `backend/tests/test_factory_*.py` / `test_ingestion_*.py`.
