# Corrix — Data Methodology
### Where every number in the system comes from, and exactly how it's generated

This document is a deep-dive companion to `CORRIX_PROJECT.md` Section 12. That section states the *policy* ("physics-informed simulation, externally validated, radically disclosed"). This document is the *engineering spec* — precise enough that a teammate could implement the simulator from this alone, and precise enough that we can defend every parameter choice if a technical judge asks "why that number?"

The organizing principle throughout: **use the most physically-appropriate model for each phenomenon, not one model forced onto everything.** One of the more interesting findings of the research pass behind this document is that our own anchor incident (Section 2) does *not* fit the "gas concentration rising over time" model the original playbook applied to everything — and getting that distinction right is itself a credibility signal.

This version incorporates a round of external validation review against the official problem statement (see `CORRIX_PROJECT.md` for the full validation notes). Three things changed as a result, each covered in its own section below: a worker-location data stream and evacuation-routing methodology were added (the brief names "worker location data" explicitly and we had no such stream); the memory-loop and forecasting methodology were tightened to survive an obvious "isn't this circular?" challenge; and DGMS was added to the regulatory corpus, honestly scoped rather than force-fit.

---

## 1. Data Taxonomy — What's Real, What's Simulated, What's Hybrid

| # | Data stream | Category | Generation method | Section |
|---|---|---|---|---|
| 1 | Atmospheric/gas sensor readings | **Simulated**, physics-informed, externally calibrated | Ornstein-Uhlenbeck stochastic process + scripted source term | §3 |
| 2 | Ladle/process moisture-compliance signal (S1 anchor) | **Simulated**, procedural-compliance model (not a gas sensor) | Degrading compliance-score process + discrete lapse probability | §4 |
| 3 | Permit-to-work records | **Simulated**, structured, schema-real | Rule-based generator against real permit taxonomies | §5 |
| 4 | Shift schedules | **Simulated**, structured | Deterministic roster generator | §6 |
| 5 | Plant layout / zone definitions + adjacency graph | **Simulated**, hazard classification real-world-grounded | Hand-authored JSON, cross-checked against OISD hazard-zone categories | §7 |
| 6 | Worker location / badge-ping stream | **Simulated**, zone-level granularity | Badge/turnstile-style event generator, feeds heatmap + evacuation routing | §8 |
| 7 | Site observation / CV detections | **Hybrid** — real inference, simulated correlation | YOLO26 fine-tuned on real open dataset, run on live/sample footage; badge-correlation layer is scripted against #6 | §9 |
| 8 | Historical near-miss / audit-log corpus (knowledge graph seed) | **Simulated/mocked**, structurally grounded in real regulatory clauses | Hand-authored corpus referencing real OISD/Factories Act/DGMS clause numbers | §10 |
| 9 | Regulatory RAG corpus (OISD, Factories Act 1948, DGMS circulars) | **Real** | Direct government-source PDFs, chunked and embedded as-is; DGMS included as honestly-scoped supplementary grounding (§11.3) | §11 |
| 10 | Scenario timelines (S1–S5 + negative controls) | **Simulated**, deterministically scripted, multi-seed | Config-driven scenario engine, fixed seeds, partitioned into memory-population/held-out subsets | §12 |
| 11 | Joint-evidence novelty score (catches the unscripted pattern) | **Simulated training data, real technique** | Density/reconstruction model fit to negative-control joint-evidence vectors; not scenario-matching | §13 |
| 12 | Evaluation ground truth + confidence calibration | **Simulated but rule-defined**, not hand-waved | Precise, code-level definition of "incident threshold crossing"; calibration checked against actual outcomes | §14 |
| 13 | External validation reference | **Real dataset**, used for calibration only | SWaT (Secure Water Treatment) public ICS testbed dataset | §15 |

Nothing in this list is presented to judges as more real than it is. Rows 1, 2, 4, 5, 6, 8, 10, 11 are synthetic (or trained on synthetic data) and labeled as such everywhere they appear in the UI. Rows 7 (partially), 9, and 13 are real and are the load-bearing evidence for "this isn't just a random-number generator."

---

## 2. Why One Simulation Model Doesn't Fit All Scenarios

The original playbook's model — an Ornstein-Uhlenbeck gas-concentration process with a scripted "leak" source term — is a good, physically reasonable model for **atmospheric gas accumulation in a zone**. It is the correct model for three of our five scenarios (S2, S3, S4 — confined space entry, maintenance/gas co-occurrence, hot work near elevated gas — the same three the brief names verbatim). It is **not** the correct model for our anchor scenario, S1.

Our research into the real, verified anchor incident (Section 3 of `CORRIX_PROJECT.md`) found that ladle explosions from "entrapped gases" are a distinct, well-documented steelmaking hazard mode:

- Molten steel contacting **moisture** (condensation, damp scrap, a cooling-line leak, an incompletely dried/preheated ladle) instantaneously vaporizes that moisture, expanding it roughly **1,600×** in volume, and can additionally trigger an oxidation-reduction reaction generating hydrogen gas — producing a sudden, violent pressure release.
- This is a **threshold/trigger event driven by a procedural lapse** (a moisture-elimination or ladle-drying step skipped or rushed), not a slowly rising ambient concentration a fixed-point gas detector would trend toward over minutes. There usually isn't a "gas ppm creeping up" curve to plot for this specific failure mode — the hazard is latent (moisture present) until the lift/pour operation itself triggers it.

