# Corrix Demo Script

A five-minute live run-through, timed and verified against the running system, not a rehearsed-in-the-abstract plan. Every number below was pulled from a real run: the Evaluation Report screenshot in `docs/pitch_deck.html`, the Counterfactual Replay API, and three live end-to-end passes against the real backend, one with both LLM providers deliberately broken to verify the fallback beat, one covering the override, replay, evaluation report, and incident-report beats end to end, and one full Open Challenge draw. See `memory.md`'s Step 10 entries for exactly how and when each was verified.

Backend and frontend must both be running before starting (`uvicorn app.main:app --port 8000` from `backend/`, `npm run dev` from `frontend/`, which must serve on port 5173, the only origin the backend's CORS config allows). Confirm `GET /health` returns `{"status":"ok"}` and the dashboard shows `backend live` in the bottom-left corner before beginning.

## Timing at a glance

| Beat | Time | What happens |
|---|---|---|
| 1. Open | 0:00-0:30 | The corrected anchor incident, stated plainly |
| 2. The gap | 0:30-1:00 | Five systems, zero conversation |
| 3. Live convening (S1) | 1:00-2:15 | The Council convenes, resolves HIGH |
| 4. Safety Officer Override | 2:15-2:45 | A human note changes the outcome |
| 5. Counterfactual Replay | 2:45-3:15 | Real lead time, side by side |
| 6. Induced failure | 3:15-3:45 | Both providers down, the system stays honest |
| 7. Open Challenge | 3:45-4:20 | An unrehearsed combination, live |
| 8. Proof | 4:20-4:50 | The Evaluation Report, real numbers |
| 9. Close | 4:50-5:00 | Judging criteria, one line |

## 1. Open (0:00-0:30)

Say it straight, no slide needed yet, or hold on the pitch deck's hero slide:

> "On June 8, 2025, eight workers at Visakhapatnam Steel Plant died when entrapped gases inside a ladle of molten steel triggered a sudden explosion during a routine casting operation. A preliminary investigation by the Chief Inspector of Factories confirmed the cause. The signal existed. Nothing connected it to the fact that a lifting and casting operation was underway in that exact location, at that exact moment. That is the gap Corrix closes."

If asked why this isn't the incident described in the official brief: the brief describes a January 2025 coke-oven incident. Our own research traced the closest verified match to this June 2025 event instead, and we cite the version we could confirm. Full correction in `CORRIX_PROJECT.md` Section 3.

## 2. The gap (0:30-1:00)

Switch to the pitch deck's "Five systems, zero conversation" slide, or say it directly: gas sensors, SCADA, permit-to-work, CCTV, and shift logs are each individually competent and collectively blind to each other. Danger is the intersection none of them is watching.

## 3. Live convening, Scenario S1 (1:00-2:15)

Open the dashboard. Select **S1: Anchor (Ladle Bay)** from the scenario dropdown if it isn't already selected. Let it play live.

What to narrate while it runs:
- The heatmap is playing back real simulated sensor, permit, and shift data minute by minute, not a static mockup.
- When the Council convenes, point at the five-icon row and the signal animation running from each agent toward the Chair. Say what's actually happening: four agents are querying four different, deliberately siloed data sources at once, not one model with four personas.
- A real convening resolves in roughly 10-25 seconds against a healthy provider. Do not narrate through dead air. If it's running long, this is a natural place to explain the Chair's synthesis step rather than stall.
- When the verdict lands (HIGH, Zone 1), read one line from the explanation panel aloud: it names the specific compound pattern (active lifting permit, imminent shift changeover, worker presence), not a generic "elevated risk" message.
- Point at the heatmap: Zone 1 is now pulsing, a pale gas-dispersion haze is drifting across it, and the evacuation route (Z1 to Z3 to Z4) has drawn itself in. This is the risk-aware routing computed live from the current zone-risk snapshot, not a fixed line.

## 4. Safety Officer Override (2:15-2:45)

This is automatic in live mode, not something you click for. Every real convening pauses on its own, right after the four agents gather evidence and before the Chair synthesizes, for exactly **8 seconds** (verified directly against the running backend, `OVERRIDE_WINDOW_SECONDS` in `app/api/websocket.py`). The Council panel shows "Council deliberating. Add a note within the window to override, or it resolves automatically." the moment it opens. Watch for that line during Beat 3's convening, not after the verdict lands.

Eight seconds is not enough time to compose a sentence live. Have the note already typed somewhere you can paste it, for example:

> Permit P-2291 was already suspended manually 5 minutes ago by the Zone 1 supervisor, pending gas verification.

Paste it into the textarea and click **Resume Council** the moment the window opens. Verified live: the Chair's explanation and recommended action visibly incorporate the note (both "P-2291" and "suspend" appear in the synthesized verdict). If the window is missed, the graph resolves on its own with no note, which is also correct behavior, not a failure, so narrate it as "and if nobody steps in, it resolves on its own" rather than treating a miss as a mistake.

If asked how this is different from a UI-only pause: this is a real LangGraph interrupt (`interrupt_before=["chair"]`). The graph genuinely stops before the Chair node runs and resumes with the human note written into its checkpointed state, the same mechanism `test_override_pauses_before_chair_and_incorporates_the_note` in `backend/tests/test_council_graph.py` verifies directly.

The **Safety Officer Override** button in the top bar is a mock-mode convenience only: it retroactively reopens a note field on an already-reached verdict when there is no live backend to interrupt. Do not click it during a live run; it does nothing while `connectionMode` is `live` (`useCorrixStore.ts`'s `pauseForOverride` explicitly no-ops in that case, so the real pause has something to resume, not a control with nothing behind it).

## 5. Counterfactual Replay (2:45-3:15)

Open **Counterfactual Replay**. Scrub to the point where the two tracks diverge. Cite the real numbers, not an estimate:

- S2 (confined space): Corrix escalates at minute 17, the legacy z-score track at minute 22. Five minutes of real lead time.
- S3 (maintenance/gas): Corrix at minute 28, legacy at minute 33. Five minutes.
- S4 (hot work/gas): Corrix at minute 30, legacy at minute 31. One minute, a smaller but real gap.

If asked about S1 specifically: it shows no gap (both tracks escalate at minute 57), because its compliance-signal anomaly score and the permit conflict happen to cross their thresholds on the same tick for that scenario. Say this plainly if it comes up. It is disclosed in the Evaluation Report, not hidden.

## 6. Induced failure (3:15-3:45)

Tell the room what you're about to do before doing it:

> "Let's break it. I'm going to take down both AI providers and run a new scenario."

Restart the backend with both `GROQ_API_KEY` and `GEMINI_API_KEY` overridden to invalid values for this one process (shell environment, never the real `.env` file):

```
GROQ_API_KEY=invalid GEMINI_API_KEY=invalid uvicorn app.main:app --port 8000
```

Trigger a scenario. Verified behavior: the Council still convenes, still tries both providers with real retries, and after roughly 25-30 seconds resolves a labeled fallback verdict, confidence shown honestly as 0%, risk defaulted to HIGH, and an explanation that says outright: *"Automated Council synthesis was unavailable (both the primary and secondary inference providers failed), so this is a rule-based fallback verdict from the novelty trigger alone, not a synthesized Council judgment."* The recommended action tells a human to review manually rather than pretending the system still reasoned about it.

Say the point directly: this did not crash, and it did not fake a confident answer. Restart the backend with the real keys before the next beat.

## 7. Open Challenge (3:45-4:20)

Click **Open Challenge** (requires live mode; the button is disabled otherwise). One of five curated, pre-validated, but not pre-run combinations is drawn at random and streamed live; the drawn label appears next to the button (verified live: "Electrical isolation during a slow..." drew Zone Z3, resolved HIGH in 24.8 seconds).

Say what "unrehearsed" actually means here, before anyone asks: this is a curated-random draw, not raw improvisation with no safety net. Five valid, genuinely different combinations were generated and confirmed in advance to reach the Council via the novelty path, not the scripted rule/threshold path; which one runs tonight is decided live. When the verdict lands, read the Process Safety Engineer's line in the Council panel: it says the reading is a number of standard deviations from its calibrated baseline and calls the condition abnormal, not a named pattern like "gas readings above baseline, rising." That statistical framing, not a literal label in the UI, is the visible tell that this one escalated through the novelty path.

## 8. Proof (4:20-4:50)

Open **Evaluation Report**. Lead with the one number that matters most:

> "Held-out false-negative rate: 30% before the memory loop, 0% after, on scenarios the memory index never saw."

Then, in one breath, the honest complication: the full pipeline's overall recall (60%) trails the simple rule/threshold baseline (80%) on the current run, because the novelty path sometimes convenes the Council on evidence that's real but not yet dramatic enough for the Chair to call HIGH, and the memory loop's own false-positive rate rises from 20% to 50% on held-out negative controls alongside its false-negative gain. Both are on the same report. Nothing here is smoothed over.

Close this beat with the SWaT line: our simulator's noise-to-signal ratio (0.043-0.055) falls inside the range measured from three real SWaT industrial process tags (0.012-0.117), an external validation against a real dataset, not a self-graded claim.

## 9. Close (4:50-5:00)

One line, no slide needed:

> "Corrix detects compound risk, explains its reasoning, and improves from its own near-misses. Every number in this demo came from the system in front of you, not a slide."

## Backup material, not part of the timed run

- **Incident Report**: after any verdict, "Incident Report" downloads a real PDF with the evidence snapshot and, if fired, the ERO's delivery hash. Useful if a judge asks what a safety officer actually walks away with.
- **Regulatory Intelligence**: the chat drawer at the bottom answers questions grounded in the real OISD/Factories Act/DGMS text, not invented citations. Good for an ad hoc "does this system know the actual regulation" question.
- **Full Evaluation Report screenshot**: `docs/pitch_deck.html`'s backup slide, or the live modal itself, for anyone who wants every number rather than the headline ones above.
