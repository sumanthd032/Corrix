# Corrix — "Bring Your Own Factory" (BYOF)
### Step-by-step implementation guide for a code generator

**How to use this document:** each step is self-contained, has a single clear goal, lists exactly which
files to create or touch, and ends with a **Verify** checklist. Do not start step *N+1* until step *N*'s
Verify checklist passes. Steps are ordered so that the app is always in a runnable, non-broken state after
each one — if something goes wrong, you can always roll back to the end of the previous step rather than to
the start of the whole feature.

**Global rule for every step below:** never edit any file under `frontend/src/components/BootSequence*`,
`DemoIntro*`, `PresenterMode*`, the five scenario YAMLs, `app/api/live_scenario.py`,
`app/simulation/scenario_engine.py`, or any existing file in `backend/tests/`. If a step seems to require
editing one of these, stop and re-read Step 0 — the boundary is wrong.

---

## Step 0 — Read before writing anything

Open and read, without editing:
- `frontend/src/Root.tsx`, `App.tsx`, `components/LandingPage.tsx`, `store/useCorrixStore.ts`,
  `lib/useScenarioSocket.ts`, `data/plantLayout.ts`
- `backend/app/main.py`, `app/api/websocket.py` (especially `_convene_council`, lines ~113–200),
  `app/api/live_scenario.py`, `app/api/live_evidence.py`, `app/simulation/plant_layout.py`,
  `app/simulation/gas_process.py`, all files in `app/schemas/`, `app/council/graph.py`,
  `app/detection/trigger.py`, `app/detection/anomaly_scorer.py`, `app/memory/exemplar_store.py`

**Verify:** you can answer, without re-opening the files: (1) what four `raw_evidence` keys
`_convene_council` builds and which `format_*` functions build them, (2) what fields `PlantLayout`,
`Zone`, `ZoneAdjacencyEdge`, `GasSensorReading` require, (3) how `get_shared_driver()` is used elsewhere for
Neo4j. If you can't answer all three, go back and read again — every later step assumes this.

---

## PHASE 1 — Backend foundation (factory profile, no ingestion yet)

### Step 1 — `FactoryProfile` schema

Create `backend/app/schemas/factory.py`:

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from app.schemas.zone import PlantLayout
from app.schemas.shift import ShiftRecord

class FactoryProfile(BaseModel):
    factory_id: str
    name: str
    industry: str
    location: str | None = None
    layout: PlantLayout
    permit_types_in_use: list[str]
    shift_pattern: list[ShiftRecord]
    data_source: Literal["csv", "mqtt", "opcua"] = "csv"
    created_at: datetime
```

Check `app/schemas/shift.py`'s actual `ShiftRecord` field names before writing this — import what's really
there, don't guess the fields.

Add `FactoryProfile` to `app/schemas/__init__.py`'s exports, following the same pattern already used for the
other schema exports in that file.

**Verify:** `python -c "from app.schemas import FactoryProfile"` runs with no import error.
`pytest backend/tests/` still shows the same pass count as before this step (nothing should be broken by
adding an unused schema).

---

### Step 2 — Neo4j persistence for `FactoryProfile`

Create `backend/app/storage/factory_store.py` (new package `app/storage/` if it doesn't exist):

- `save_factory(profile: FactoryProfile) -> None` — uses `get_shared_driver()` from
  `app/memory/exemplar_store.py` (import it, don't re-implement driver setup). Writes a `Factory` node with
  its scalar fields, and `HAS_ZONE` edges to `Zone` nodes for each zone in `profile.layout.zones`, and
  `ADJACENT_TO` edges between zones per `profile.layout.adjacency`.
- `load_factory(factory_id: str) -> FactoryProfile | None` — inverse query, reconstructs the Pydantic model.

Write one standalone test script (not a `pytest` file yet) that saves a hand-built `FactoryProfile` with 2
zones and 1 adjacency edge, reloads it, and asserts equality — run it manually against your dev Neo4j
instance to confirm the Cypher is correct before wiring it into an endpoint.

**Verify:** the manual round-trip script prints "OK" / passes its assertion. No existing test file touched.

---

### Step 3 — `POST /api/factory` and `GET /api/factory/{factory_id}`

Create `backend/app/api/factory.py`:

```python
from fastapi import APIRouter, HTTPException
router = APIRouter(prefix="/api/factory", tags=["factory"])