Forcing this into the same "rising gas ppm" chart as our other scenarios would have been the easy, lazy choice — and a domain expert on the judging panel would likely catch it as physically wrong. Instead, S1 is modeled with a different signal type entirely: a **procedural-compliance degradation process** (Section 4) representing the real risk driver (was the moisture/dryness check actually done, under real time pressure), combined with the same permit and shift-timing evidence used elsewhere, plus the worker-location stream (Section 8) confirming who was actually in the ladle's swing path. This is more work than reusing one model everywhere, and it's a deliberate technical-rigor signal worth stating plainly in the pitch: *"we didn't use the same fake-gas-sensor model for every scenario — we used the model that actually matches the documented failure mechanism for each one."*

---

## 3. Atmospheric Gas Sensor Simulation (S2, S3, S4)

### 3.1 The stochastic model

Gas concentration in a zone is modeled as a mean-reverting Ornstein-Uhlenbeck (OU) process — a baseline equilibrium representing normal ventilation/dispersion, perturbed by continuous stochastic noise, with an injectable deterministic source term for scripted events:

```
dC(t) = k · (C_baseline − C(t)) dt  +  S(t) dt  +  σ dW(t)

C(t)         gas concentration at time t, in the sensor's native unit (ppm or %LEL)
k            mean-reversion / ventilation-dissipation rate constant (1/min)
C_baseline   the zone's equilibrium concentration under normal ventilation
S(t)         source term: 0 under normal conditions; positive during a scripted
             leak/accumulation event (Section 3.3)
σ            noise intensity (calibrated against SWaT, Section 15)
dW(t)        a standard Wiener process increment (Brownian motion)
```

### 3.2 Discretization for implementation (Euler–Maruyama)

The simulator ticks on a fixed interval `Δt` (default: 5 seconds, matching a realistic industrial gas-detector polling cadence — faster than typical 1–5 minute HMI refresh but coarse enough to be computationally cheap over a multi-hour scenario replay):

```python
def step(C_t, k, C_baseline, S_t, sigma, dt, rng):
    drift = k * (C_baseline - C_t) * dt
    source = S_t * dt
    noise = sigma * sqrt(dt) * rng.normal(0, 1)
    return max(0.0, C_t + drift + source + noise)  # concentration can't go negative
```

Every scenario run is seeded (`numpy.random.default_rng(seed)`) so a given scenario+seed pair always reproduces the same noise path — critical for live-demo reliability and for the Evaluation Harness to be re-runnable and diffable. Note that this same `step()` function is reused, unmodified, as the engine behind the Monte Carlo Time-to-Critical forecaster (Section 3.6) — one implementation serves both the offline simulator and the live forecaster, which is both less code and a cleaner "we didn't build two different models that could quietly diverge" story.

### 3.3 Source term `S(t)` — how a "leak" is scripted

Rather than an arbitrary spike, each scenario's source term follows one of three physically-motivated shapes, chosen per scenario to match the documented pattern it's modeling:

| Shape | Formula | Used for |
|---|---|---|
| **Ramp** (steady accumulation) | `S(t) = a · min(1, (t − t0) / t_rise)` for `t ≥ t0` | S3 — gradual gas accumulation co-occurring with maintenance work |
| **Step + decay** (sudden release, slow dissipation) | `S(t) = a · e^{−(t − t0)/τ}` for `t ≥ t0` | S4 — a discrete release event near active hot work |
| **Ramp with plateau** (accumulation that stabilizes at an elevated, sub-critical level until a second factor pushes it over) | Ramp to a target level `C_plateau`, held, then a secondary smaller ramp triggered by the compound factor (e.g., ventilation reduction during shift changeover) | S2 — confined space entry during "abnormal but not yet alarming" process conditions, where the *compounding* factor (personnel entry closing off ventilation, or changeover-driven inattention) is what pushes it critical, not the gas alone |

`a`, `t0`, `t_rise`, `τ`, and `C_plateau` are all scenario-config parameters (Section 12), not hardcoded — this is what makes the scenario library extensible rather than three hardcoded demo scripts.

### 3.4 Parameter calibration — where the numbers come from

Baseline ranges and alarm thresholds are not invented; they're set from real, citable occupational exposure and confined-space monitoring standards, displayed on-screen in the UI (not hidden in code) for auditability:

| Gas / parameter | Normal / safe range | Alert threshold | Source |
|---|---|---|---|
| Oxygen (O₂) | 20.9% (ambient) | Alarm outside **19.5%–23.5%** | OSHA confined-space atmospheric testing standard |
| Carbon monoxide (CO) | Near 0 ppm, zone-dependent baseline | PEL **50 ppm** (8-hr TWA) | OSHA PEL |
| Hydrogen sulfide (H₂S) | Near 0 ppm | PEL **20 ppm** TWA / STEL **50 ppm** (15-min) / IDLH **100 ppm** | OSHA |
| Combustible gas (LEL%) | 0% | Alarm at **≥10% LEL** | OSHA confined-space standard |
| Coke-oven-gas-adjacent zones (Z2, Z3 — Section 7) | Composition reference: ~H₂ 55–60%, CH₄ 23–25%, CO 5–6%, CO₂ ~2%, N₂ 6–9% | Flammability + CO toxicity both apply — flammable-gas LEL alarm is the binding constraint given the hydrogen/methane fraction | Coke oven gas composition literature; hazard summary corroborated by EPA coke-oven-emissions documentation |

