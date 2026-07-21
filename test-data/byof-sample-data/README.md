# BYOF test data

Sample data for exercising the Bring Your Own Factory feature end to end
(branch `feature/bring-your-own-factory`). Nothing here is imported by the
app; it exists only so you can drive the wizard's file pickers with
realistic values instead of typing them from scratch.

## What's in this folder

Gas readings (required data stream):
- `quick_spike_single_zone.csv` — 10 calm rows then one sharp spike on a
  single zone (Z1, LEL). Use this first — fastest way to prove a verdict
  comes back at all.
- `historian_readings.csv` — a 4-zone, 30-minute-per-zone historian
  export. Three zones ramp into a real anomaly near the end (Z1 rising
  LEL, Z2 rising CO, Z3 falling O2); Z4 (H2S) stays calm the whole time as
  a control channel.
- `gen_historian_csv.py` — the script that generated `historian_readings.csv`
  (seeded, reproducible). Not needed to run the test; kept for reference.

Permit log and badge/turnstile log (optional data streams — see "Why
three files" below):
- `quick_permit_single_zone.csv` — one active hot-work permit in Z1,
  timed to overlap `quick_spike_single_zone.csv`'s spike.
- `quick_badge_single_zone.csv` — one badge entering Z1 at the start of
  the same window.

Reference only:
- `column_map.json` — shows the column-map shape the wizard's upload step
  now builds for you automatically; no need to construct this by hand
  anymore.

## Why three files, not one

Corrix's actual pitch is gas + permit + shift/badge fused into one
compound-risk verdict — the "three routine signals, one compound risk"
line on the landing page. Uploading only the gas CSV genuinely drives
real zones and a real Council verdict, but the Council's permit and
workforce evidence formatters had no real data to draw on, so every
convening reported "no active permits on file" / "no workers detected,"
even though the wizard collects a permit-types list and a worker count.
That's now fixed: the CSV data source accepts an optional permit log and
an optional badge log alongside the required gas file, each replayed
concurrently so their events interleave in real time with the gas stream.

## CSV upload happens entirely in the wizard

The wizard's sixth step, **Upload data**, appears when you pick CSV as
the data source in Review. It creates the factory, then shows three
upload cards:

1. **Gas readings** (required) — drives the live trigger.
2. **Permit log** (optional, skippable) — real `PermitRecord`s, so the
   Council can cite an actually-active permit instead of "none on file."
3. **Badge / turnstile log** (optional, skippable) — real
   `BadgePingEvent`s, so "Workers on site" and the Council's site-safety
   evidence reflect a real roster instead of staying at 0.

Each card shows a plain-language format spec (using your actual zone IDs
and permit types), a "download a sample shaped for your factory" button
that generates a ready-to-edit file on the spot, drag-and-drop upload,
auto-detected column mapping (with dropdowns to correct it), and a row
preview. One shared playback-speed field applies to all three uploads so
gas, permit, and badge events stay correlated in time. "Enter the Live
Command Center" only unlocks once gas is uploaded and the other two are
either uploaded or explicitly skipped ("I don't have this data").

Verified end to end in a real browser (Chrome via claude-in-chrome)
against the running backend: wizard → real factory created in Neo4j →
all three files uploaded and mapped in the UI → Live Command Center
showing "Workers on site: 1" before any trigger even fired → a real
Council verdict whose own reasoning text read *"Hot work permit P-5001 is
currently active"* and *"Badge W-FT-001 is currently located in Zone
Z1"* — the real records I'd just uploaded, not placeholders. Zero manual
API calls, no console errors.

## Testing the CSV + permit + badge fusion path

1. Run the app, click the landing page button (labeled **"Bring Your Own
   Factory"**), and go through the wizard:
   - **Step 1 — Identity:** e.g. Name `Bhavani Steel Works`, industry
     `steel`, location `Bellary, Karnataka`.
   - **Step 2 — Zones:** add 4 zones in this exact order so their
     auto-generated IDs (`Z1`, `Z2`, `Z3`, `Z4`) line up with the CSVs:
     1. `Ladle Bay` — hazard class `high`
     2. `Gas Main` — hazard class `high`
     3. `Maintenance Bay` — hazard class `medium`, confined space on
     4. `Control Room` — hazard class `low`
     Draw a couple of adjacency edges between them.
   - **Step 3 — Workforce:** worker count `48`, badge prefix `W-BG`, one
     shift `06:00`–`14:00`, changeover `15` min, zones `Z1,Z2,Z3,Z4`.
   - **Step 4 — Permits:** check `hot_work` and `confined_space_entry`.
   - **Step 5 — Review:** data source **CSV**, click "Continue to data
     upload."
   - **Step 6 — Upload data:**
     - Gas readings: drop in `quick_spike_single_zone.csv`, confirm the
       auto-mapped columns (`timestamp`, `zone_id`, `concentration`,
       `gas`), click Upload.
     - Permit log: drop in `quick_permit_single_zone.csv`, confirm
       auto-mapping, click Upload.
     - Badge log: drop in `quick_badge_single_zone.csv`, confirm
       auto-mapping, click Upload.
     - Click "Enter the Live Command Center."
2. You land in the Live Command Center immediately showing "Workers on
   site: 1." Within a few seconds (playback speed 30x) a real verdict
   should land. Expand the Council's reasoning (the chevron under the
   verdict badge) and confirm it references the real permit ID (`P-5001`)
   and badge ID (`W-FT-001`), not "no data on file."
3. Once that works, repeat with `historian_readings.csv` for a longer,
   multi-zone run (`speed_multiplier` around `120` is a reasonable
   watchable pace given it spans 30 minutes of simulated time). You'll
   need your own permit/badge CSVs matching those zone IDs and
   timestamps if you want the fusion story on that run too.
4. If you ever need the raw API instead of the UI (e.g. scripting a batch
   of test factories), the endpoints are `POST /api/factory/{id}/csv-upload`,
   `.../permit-upload`, `.../badge-upload`, all multipart with
   `column_map` as a JSON string form field — `column_map.json` in this
   folder shows the gas shape; permit/badge shapes are documented in the
   wizard's own format-spec boxes.

## Testing the MQTT flagship path

This one doesn't need any file — it's fully wired through the UI, and
already covers gas, permits, and badges together (unlike CSV until this
fix, MQTT's virtual sensor panel always had all three):

1. Repeat the wizard with data source **MQTT** instead of CSV.
2. In the Live Command Center, open the Virtual Sensor Panel.
3. Drag a gas slider for `Z1` (ranges: O2 0–25%, CO 0–200ppm, H2S 0–100ppm,
   LEL 0–100%) to a clearly hazardous value (e.g. LEL to 60%) and hold it
   there. Within a couple of seconds you should see the reading move on
   `TelemetryStrip`/`PlantHeatmap`, then a Council convening, then a
   verdict.
4. Try the badge-enter/exit and permit-fire buttons too — they publish on
   the `corrix/{factory_id}/{zone_id}/badge` and `.../permit` topics and
   should show up in `AlertFeed`/workforce state.

Note: the default broker is the public `test.mosquitto.org:1883`
(`backend/app/ingestion/README.md`) — if that's unreachable from your
network, set `MQTT_BROKER_HOST`/`MQTT_BROKER_PORT` to a local Mosquitto
instance (`docker run -p 1883:1883 eclipse-mosquitto`) before testing.

## Testing OPC-UA (built, but not exposed in the wizard UI)

The backend has a real implementation (`backend/app/ingestion/opcua_ingest.py`,
`backend/scripts/virtual_scada_server.py`), but the wizard's Review step
only offers CSV/MQTT — there's no OPC-UA option in the UI. To exercise it:

1. Start the demo server: `python backend/scripts/virtual_scada_server.py`
   (spins up a real OPC-UA server on localhost with `Z1_LEL`, `Z2_CO`,
   `Z3_H2S` simulated nodes — note the fixed node map, so a factory tested
   this way should have zones literally named/ID'd to match, or you're
   just confirming the connection works rather than seeing your own zones
   react).
2. Create a factory via the wizard with data source CSV or MQTT (whichever
   is available), then switch it over:
   ```bash
   curl -X PATCH "http://localhost:8000/api/factory/<factory_id>/data-source" \
     -H "Content-Type: application/json" \
     -d '{"data_source": "opcua"}'
   ```
3. Reconnect the live-factory websocket (reload the Live Command Center, or
   a throwaway script) and confirm ticks arrive sourced from the OPC-UA
   server's changing node values.

## A couple of things worth flagging back to your teammate, not blockers for testing

- No workforce roster CSV import for the wizard's own worker-count/badge
  prefix fields — those are still plain inputs, not persisted to
  `FactoryProfile` (unrelated to the badge-log upload above, which is a
  real event stream, not the wizard's aggregate fields).
- `backend/app/ingestion/README.md` is stale (still says MQTT/OPC-UA are
  unbuilt, though both are complete).
- No OPC-UA option in the wizard's Review step (backend supports it, UI
  doesn't expose it) — see the OPC-UA section above for the manual
  workaround.