@router.post("")
async def create_factory(profile: FactoryProfile) -> dict:
    # validate: zone_ids unique, every adjacency edge references a real zone_id
    # on failure: raise HTTPException(422, detail=...)
    ...

@router.get("/{factory_id}")
async def get_factory(factory_id: str) -> FactoryProfile:
    # 404 if not found
    ...
```

Register it in `backend/app/main.py` the same way every other router is registered:
```python
from app.api.factory import router as factory_router
...
app.include_router(factory_router)
```
This is the **only** line you touch in `main.py` in this step — do not reorder or modify any existing
`include_router` call.

Write `backend/tests/test_factory_api.py` (new file, does not touch any existing test file): test create with
valid payload → 200; create with a dangling adjacency edge → 422; get unknown id → 404; get after create →
matches what was posted.

**Verify:** `pytest backend/tests/test_factory_api.py -v` — all new tests pass. `pytest backend/tests/` —
same pre-existing pass count as Step 1, plus your new tests, zero regressions.

---

### Step 4 — `PATCH /api/factory/{factory_id}/data-source`

Add to `backend/app/api/factory.py`:
```python
@router.patch("/{factory_id}/data-source")
async def set_data_source(factory_id: str, data_source: Literal["csv", "mqtt", "opcua"]) -> FactoryProfile:
    ...
```
Update the stored node's `data_source` field and return the updated profile.

**Verify:** new test in `test_factory_api.py` — patch changes `data_source`, subsequent `GET` reflects it.
Full backend test suite still green.

---

### Step 5 — Factory-aware plant layout loader

Edit `backend/app/simulation/plant_layout.py`. **Do not remove or rename the existing function** — add an
optional parameter:

```python
def load_plant_layout(factory_id: str | None = None) -> PlantLayout:
    if factory_id is None:
        return _load_static_demo_layout()   # existing behavior, byte-for-byte unchanged
    from app.storage.factory_store import load_factory
    profile = load_factory(factory_id)
    if profile is None:
        raise ValueError(f"unknown factory_id: {factory_id}")
    return profile.layout