For each zone, `C_baseline` is drawn from a narrow band around the "normal" value in the table above (e.g., CO baseline 5–12 ppm in a maintenance bay with typically-present low-level combustion sources, versus 0–3 ppm in a control room), and the alert/critical thresholds used by the anomaly scorer and the Safety Council are the PEL/IDLH/LEL values above — so when the UI shows "34.2 ppm, threshold 50 ppm PEL," that threshold is a real regulatory number, not an arbitrary round figure chosen to make the demo trigger nicely.

### 3.5 Testing-order fidelity (a small but real detail)

OSHA's own required confined-space testing order — oxygen first, then flammables (LEL%), then toxics (CO/H₂S PELs) — is mirrored in the *order* the Process Safety Engineer agent reports evidence for confined-space scenarios (S2), rather than reporting all three simultaneously as an undifferentiated blob. It's a small detail, but it's exactly the kind of detail that reads as "built by people who read the actual standard" rather than "built by people who guessed at gas safety."

### 3.6 New: Monte Carlo forecasting for Time-to-Critical

`CORRIX_PROJECT.md` §6.4 surfaces a live per-zone forecast rather than a bare "risk is HIGH" label. The method, precisely:

1. At forecast time, take the **currently observed** state `C_t` (or `Q_t` for the compliance signal, Section 4) as the starting point — not a scripted value, the real current simulated reading.
2. Roll forward **N independent stochastic paths** (default N = 200) using the same `step()` function from Section 3.2, the same calibrated `(k, C_baseline, σ)` for that zone, but fresh random draws per path, out to a bounded horizon (default 60 minutes).
3. Record, per path, the first minute (if any) each path crosses the zone's configured HIGH/CRITICAL threshold.
4. Report the **median** crossing time, the **interquartile range** (25th–75th percentile) as the displayed band, and the **fraction of paths that crossed at all** within the horizon as an implicit escalation probability.
5. Recompute on a fixed interval (e.g., every 15–30 seconds) as new real observations move the starting point — the forecast should visibly tighten or widen as the live scenario progresses, not stay static.

Displayed as: *"Zone 1 — 68% chance of CRITICAL within 15–22 min at current trend."* This is a Monte Carlo rollout, not a closed-form analytical solution — deliberately, because a full analytical OU first-passage-time derivation is mathematically intricate and fragile to implement correctly under time pressure, while reusing the exact simulator code we already built and validated (Section 15) is cheap, robust, and produces the same kind of answer. If asked "why not the closed-form solution," the honest answer is exactly that trade-off — not that we didn't know one exists.

---

## 4. Procedural-Compliance Signal (S1 — the Anchor Scenario)

### 4.1 What this models

S1 represents the verified anchor incident's real mechanism (Section 2): a moisture/dryness verification step for ladle preparation that is time-pressured, not a rising ambient gas reading. We model this as a **compliance-degradation process** — a bounded score in `[0, 1]` representing "how thoroughly was the pre-lift moisture/dryness check actually performed," which is a plausible real output of a digital permit/checklist system (squarely inside the brief's own "permit-to-work logs" data category, not a fabricated sensor type).

```
Q(t) = Q_baseline − p_lapse(t) · degradation_step

Q_baseline        starting compliance quality, drawn from a realistic high value
                   (most checks, most of the time, are done properly — this must
                   not be a system that cries wolf on every routine lift)
p_lapse(t)         probability of a procedural shortcut being taken at time t,
                   which we deliberately couple to shift-changeover proximity
                   (time pressure near a handoff is a documented human-factors
                   risk driver) and to workload/queue-length context
degradation_step   the compliance-score penalty applied when a lapse is sampled
```

`Q(t)` crossing below a configured floor (e.g., `0.6`) is **not**, by itself, an alarm — exactly like a single elevated gas reading elsewhere in the system, a lower compliance score alone is common and not inherently critical. It only becomes the Process Safety Engineer agent's flagged evidence when combined with:

- an **active lifting/casting permit** in the same zone (Permit Control Officer evidence),
- **shift-changeover proximity** (Shift Operations evidence — and note this is the same causal factor driving `p_lapse(t)` up in the first place, which is intentional: the model captures that changeover pressure both *causes* the lapse and *independently* elevates operational risk, which is a more sophisticated compound-risk structure than three unrelated signals happening to coincide), and
- a **worker-location/CV-confirmed personnel presence** in the ladle's lift/swing path (Site Safety Observer evidence, Section 9).

None of the four alone crosses a critical threshold. The combination is the compound risk — which is the exact structural property the whole product is built to detect, now applied to the scenario it's most directly grounded in. Consistent with the agent-silo design (`CORRIX_PROJECT.md` §6.1), the Process Safety Engineer agent only has access to `Q(t)` via the Sensor Stream MCP server — it cannot itself see the permit or worker-location data that make the combination dangerous; only the Chair can.

### 4.2 Why this is more defensible, not less