```

**Verify:** grep the codebase for every existing call site of `load_plant_layout(` — confirm every one calls
it with zero arguments and still works unmodified. Run the full existing test suite; pass count must be
identical to before this step (this function is on the hot path for the synthetic demo, so this is the
highest-risk step in Phase 1 — treat a single regression here as a blocker).

---

**Phase 1 checkpoint:** you can `POST` a hand-built factory JSON, `GET` it back, `PATCH` its data source, and
the synthetic demo (`/ws/scenario`) still works exactly as before. Confirm this manually by running the
existing frontend against the backend and clicking through "Launch live demo" end to end before moving on.

---

## PHASE 2 — CSV ingestion path (proves the reuse story, no broker/simulator needed yet)

### Step 6 — CSV ingestion adapter

Create package `backend/app/ingestion/__init__.py` and `backend/app/ingestion/csv_ingest.py`:

```python
async def replay_csv(
    file_bytes: bytes,
    column_map: dict,          # {"timestamp": "ts_col", "zone": "zone_col", "gas_concentration": "...", "gas_type": "..."}
    speed_multiplier: float,
    queue: "asyncio.Queue",
) -> None:
    # pandas.read_csv, validate column_map keys exist as columns, sort by timestamp,
    # yield GasSensorReading objects onto queue at (real_dt / speed_multiplier) pacing
    ...
```

Reuse `pandas` (already a backend dependency, do not add a new one). On a missing/mistyped column, raise a
clear `ValueError` with the offending column name — do not silently skip or mis-map.

Write `backend/tests/test_ingestion_csv.py` (new file): a small in-memory CSV (5 rows) with correct
column_map produces 5 `GasSensorReading` objects on the queue in chronological order; a CSV missing a mapped
column raises `ValueError`.

**Verify:** `pytest backend/tests/test_ingestion_csv.py -v` passes. Full suite still green.

---

### Step 7 — Decouple `_convene_council` from `ScenarioPlayback`

This is the step your original plan flagged as "worth an hour refactoring" — do it now, before building the
live WebSocket, so Step 8 has a clean function to call.

In `backend/app/api/websocket.py`, `_convene_council` currently takes a `ScenarioPlayback` and pulls
`raw_evidence`, `trigger_reason`, `zone_id`, `scenario_id`, and `memory_context` out of it internally.
Extract a new function that takes those five values directly:

```python
async def _run_council(
    websocket: WebSocket,
    incoming: "asyncio.Queue[dict]",
    zone_id: str,
    trigger_reason: str,
    raw_evidence: dict,
    scenario_id: str | None,
    memory_context: str | None,
) -> None:
    # body = everything _convene_council currently does AFTER it finishes unpacking `playback`
    ...

async def _convene_council(websocket, incoming, playback: ScenarioPlayback) -> None:
    # unpack playback into the five values exactly as today, then:
    await _run_council(websocket, incoming, zone_id=..., trigger_reason=..., raw_evidence=...,
                        scenario_id=..., memory_context=...)
```

`_convene_council`'s existing callers (`_stream_playback`) are untouched — same signature, same behavior,
just delegating internally now.

**Verify:** run the **entire existing backend test suite**, especially `test_live_scenario.py` and any
websocket-related tests. Pass count must be identical to before this refactor — this is a pure extraction, no
behavior change. Manually re-run the synthetic demo end to end in the frontend to visually confirm council
convening still looks the same.

---

### Step 8 — Live-factory WebSocket, wired to the CSV path

Create `backend/app/api/live_factory_websocket.py`, structured as a sibling to `app/api/websocket.py`:

```python
async def live_factory_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    # 1. receive {"type": "connect", "factory_id": ...}
    # 2. load_plant_layout(factory_id) via Step 5's function
    # 3. based on profile.data_source, start the matching ingestion adapter feeding an asyncio.Queue
    #    (Step 6's replay_csv for now — mqtt/opcua adapters don't exist until Phase 3/4)
    # 4. drain the queue in a loop: send {"type": "tick", ...} per reading,
    #    score with app.detection.trigger / anomaly_scorer over a rolling window
    # 5. on trigger: call _run_council(...) from Step 7 with the live evidence
    ...
```

For evidence text, reuse `format_process_safety_text`, `format_permit_text`, `format_shift_text`,
`format_site_safety_text` from `app/api/live_evidence.py` — check their real signatures first; if they
require scenario-specific config objects you don't have in the live-factory path, wrap the factory's
zones/permits/shifts into the minimal equivalent shape rather than forking the functions.

Register the route in `app/main.py`:
```python
from app.api.live_factory_websocket import live_factory_websocket
app.websocket("/ws/live-factory/{factory_id}")(live_factory_websocket)
```
Again, this is the only new line in `main.py` for this step.

Write `backend/tests/test_live_factory_websocket.py`: use FastAPI's `TestClient` websocket testing, connect
with a factory that has `data_source="csv"` and a pre-uploaded/mocked CSV, assert you receive at least one
`tick` message and (with a CSV engineered to cross a threshold) a `verdict` message.

**Verify:** new test passes. Full suite green. Manually connect a WebSocket client (e.g. `websocat` or a
throwaway script) to `/ws/live-factory/{factory_id}` against a real factory created in Step 3 and see ticks
stream.

---

### Step 9 — CSV upload endpoint

Add to `backend/app/api/factory.py`:
```python
@router.post("/{factory_id}/csv-upload")
async def upload_csv(factory_id: str, file: UploadFile, column_map: str) -> dict:
    # column_map arrives as a JSON string from a multipart form field; json.loads it
    # validate columns per Step 6's rules, store the file (or its parsed rows) associated with factory_id
    # so Step 8's websocket can find it when data_source == "csv"
    ...
```
Decide storage: simplest is writing the raw CSV to a per-factory path under a `data/factory_uploads/`
directory (gitignored) and having Step 8 read it by `factory_id` — do not over-engineer this into a database
table.

**Verify:** new test — upload a valid CSV, then connect the Step 8 websocket for that factory, confirm ticks
now come from the uploaded file's actual values, not a placeholder.

---

**Phase 2 checkpoint — the single most important milestone in this whole build:** a factory created via
`POST /api/factory`, fed a real uploaded CSV, produces a real trigger → real Council convening → real verdict
over `/ws/live-factory/{factory_id}`, using the exact same `_run_council` function the synthetic demo uses.
Do not proceed to Phase 3 until this works and is demoable, even roughly, in the frontend — everything after
this point is additive polish and additional data sources, not new architecture.

---

## PHASE 3 — Frontend wizard + live console (against the CSV path)

### Step 10 — Router-lite state in `Root.tsx`

Edit `frontend/src/Root.tsx`. Add the view-state type and a second landing-page callback, without touching
the existing `onLaunch` branch:

```tsx
type View = 'landing' | 'onboarding' | 'demo-console' | 'live-console';
// existing onLaunch logic → sets 'demo-console', unchanged
// new onGetStarted → sets 'onboarding'
```

Edit `LandingPage.tsx` to accept and render a second button calling `onGetStarted`, placed next to the
existing "Launch live demo" button — do not remove, rename, or restyle the existing button.

**Verify:** app still boots to landing page; clicking "Launch live demo" behaves exactly as before
(pixel-for-pixel, same components mount). Clicking the new "Get Started" button (which can render a bare
placeholder `<div>Onboarding coming soon</div>` at this step) navigates away from landing and back correctly.

---

### Step 11 — `OnboardingWizard.tsx` steps 1, 3, 4 (simple forms first)

Create `frontend/src/components/OnboardingWizard.tsx` with step state (`useState<number>`) and Framer-Motion
transitions (already a dependency). Build **Step 1 (identity)**, **Step 3 (workforce/shifts)**, and
**Step 4 (permits)** first — these are plain controlled forms with no new interaction pattern, so building
them first gets the wizard shell and navigation (Next/Back, validation-before-advance) working before you
tackle the harder Step 2 graph editor.

Leave Step 2 as a placeholder screen for now (`<div>Zone editor — Step 12</div>`) so the wizard is
click-through-able end to end.

**Verify:** can navigate Step 1 → 3 → 4 → (placeholder 2) → Review, Back button returns to prior step with
form values retained, Next is disabled until required fields are filled.

---

### Step 12 — Zone & adjacency graph editor (Step 2 of the wizard)

Build the SVG node-graph editor described in the plan: draggable circle/rect per zone (click "add zone" to
create one, fill name/hazard-class/flags in a small side panel), click-drag from one node to another to
create an adjacency edge, click an existing edge to delete it. Plain SVG + `onMouseDown/Move/Up`, no new
library.

Store the resulting `{zones: Zone[], adjacency: ZoneAdjacencyEdge[]}` in the wizard's step state using the
**exact same field names** as `app/schemas/zone.py`'s `Zone` and `ZoneAdjacencyEdge` — this avoids a mapping
layer when you POST to the backend in Step 13.

**Verify:** can add 3+ zones, drag them apart without overlap-locking, draw 2+ adjacency edges, delete one,
and the resulting JS object matches the backend schema shape exactly (log it and eyeball it against
`zone.py`).

---

### Step 13 — Review screen + `POST /api/factory`

Build the Review step: summarizes all 4 steps, "Launch" button that POSTs the assembled `FactoryProfile`
payload (minus `data_source`, defaulted to `"csv"` for now since MQTT/OPC-UA don't exist yet in the UI) to
`POST /api/factory`. On success, transition `Root.tsx`'s view to `'live-console'` carrying the returned
`factory_id`. On a 422 validation error, surface the backend's error message inline rather than a generic
failure toast.

**Verify:** completing the full wizard creates a real factory row in Neo4j (confirm via Step 3's `GET`
endpoint or a direct Neo4j browser query), and failure cases (e.g. deliberately break an adjacency edge to
reference a non-existent zone) show a real, specific error instead of crashing the wizard.

---

### Step 14 — Dynamic plant layout rendering

Edit `frontend/src/data/plantLayout.ts` (or add a sibling file, do not delete the existing static
`PLANT_ZONES` export) to add a new function:
```ts
export function layoutFromZones(zones: Zone[], adjacency: ZoneAdjacencyEdge[]): PlantZone[]
```
Implement a simple force-directed or grid-packing placement (no need for a physically accurate factory floor
plan — legible and non-overlapping is the bar) that produces the same `PlantZone[]` shape the static array
already produces, so `PlantHeatmap.tsx` needs **zero changes** — only its data source changes depending on
view mode.

**Verify:** feed it a 5-zone, 4-edge test graph, render through the existing `PlantHeatmap.tsx` unmodified,
confirm zones render without overlapping and without touching `PlantHeatmap.tsx`'s source.

---

### Step 15 — `useLiveFactorySocket.ts`

Create `frontend/src/lib/useLiveFactorySocket.ts`, sibling to `useScenarioSocket.ts`. Connects to
`/ws/live-factory/{factory_id}`, parses incoming `tick` / `council_convening` / `deliberating` / `verdict` /
`ero_fired` messages, and calls the **same** existing Zustand actions in `useCorrixStore.ts` that
`useScenarioSocket.ts` already calls (`applyLiveTick`, `startLiveConvening`, `applyLiveDeliberating`,
`applyLiveVerdict`, `applyEroFired`). Do not add new store actions unless a message shape genuinely doesn't
fit an existing one — check first.

**Verify:** connecting this hook to a factory from Step 8's backend produces visible ticks/verdicts in a
throwaway test render, using unmodified store actions.

---

### Step 16 — Live Command Center screen

Assemble the live-console view in `Root.tsx`'s `'live-console'` branch: reuse `App.tsx`'s existing panel
layout (`TopControlBar`, `TelemetryStrip`, `PlantHeatmap`, `CouncilPanel`, `AlertFeed`) but fed by Step 15's
hook and Step 14's dynamic layout instead of the scenario store slice. Replace `BootSequence`/`DemoIntro`
with a short "Your factory is now live" confirmation screen shown once on entry.

**Verify:** full click-through — Get Started → wizard → Review/Launch → Live Command Center — renders the
user's own zones, and (with a CSV uploaded via Step 9 that's engineered to cross a threshold) a real verdict
appears in `CouncilPanel` sourced from real backend data.

---

**Phase 3 checkpoint:** the CSV path is fully demoable end-to-end through the UI with zero manual API calls.
This is a legitimate stopping point if you're short on time — it already satisfies "real data in, real
Council out."

---

## PHASE 4 — Virtual MQTT flagship path (hardware-free)

### Step 17 — Local MQTT broker + `paho-mqtt` dependency

Add `paho-mqtt` to `backend/requirements.txt` (pin a version, do not leave unpinned). Stand up a broker for
development: either a local Mosquitto via Docker (`docker run -p 1883:1883 eclipse-mosquitto`) or point at a
public test broker (`test.mosquitto.org`) for early development, switching to your own broker before the
final demo so you're not dependent on a third-party service being up. Document the choice in a short
`backend/app/ingestion/README.md`.

**Verify:** `pip install -r backend/requirements.txt` succeeds. A one-off script publishes a test message and
a second script subscribing to the same topic receives it — confirms the broker is reachable before writing
any adapter code against it.

---

### Step 18 — `mqtt_ingest.py` (subscriber side)

Create `backend/app/ingestion/mqtt_ingest.py`:
```python
async def stream_mqtt(factory_id: str, broker_host: str, broker_port: int, queue: "asyncio.Queue") -> None:
    # subscribe to corrix/{factory_id}/#
    # on each message: parse topic to get zone_id + reading_type, parse payload,
    # build the matching schema object (GasSensorReading / BadgePingEvent / PermitRecord),
    # push to queue. On parse failure: log and drop, never raise into the caller.
```
Wire `data_source == "mqtt"` into Step 8's live-factory websocket as an alternative to `replay_csv`.

Write `backend/tests/test_ingestion_mqtt.py`: use a local test broker (or an in-process fake if `paho-mqtt`
supports one cleanly) — publish 3 well-formed messages and 1 malformed one, assert 3 objects land on the
queue and the malformed one is dropped without crashing the stream.

**Verify:** test passes. Full suite green.

---

### Step 19 — `virtual_sensor_publisher.py` (the hardware replacement)

Create `backend/app/ingestion/virtual_sensor_publisher.py`. This is the backend half of the Virtual Sensor
Simulator:
```python
class VirtualChannel:
    # one instance per (factory_id, zone_id, sensor_type) — holds current target + OU state

async def set_target(factory_id, zone_id, sensor_type, target_value) -> None:
    # called when a user moves a slider / toggles a badge / fires a permit button
    ...

async def run_publisher_loop(factory_id: str) -> None:
    # one background asyncio task per active VirtualChannel:
    # every 1-2s, call gas_process.step() (imported unmodified from app.simulation.gas_process)
    # to move current value toward target with realistic OU jitter, then
    # paho-mqtt publish to corrix/{factory_id}/{zone_id}/{sensor_type}
```
Import `step()` from `app/simulation/gas_process.py` directly — do not re-implement the OU math.

Expose a small FastAPI route group `backend/app/api/virtual_sensor.py`:
- `POST /api/virtual-sensor/{factory_id}/{zone_id}/gas` — body `{gas_type, target_concentration}`, calls
  `set_target`.
- `POST /api/virtual-sensor/{factory_id}/{zone_id}/badge` — body `{badge_id, entering: bool}`.
- `POST /api/virtual-sensor/{factory_id}/{zone_id}/permit` — body `{permit_type}`.

Register this router in `main.py` the same way as Step 3.

**Verify:** a manual script calling `POST /api/virtual-sensor/.../gas` with a high target concentration
results in messages appearing on the MQTT topic within a couple seconds, with values that visibly jitter
around a rising trend rather than jumping straight to the target — confirm by subscribing to the topic with a
plain MQTT client and eyeballing the value sequence.

---

### Step 20 — Wire MQTT end-to-end into a live factory

Connect Steps 18+19: create a factory with `data_source="mqtt"`, connect `/ws/live-factory/{factory_id}`,
hit the virtual sensor endpoints from Step 19, and confirm ticks arrive over the websocket sourced from real
MQTT messages, and that an engineered high-concentration target eventually triggers a real Council convening
exactly as the CSV path did in Step 8.

Write `backend/tests/test_live_factory_mqtt_e2e.py` covering this full loop against a test broker.

**Verify:** new e2e test passes. Full suite green. This is the highest-value manual demo you can run at this
point — actually do it once, watching real terminal/log output, before moving to frontend work.

---

### Step 21 — `VirtualSensorPanel.tsx`

Create `frontend/src/components/VirtualSensorPanel.tsx`: a slider per gas type per zone (calls
`POST /api/virtual-sensor/.../gas` on drag, debounced to avoid flooding), a toggle per badge, a button per
permit type. Wire it into wizard Step 5's "Connect Virtual IoT (MQTT)" card and, more importantly, make it
reachable from the Live Command Center itself (a drawer or tab) so a judge can trigger events *while already
watching the dashboard* — that's the actual demo moment, not the wizard step.

**Verify:** dragging a slider in the live console visibly moves the corresponding gauge/number on
`TelemetryStrip`/`PlantHeatmap` within a couple seconds, and a sustained high value produces a verdict in
`CouncilPanel` — the full loop, now entirely through the UI with no manual API calls.

---

### Step 22 — Multiple concurrent virtual devices

Confirm (don't just assume) that Step 19's `run_publisher_loop` correctly runs one independent async task
per active `(zone_id, sensor_type)` channel, so that setting targets in 3 different zones produces 3
independently-jittering, concurrently-publishing streams rather than one shared loop overwriting itself.

**Verify:** set different targets in 3 zones simultaneously via `VirtualSensorPanel.tsx`, confirm all 3
zones' values evolve independently and concurrently on the dashboard (not sequentially, not one zone stalling
the others).

---

### Step 23 — Honest labeling (`ConnectionPill` reuse)

Add the "LIVE FACTORY DATA · SIMULATED DEVICE (MQTT)" / "· UPLOADED CSV" / "· SIMULATED DEVICE (OPC-UA)"
badge to the Live Command Center, reusing the existing `ConnectionPill.tsx` component/pattern rather than a
new one. It must reflect the factory's actual `data_source` and never be hideable or dismissible.

**Verify:** the badge text updates correctly across all three `data_source` values by manually switching a
test factory's data source via Step 4's PATCH endpoint and reloading the live console.

---

**Phase 4 checkpoint:** the flagship demo works — a judge (or you) drags a slider, a real MQTT message
publishes, a real Council convenes, a verdict appears, all visibly labeled as using a simulated device over a
real protocol. If you're tight on time, this is the point to stop and move straight to Step 26 (safety rails)
and Step 27 (demo script), skipping Phase 5 (OPC-UA) entirely and shipping the honestly-labeled placeholder
card instead.

---

## PHASE 5 — OPC-UA (optional, time-permitting)

### Step 24 — `asyncua` demo server

Add `asyncua` to `backend/requirements.txt`. Create `backend/scripts/virtual_scada_server.py`: spins up a
local `asyncua.Server()` with a handful of simulated nodes (e.g. one node per zone's gas concentration),
values driven by the same `gas_process.step()` function as Step 19's MQTT publisher (reuse, don't
reimplement).

**Verify:** running the script starts a real OPC-UA server on localhost; a throwaway `asyncua` client script
can connect and read a changing node value.

---

### Step 25 — `opcua_ingest.py`

Create `backend/app/ingestion/opcua_ingest.py` implementing
`connect(endpoint_url, node_ids) -> AsyncIterator[GasSensorReading]` against Step 24's server, wired into
Step 8's live-factory websocket as the third `data_source` option. If time runs out here, skip straight to
shipping the frontend's "Enterprise SCADA connector — spec available" placeholder card instead — do not ship
a fake OPC-UA response labeled as real.

**Verify:** either (a) a factory with `data_source="opcua"` produces real ticks from Step 24's server through
the same websocket path as CSV/MQTT, or (b) the UI clearly shows the honest placeholder with no backend claim
of a live connection.

---

## PHASE 6 — Safety rails and final polish

### Step 26 — Input sanitization, rate limiting, upload validation

- Add a character allow-list check on every free-text wizard field (zone names, "other" permit text) before
  it can reach `raw_evidence` / an LLM prompt. Reject or strip on the backend, not just the frontend, since
  the frontend check can be bypassed by a direct API call.
- Rate-limit `POST /api/virtual-sensor/*` per `factory_id` (simple in-memory token bucket is enough at
  hackathon scope) so a rapidly-dragged slider or a scripted flood can't overwhelm the Council convening
  loop.
- Confirm Step 9's CSV upload rejects malformed column counts/types with a clear error rather than silently
  mis-mapping a column (re-verify this explicitly now that the rest of the system exists around it).

**Verify:** a scripted attempt to inject instruction-like text into a zone name is stripped before reaching
`raw_evidence` (log and inspect the actual string sent to the Council). A scripted flood of virtual-sensor
POSTs is throttled without crashing the backend. A malformed CSV upload returns a clear 422, not a silent
partial import.

---

### Step 27 — Full regression pass + demo script

- Run the **entire** `backend/tests/` suite and confirm the pass count is the original count plus every new
  test file added in this document — zero regressions, zero skipped-and-forgotten tests.
- Manually run the **synthetic** demo end-to-end one more time (Launch live demo → five scenarios →
  PresenterMode) to confirm it is untouched.
- Manually run the **BYOF** demo end-to-end: Get Started → wizard (all 5 steps, real zone graph) → Review →
  Live Command Center → open the virtual sensor panel → drag one gas slider → watch a real verdict appear →
  confirm the honesty badge is correct.
- Write a one-paragraph judge-facing script: *"Watch me add my own factory, draw its zone layout, open the
  virtual sensor panel, and drag one gas reading up — that's a real MQTT message over a real broker, scored
  by the same five-agent Council you just saw reasoning about our synthetic scenarios, with zero pre-authored
  scenario involved and zero physical hardware."*

**Verify:** both demos run back-to-back without restarting the backend, in front of a second person if
possible, with no console errors in either the frontend or backend logs.

---

## Definition of done (final checklist)

- [ ] Landing page: "Launch live demo" (unchanged) + "Get Started" (new), neither breaks the other.
- [ ] 5-step wizard produces a real `FactoryProfile`, including a hand-drawn zone/adjacency graph.
- [ ] CSV path: real upload → real trigger → real Council → real verdict, zero scenario YAML involved.
- [ ] MQTT path: virtual sensor panel → real broker message → real Council → real verdict, within seconds,
      end to end through the UI.
- [ ] OPC-UA: either a real `asyncua`-backed path, or an honestly-labeled placeholder — never a fake one.
- [ ] Every live-console view labels its actual data source, including "simulated device" where applicable.
- [ ] `_run_council` (Step 7) is the single shared function both the synthetic and BYOF paths call — no
      duplicated Council/detection/regulatory logic anywhere.
- [ ] Full `backend/tests/` suite green, original tests untouched, new tests isolated in new
      `test_factory_*.py` / `test_ingestion_*.py` / `test_live_factory_*.py` files.
- [ ] Both demo paths run back-to-back without a backend restart.