A judge who has done their own homework on the anchor incident (plausible, given it's a real, searchable event) and sees us plotting a "gas ppm" line for a ladle-moisture explosion would reasonably conclude we didn't actually understand the incident we're citing. Modeling the real driver — a procedural/human-factors signal — instead is a small amount of extra engineering effort that closes that exact gap.

---

## 5. Permit-to-Work Data Generation

Permits are generated as structured records against a fixed taxonomy of permit types drawn from standard Indian industrial permit-to-work practice (hot work, cold work, confined space entry, lifting/heavy-equipment operation, electrical isolation):

```json
{
  "permit_id": "P-2291",
  "type": "lifting_operation",
  "zone_id": "Z1",
  "issued_by": "Shift Supervisor A. Rao",
  "start_time": "2026-07-19T10:00:00Z",
  "end_time": "2026-07-19T14:00:00Z",
  "status": "active",
  "linked_checklist_id": "CHK-0410"
}
```

Generation logic:
- A background rate of routine, non-conflicting permits is generated continuously across all zones (so the demo plant always looks operationally busy, not artificially quiet except during "the" scenario — this matters for realism and for the negative-control runs, Section 12.4).
- Each scenario config specifies which permit(s) to inject, in which zone, on what timing offset relative to the scripted event, and (for S1) which `linked_checklist_id` ties the permit to the compliance signal in Section 4.
- Permit-conflict rules (e.g., hot-work permit + high-hazard zone + elevated anomaly score) are a separate, fully deterministic rule table — not LLM-generated — consistent with the "core safety logic should be rule-based and auditable" principle.

---

## 6. Shift Schedule Generation

Shift rosters are generated deterministically for a standard three-shift industrial pattern (e.g., 06:00–14:00, 14:00–22:00, 22:00–06:00), each with a configurable changeover window (default 15 minutes) during which handoff-related risk factors (Section 4) are elevated. Each shift record lists the zones it covers, so the Shift Operations agent can answer "is a changeover imminent *in this zone specifically*" rather than a plant-wide constant.

---

## 7. Plant Layout, Zone Definitions & Adjacency Graph

Eight zones, hand-authored as static JSON, modeled loosely on an integrated steel plant for narrative coherence with the anchor incident — spanning both the coke-oven/gas-processing side (for S2–S4) and the steel-melting/ladle side (for S1):

| Zone | Name | Hazard class | Primary role |
|---|---|---|---|
| Z1 | SMS-2 Ladle Bay / Casting Floor | High (molten metal, moisture/entrapped-gas risk) | Anchor scenario S1 |
| Z2 | Gas Collection Main | High (atmospheric gas accumulation) | S3, S4 |
| Z3 | Maintenance Bay | Medium (hot work common) | S3, S4 |
| Z4 | Control Room | Low | Baseline/negative-control traffic; evacuation assembly point |
| Z5 | Raw Material / Scrap Yard | Low–Medium (moisture source — damp scrap is a documented contributing factor to Z1's risk, per Section 2) | Cross-zone risk narrative |
| Z6 | Quenching Tower / Slag Pit | Medium (steam/thermal, moisture) | Baseline/negative-control traffic |
| Z7 | Gas Collection Vault (confined space) | High (confined space + gas) | S2 |
| Z8 | Perimeter / Walkway | Low | Baseline/negative-control traffic; evacuation assembly point |

Hazard classifications are cross-checked qualitatively against OISD's own zone/area hazard-classification language (high/medium/low hazard areas, confined-space designation) rather than assigned arbitrarily — each zone's `hazard_class` field is the same value the Permit Control Officer's rule table keys off, so there's one source of truth, not a UI label disconnected from the logic.

**Adjacency graph (new):** the zone layout also defines which zones share a walkable boundary or corridor, as a simple undirected edge list — e.g., `Z1–Z3`, `Z1–Z6`, `Z3–Z5`, `Z2–Z7`, `Z4–Z8`, and so on, authored alongside the coordinate data. This is the only new data this adds; it feeds two consumers directly: the evacuation-routing algorithm (Section 8.2) and, incidentally, nothing else — it's a small, static addition, not a new subsystem.

---

## 8. Worker Location & Evacuation Routing (New)

### 8.1 Why this exists

The official brief's Geospatial Safety Heatmap sub-direction explicitly names *"integrating worker location data"* as part of the expected feature — a data type the original design didn't model as a first-class stream. This section closes that gap, and does it in a way that's cheap and, more importantly, realistic: real industrial badge/RTLS systems overwhelmingly report **zone-level transitions** (a badge reader or turnstile logs "worker X entered Zone Y"), not continuous GPS coordinates — so modeling it at zone granularity isn't a shortcut, it's the more accurate choice.

### 8.2 Data generation

A small simulated workforce roster (15–30 active badge IDs per shift, matching the shift generator in Section 6) emits periodic **badge-ping events**:

```json
{
  "badge_id": "W-0142",
  "zone_id": "Z1",
  "timestamp": "2026-07-19T10:31:00Z",
  "event_type": "zone_entry"
}
```

Ping cadence: a background rate (e.g., every 30–60 seconds while stationary) plus event-driven pings on every zone entry/exit, generated consistently with each scenario's scripted permit/shift context — a worker with an active lifting-operation permit in Z1 shows up as present in Z1 during that window, not randomly elsewhere.

This stream feeds three consumers:

1. **The heatmap** — worker markers rendered at their current zone (with small random jitter within the zone's polygon so multiple workers in one zone are visually distinguishable).
2. **The CV badge-scan correlation** (Section 9) — a CV-detected person in a zone is checked against this stream; "no matching badge scan" means no badge-ping exists for that zone in the matching time window, not an arbitrary flag.
3. **Zone occupancy on a CRITICAL verdict** — when the Emergency Response Orchestrator fires, it can answer "who is actually in the affected zone right now, by badge ID" immediately, because it's just a query against this stream rather than a separate headcount system. This is a small, concrete way of making good on the brief's own framing for the Emergency Response Orchestrator — reducing "the critical first 10 minutes from chaos to coordinated response" — with something more substantive than a colored map.

### 8.3 Evacuation routing methodology

On a HIGH/CRITICAL verdict in a zone, a **Dijkstra shortest-path search** runs over the zone-adjacency graph (Section 7) from the affected zone to the nearest designated safe assembly point (Z4 Control Room or Z8 Perimeter/Walkway):

- Base edge weight: a fixed traversal cost between adjacent zones (proportional to physical distance if known, otherwise a uniform cost — precision here doesn't matter much for an 8-zone graph).
- **Risk-adjusted weight:** any zone currently in an elevated (HIGH/CRITICAL) risk state gets its edges' weight multiplied by a large penalty factor, so the search actively routes around other unsafe zones rather than just finding the geometrically shortest path.
- Output: an ordered list of zones forming the recommended path, rendered as a highlighted route on the heatmap and attached to the ERO's fired notification and the Incident Report.

Dijkstra, not A* or anything more elaborate, because the graph is small (8 nodes) — the correct engineering choice here is the simplest algorithm that solves the actual problem, not the most impressive-sounding one.

---

## 9. Computer Vision Data — the Real/Simulated Split, Precisely

This is the one subsystem where "how the data is taken" has a genuinely real answer, and it's worth being precise about exactly where the real part ends and the simulated part begins, since blurring that line is the single easiest way to lose credibility on stage.

**Real:**
- **Model:** YOLO26 (or YOLOv11 if inference latency on demo hardware matters more than the marginal accuracy gain), fine-tuned on the **Ultralytics Construction-PPE** dataset — a real, open, license-compatible dataset (1,416 labeled images, 11 classes: helmets, gloves, vests, boots, goggles, and person/no-PPE variants).
- **Input:** a live webcam feed or a short pre-recorded sample clip, run through actual forward-pass inference at demo time — not a pre-baked "detection log" played back on a timer.
- **Output:** genuine bounding-box detections with class labels and confidence scores, timestamped as they're produced.

**Simulated (and labeled as such in the UI, every time):**
- The **correlation** between a detection and plant context — e.g., "this person-detection occurred in Zone 1, with no matching badge-ping in the worker-location stream (Section 8) for that zone/time window." There is no real camera-to-zone geofencing or real badge system in this build; that correlation is a scripted lookup against the simulated worker-location stream, not an arbitrary flag invented on the spot.

```json
{
  "event_id": "CV-0042",
  "zone_id": "Z1",
  "timestamp": "2026-07-19T10:31:10Z",
  "detection": "person",
  "confidence": 0.91,
  "source": "real_inference",
  "correlation": "no matching badge-ping in Zone 1",
  "correlation_source": "simulated"
}
```

The `source` / `correlation_source` field split in the schema itself is deliberate — it's not just a UI label, the honesty is encoded in the data structure so it can't accidentally get lost or misrepresented as the system evolves.

---

## 10. Historical Near-Miss / Audit-Log Corpus (Knowledge Graph Seed Data)

A small, hand-authored corpus of illustrative near-miss and inspection-log entries, explicitly labeled as mocked/illustrative wherever surfaced. It is not random filler text: each entry references a **real** clause structure from the OISD/Factories Act/DGMS corpus (Section 11) — e.g., an audit entry flags `missing_required_signature` against a specific `required_checklist_ref` like `OISD-STD-XXX §4.2` — so that when the Regulatory Intelligence layer (`CORRIX_PROJECT.md` §8, Pillar 3) surfaces one of these entries — whether through pattern-lookup or a compliance-check query — the regulatory citation it points to is real and checkable, even though the specific mocked incident record is not.

---

## 11. Regulatory RAG Corpus — Real, Sourced Documents

### 11.1 Primary sources

No generation involved here — these are downloaded as-is from government sources and chunked for retrieval:

- OISD guideline document: `oisd.gov.in` (direct PDF, logged in `CORRIX_PROJECT.md` Section 17)
- Factories Act, 1948, full text: `indiacode.nic.in` and mirrored at `dgms.gov.in`
- Model Rules under the Factories Act, 1948: `indiacode.nic.in`

### 11.2 Chunking and embedding approach

Documents are split on structural boundaries (section/clause numbers) rather than fixed-token windows where possible, so a retrieved chunk is a coherent clause a human could cite directly, and the RAG assistant's citation always points to a real section number a judge could look up live. Embeddings and retrieval are served from the same Neo4j AuraDB instance used for the knowledge graph, so there is exactly one place "what does the regulation actually say" data lives — no risk of the KG and the RAG corpus drifting out of sync because they're two different databases.

### 11.3 DGMS — added, and honestly scoped

The problem statement's own Evaluation Focus line names three regulatory frameworks: OISD, the Factories Act, and DGMS. The original corpus covered only the first two — a real gap against the judges' own rubric, not a stylistic omission. DGMS (Directorate General of Mines Safety) statutorily governs mining operations under the Mines Act, 1952, which is not, strictly, the downstream steel-processing operations (coke ovens, ladle bays, maintenance shops) our layout models. Rather than force an ill-fitting citation, DGMS's general safety circulars are added as **supplementary** grounding — on the honest basis that integrated steel plants of this kind typically run captive raw-material/mining supply chains (loosely reflected in Zone 5) that do fall under DGMS jurisdiction, and because the rubric explicitly asks for it. The specific circular(s) to ingest are selected and verified against `dgms.gov.in` at build time — this document intentionally does not cite a specific DGMS document URL that hasn't been individually verified, consistent with the same real-source-only discipline applied to OISD and the Factories Act.

---

## 12. The Scenario Engine — How S1–S5 and Negative Controls Are Actually Triggered

### 12.1 Config-driven, not hardcoded

Every scenario is a versioned config file (e.g. `scenarios/s1_anchor.yaml`), not a hardcoded script buried in application logic — this is what makes "deterministic scenario mode" (needed for live-demo reliability) compatible with "extensible scenario library" (needed for the five-scenario generalization claim) at the same time.

```yaml
scenario_id: S1
name: "Anchor case — ladle moisture/entrapped-gas compound risk"
seed: 20260714
memory_split: population   # population | held_out — see 12.5
duration_minutes: 90
zone: Z1
signals:
  compliance:
    model: procedural_compliance
    Q_baseline: 0.92
    degradation_step: 0.35
    lapse_coupling: shift_changeover_proximity
  permit:
    type: lifting_operation
    inject_at_minute: 20
    linked_checklist_id: CHK-0410
  shift:
    changeover_at_minute: 68
  worker_location:
    badge_id: W-0142
    zone_entry_at_minute: 55
  cv_event:
    inject_at_minute: 55
    detection: person
ground_truth:
  compound_risk_window_start_minute: 60
  incident_threshold_minute: 82
```

### 12.2 Deterministic seeding

Each scenario's `seed` fixes every stochastic draw (gas-noise paths, lapse-probability sampling, negative-control noise) so a given scenario+seed reproduces bit-for-bit identically on every run — this is what lets us re-run the Evaluation Harness before/after the self-improving memory loop and attribute any change in the metrics to the memory loop itself, not to random variation between runs.

### 12.3 Positive scenarios

S1 (Section 4), S2/S3/S4 (Section 3), and one addition beyond the brief's own examples:
- **S5 — silent sensor drift (near-miss):** an OU-process run (Section 3) with a source term deliberately parameterized to *stay below* the hard HIGH/CRITICAL threshold for its entire duration, but whose shape matches a labeled historical near-miss pattern stored in the knowledge graph (Section 10) — this scenario is unsolvable by threshold logic alone by construction, and exists specifically to demonstrate the retrieval-based memory loop actually changing the outcome.

A sixth scripted scenario ("multi-zone cascade," reasoning across two zones at once) was cut during review — it didn't demonstrate a mechanism the other five don't already cover, and the Joint-Evidence Novelty Detector (Section 13) is a stronger, more general answer to "does this generalize beyond a fixed scenario count" than one more authored script would have been. Five scripted scenario types, not six, is the deliberate choice.

### 12.4 Negative controls

Generated using the identical zone/permit/shift/worker-location generators with `S(t) = 0` for the entire run (no injected event) and `p_lapse(t)` left at its normal, low background rate — in matched volume to the positive scenario count, so the Evaluation Harness's false-positive rate is computed on a fair, non-cherry-picked sample rather than a token handful of "quiet" runs.

### 12.5 New: train/held-out partitioning for the self-improving memory loop

`CORRIX_PROJECT.md` §6.3 claims the memory loop measurably improves the false-negative rate. That claim is only defensible if the improvement is measured on cases the loop never saw — otherwise "the system got better" collapses into "the system memorized its own test," which is an obvious and fair challenge from any judge who thinks about it for ten seconds.

**Mechanics:** each of S1–S5 (and the negative controls) is instantiated with **multiple seed variants**, not one fixed seed — e.g., five seeds per scenario type. Every instance's config carries a `memory_split` field (Section 12.1): a fixed majority (e.g., three of five seeds per scenario) are designated `population` — their Evaluation Harness misses are eligible to be stored as retrievable exemplars — and the remainder (e.g., two of five) are designated `held_out` and are **never** used to populate the memory index, only to measure against it.

The before/after comparison (`CORRIX_PROJECT.md` §6.3) is computed and reported **only on the `held_out` subset.** If the false-negative rate improves there, that's a real generalization result. If it doesn't, that's the honest result to report instead — which is the same radical-honesty posture applied to a claim that's easy to get wrong.

---

## 13. Joint-Evidence Novelty Detection — Catching the Unscripted Pattern (New)

### 13.1 Why this exists

`CORRIX_PROJECT.md` §6.7 names the vulnerability plainly: everything described in Sections 3–12 detects compound risk by matching against five known, labeled scenario types. A pattern that isn't S1–S5 — a combination nobody scripted, including the people who built this system — would slip through a purely rule/scenario-matching pipeline. This section describes the second, independent detection path that closes that gap.

### 13.2 Training data — reusing what already exists

The Evaluation Harness's fairness requirement (§12.4) already forces the generation of matched-volume negative-control runs: normal operating days, no injected event, across every zone. That's incidentally exactly the training set a novelty detector needs — a reference distribution of what a *normal* joint plant state looks like. No new data generation is required; this is a second use of data the system produces anyway.

For each timestep across the `memory_split: population` negative-control runs, assemble a **joint evidence vector**: the zone's gas/compliance signal, active permit state (encoded, e.g., one-hot by permit type × hazard class), shift/changeover proximity, and worker-location/CV occupancy state — concatenated into one fixed-length vector per zone per timestep. This is the "what does the whole picture normally look like together" representation, as opposed to the per-signal thresholds the fast-path scorer (§3) uses.

### 13.3 The model

Fit a lightweight novelty/density model to the joint evidence vectors from Section 13.2. In order of preference (simplest first — use the simplest one that actually separates known-positive scenarios from negative controls in a quick offline check, don't reach for more complexity than that):

1. **Mahalanobis distance** against a fitted multivariate Gaussian (or a small Gaussian mixture) over the joint vectors — cheap, fast, easy to explain, and often sufficient at this data scale.
2. **A small autoencoder**, if the joint-evidence relationships turn out to be too non-linear for (1) — reconstruction error becomes the novelty score.

Either way, the output is a single **novelty score** per zone per timestep, calibrated (via the same negative-control set) so a threshold can be set for "unusual enough to warrant review."

### 13.4 Wiring it into the Council

The existing event-trigger path (§3, rule/threshold crossing) is unchanged. A **second, independent trigger** convenes the Council whenever the novelty score exceeds its calibrated threshold — including when *no* individual rule or z-score threshold has fired. This is the essential property: it's not a restatement of the first trigger, it's a parallel path built to catch what the first one structurally can't.

A novelty-triggered verdict carries `trigger_reason: "novelty"` in the verdict schema (`CORRIX_PROJECT.md` §6.2), and the Chair's explanation is written to reflect that honestly — *"this combination doesn't match a known compound-risk pattern; its joint statistical profile is unusual enough to warrant review"* — rather than force-fitting it into a description of S1–S5.

### 13.5 The Open Challenge — assembling unscripted combinations on demand

Because the scenario engine (§12.1) is config-driven rather than five fixed scripts, an arbitrary valid combination can be assembled from a small set of exposed parameters (zone, permit type, gas/compliance trend, timing offset) without needing a new scenario file authored in advance. For the live demo device described in `CORRIX_PROJECT.md` §6.7, a set of such combinations — deliberately distinct from S1–S5 — is pre-generated and validated against the novelty detector ahead of time (confirming they *do* trigger correctly), and one is drawn live during the demo. This keeps the live moment genuinely unrehearsed for that specific run while not depending on a system with zero validated safety net.

---

## 14. Ground Truth & Confidence Calibration for the Evaluation Harness

### 14.1 Defining "incident threshold" precisely

"Prediction lead time before incident threshold" is only a meaningful, defensible number if "incident threshold" is defined in code, not eyeballed after the fact. Each scenario config's `ground_truth` block (Section 12.1) specifies:

- `compound_risk_window_start_minute` — the earliest simulated minute at which the *combination* of evidence genuinely constitutes a compound risk (i.e., the earliest point a correct system could reasonably flag HIGH). This is the reference point the memory loop and the Time-to-Critical forecaster are evaluated against for "how early did we catch it."
- `incident_threshold_minute` — the simulated minute representing the scripted point of no return — the reference point "lead time" is measured back from.

The Evaluation Harness computes lead time as `incident_threshold_minute − (minute the pipeline under test first crossed HIGH/CRITICAL)`, for both the single-sensor baseline and the full Council pipeline, across every positive scenario — a positive lead time means the system caught it in advance; a run that never crosses HIGH/CRITICAL before `incident_threshold_minute` is scored as a false negative, not silently excluded.

### 14.2 New: confidence calibration reporting

The Chair's verdict schema includes a `confidence` value (e.g., `0.87`). Left unchecked, that's just a number the model emits — nothing verifies it means anything. Since the Evaluation Harness already has ground truth for every run, calibration is nearly free to add:

1. Bucket every verdict emitted across the (held-out, per Section 12.5) scenario library by its stated confidence into bins (e.g., 0.5–0.6, 0.6–0.7, … 0.9–1.0).
2. For each bin, compute the empirical accuracy — the fraction of verdicts in that bin that matched ground truth.
3. Plot predicted confidence (x-axis) against empirical accuracy (y-axis) — a well-calibrated system sits close to the diagonal.

This renders as a small reliability diagram in the Evaluation Report tab, alongside precision/recall/lead-time. If the Council turns out to be systematically overconfident (a common LLM failure mode), that's a genuinely useful, honest finding to disclose rather than hide — and disclosing it is more credible than a suspiciously perfect-looking confidence score would be anyway.

---

## 15. External Validation Against SWaT — Methodology

### 15.1 What SWaT is, and what we use it for

SWaT (Secure Water Treatment) is a real, publicly available dataset from a physical industrial control system testbed (iTrust, Singapore University of Technology and Design): 51 sensor/actuator tags sampled at 1 Hz, spanning 7 days of normal operation and 4 days of injected-attack anomalies. We are **not** claiming Corrix's plant is a water treatment plant, and we don't use SWaT's attack-labeled segments at all. We use only its **normal-operation segment**, and only for one narrow purpose: checking that our synthetic sensor noise "feels like" real industrial sensor noise rather than looking hand-tuned to make our own demo work.

### 15.2 The actual procedure

1. From SWaT's 7-day normal-operation window, select a handful of continuous-valued process tags (e.g., level/flow/pressure indicators) as reference signals.
2. Fit a discrete AR(1)/OU-equivalent model to each reference tag via least-squares (`C_{t+1} = C_t + k'(baseline − C_t) + noise`), recovering an *implied* mean-reversion rate and residual noise variance from **real** sensor behavior.
3. Compare the **shape** of that fitted noise (variance relative to signal range, and residual distribution skew/kurtosis) against our own simulator's configured `σ` and OU parameters (Section 3.4), scaled appropriately since the physical units differ.
4. Report the comparison as a simple table/plot in the Evaluation Report tab and the deck: "our synthetic noise-to-signal ratio falls within X% of the range observed in a real industrial control system's normal operation," not a bare "our sim runs, trust us."

### 15.3 What this validates, and what it doesn't

This validates that our simulator's **statistical texture** — how noisy, how mean-reverting, how bursty real industrial sensor data tends to look — isn't fabricated from nothing. It does **not** validate that our specific gas-concentration values are what a real coke-oven or ladle-bay sensor would read (no public dataset can answer that for this domain, which is exactly the constraint every team on this problem statement shares). Stating this distinction plainly, unprompted, is part of the same radical-honesty posture as the rest of this document.

---

## 16. Reproducibility

- Every scenario is a versioned config file (Section 12.1), not inline code — diffable, reviewable, and independently re-runnable by any teammate.
- Every stochastic process is explicitly seeded; the seed is part of the scenario config, not an environment default.
- Multi-seed variants and the `memory_split` designation (Section 12.5) are part of the same config, not a separate bookkeeping system that could drift out of sync.
- The novelty detector's training data (Section 13.2) is the same versioned negative-control runs as everything else — no separate, undocumented dataset.
- The Evaluation Harness's output (the precision/recall/lead-time/false-negative/calibration table referenced throughout `CORRIX_PROJECT.md`) is a build artifact generated by running the same scenario library through the same pipeline — it is regenerable on demand, not a number typed once into a slide.
- The SWaT-fitting procedure (Section 15.2) is itself a small, versioned script, not a one-off notebook whose output we transcribed and then discarded — so the calibration claim can be reproduced or challenged by a judge with access to the same public dataset.

---

## 17. Sources

- [Entrapped Gases Caused Visakhapatnam Steel Plant Accident: Experts — ETV Bharat](https://www.etvbharat.com/en/state/entrapped-gases-identified-as-cause-of-visakhapatnam-steel-plant-accident-experts-preliminary-assessment-enn26061003994)
- [Explosions involving water and molten metal — ARIA (French Ministry for Sustainable Development)](https://www.aria.developpement-durable.gouv.fr/wp-content/uploads/2013/08/FK_imp2009-water-metal.pdf)
- [Molten Metal Safety in Steel Plants — Oxmaint](https://oxmaint.com/industries/steel-plant/molten-metal-safety-steel-plants-hot-metal-slag-handling)
- [Acceptable and Dangerous Gas Levels in Confined Spaces — Industrial Scientific](https://www.indsci.com/en/blog/acceptable-and-dangerous-gas-levels-in-confined-spaces)
- [OSHA Confined Space: Critical Air Monitoring Compliance — Envigilance](https://envigilance.com/compliance/osha-confined-space/)
- [The Permissible Gas Levels In Confined Spaces — Rescue Solutions](https://rescuesolutionsllc.com/the-permissible-gas-levels-in-confined-spaces/)
- [The Influence of Hydrogen Concentration on the Hazards Associated with the Use of Coke Oven Gas — MDPI Energies](https://www.mdpi.com/1996-1073/17/19/4804)
- [Coke Oven Gas Generation and Usage — IspatGuru](https://www.ispatguru.com/coke-oven-gas-generation-and-usage/)
- [Coke Oven Emissions — Hazard Summary — U.S. EPA](https://www.epa.gov/sites/default/files/2016-09/documents/coke-oven-emissions.pdf)
- [SWaT Dataset: Secure Water Treatment System — iTrust SUTD, via Kaggle](https://www.kaggle.com/datasets/vishala28/swat-dataset-secure-water-treatment-system)
- [Construction-PPE Detection Dataset — Ultralytics Docs](https://docs.ultralytics.com/datasets/detect/construction-ppe)
- DGMS (Directorate General of Mines Safety) — `dgms.gov.in` — specific circular(s) to be selected and verified at build time (Section 11.3).
- Regulatory source documents — see `CORRIX_PROJECT.md` Section 17 for direct OISD/Factories Act URLs.
