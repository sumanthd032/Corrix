# Corrix v2 — The "Judges Can't Look Away" Roadmap
### Turning a genuinely deep backend into a product that *shows* its depth

</div>

---

## 0. Read this first: an honest diagnosis

I went through the actual repo (`backend/app/*`, `frontend/src/*`, all five docs) before writing a single feature idea below. Here's the real state, not the pitch-deck version of it:

**What's actually strong (keep, don't touch, just surface better):**
- The backend is not a hackathon toy. `council/`, `mcp_servers/`, `memory/`, `regulatory/`, `evaluation/`, `emergency/`, `detection/`, `cv/`, `simulation/` are all real, separated modules with 382 tests. The five-agent LangGraph Council with genuinely siloed MCP tool access, the Neo4j GraphRAG over real OISD/Factories Act/DGMS text, the held-out-set memory loop, the Monte Carlo time-to-critical forecast — these are the kind of things most teams *claim* and few teams *have*. This is your actual moat.
- The frontend has the right primitives already installed: `deck.gl`, `@react-three/fiber` + `drei` + `postprocessing`, `framer-motion`, `three`. You already paid for a cinematic frontend; it's just not being spent on more than one screen.

**What's actually the problem — and it's simpler than "we need more features":**
- `frontend/src/App.tsx` is 40 lines. There is no router (`react-router-dom` isn't even in `package.json`). Every component — heatmap, Council panel, alert feed, regulatory chat, evaluation report, replay — is a panel or a modal bolted onto **one fixed layout**. A judge opens the link, sees one screen, and everything else is a click they may never make. Your screenshot *is* the whole app, and that's the exact thing you flagged.
- Nothing tells a judge what they're looking at or why it matters *before* they have to go find out themselves. There's no on-ramp — no 30-second "here's the problem, here's the gap, here's what we built" moment before the dense operational dashboard shows up.
- The genuinely hard, differentiated work (novelty detector, memory-loop held-out proof, calibration diagram, SWaT validation) is real but currently lives one modal-click deep, competing for attention with a live sensor dashboard. A judge skimming ten projects in ten minutes will see the dashboard and miss the proof.

**The fix is not "bolt on more AI features."** You already have enough AI. The fix is **information architecture**: turn one dense screen into a small, intentional, navigable product — a landing/story page, the live console you have now, and a small number of new destination pages that each do one job extremely well. That's what makes judges *feel* like they're looking at a product instead of a demo.

Everything below is scoped against what's already in your stack (no new heavy dependencies unless called out), tiered by effort vs. impact, and mapped to what hackathon judges actually score against.

---

## 1. Design philosophy for v2

Four rules govern every feature below. If a proposed feature doesn't clearly serve one of these, cut it — the existing build plan's own discipline ("look hard for what to cut") is worth keeping.

1. **A judge should understand the value in 30 seconds without touching anything.** That means a landing experience, not a login screen into a SCADA dashboard.
2. **A judge should be able to verify your hardest claims themselves, not just read them.** "Unrehearsed novelty detection" and "held-out generalization proof" are your strongest claims — they need a page where a skeptical judge can poke at them directly, not a modal they might not open.
3. **Every new screen is a destination, not a detour.** Real apps have pages: a home, a console, a library, a report. Five focused pages beat one page with fifteen modals stacked on it.
4. **Reuse the backend; don't multiply it.** Almost everything below is a new *view* over data your backend already computes (evaluation results, memory-loop exemplars, regulatory graph, scenario library) or a thin new endpoint over an existing module. Very little of this requires new AI subsystems.

---

## 2. New site structure (the single biggest change)

Install `react-router-dom` and turn the app from one screen into a real multi-page product:

```
/                      Landing — the story, the gap, the proof, the CTA
/console               Today's dashboard (Command Center) — refined, not rebuilt
/sandbox                "Break It Yourself" — judge-editable live compound-risk builder
/proof                 Evaluation & Trust Center — the hard numbers, judge-verifiable
/incidents             Case File Library — every scenario + real-world reference incidents
/knowledge             Regulatory Intelligence, full-page — graph + chat, not a drawer
/network               Fleet View — Corrix across a multi-plant map (scale story)
/developer             API & MCP Console — "Corrix is an MCP provider," provably
```

This alone — before a single new AI capability is added — changes the reviewer's experience from "I opened a link and saw a dashboard" to "I opened a product and explored it." That shift matters more to perceived quality than almost any individual feature.

---

## 3. Feature catalog

Each entry: **what it is → why it's worth building → what it reuses from your existing backend → what's genuinely new → UI/UX approach → wow-factor rating.**

---

### TIER 1 — Build these first. Highest score-per-hour, and they fix the exact problem you named.

#### 3.1 Landing Page (`/`) — the 30-second story

**What it is:** A short, cinematic, scroll-driven page a judge sees *before* the operational dashboard. Not a marketing page with buzzwords — a demonstration of the core insight, animated.

**The story it tells, in order:**
1. **The five silos.** Five small system icons (Gas sensors, SCADA, Permit system, CCTV, Shift roster) each glowing calm green, each individually "fine."
2. **The compound moment.** The same five icons animate into alignment — gas rising, a hot-work permit active, a shift changeover starting, a worker without a badge match — none red alone, but a connecting line draws between them and the *combination* turns red. This is the entire thesis of your project, shown, not explained in a paragraph.
3. **The number that matters.** Your real Evaluation Harness output, pulled live from the backend, not hardcoded: recall, false-negative rate, and lead time in minutes, animated counting up.
4. **One clear CTA:** "Enter the Command Center" → `/console`, plus a secondary "See how we prove it" → `/proof`.

**Reuses:** Your real evaluation numbers (`backend/app/evaluation`), your existing Framer Motion setup, your existing color/zone-state design tokens.

**New work:** One route, one component, a small `/api/evaluation/summary` endpoint if one doesn't already return a compact headline JSON (check `evaluation/` first — you likely already compute this for the report modal and just need a smaller summary shape).

**Wow factor:** ★★★★☆ — this is what makes the *first ten seconds* land. Judges decide a lot of their impression in that window.

---

#### 3.2 "Break It Yourself" Sandbox (`/sandbox`) — turn the Open Challenge into a self-serve moment

**What it is:** Your `docs/CORRIX_BUILD_PLAN.md` already describes an Open Challenge trigger that assembles a live, unscripted evidence combination from exposed parameters (zone, permit type, gas trend, timing) and runs it through the real Council. Right now that's something *you* trigger during a live demo. Turn it into something **the judge drives themselves**, on the public deployment, with no presenter needed.

**Why this is your single highest-leverage new feature:** the single most common failure mode in AI hackathons is the judge's unspoken thought, *"is this actually reasoning, or is this a slideshow with a script?"* A sandbox where the judge picks the zone, the permit type, the gas trajectory, and the timing themselves — and then watches five real agents actually reason over it and reach a verdict — answers that question better than any amount of description could. It's proof by direct manipulation, not narration.

**UI/UX:**
- A simple, constrained builder: dropdowns/sliders for zone, permit type, gas trend shape, and minutes-to-changeover — deliberately not free text, so every combination stays valid and demo-safe (your build plan already made this call for the Open Challenge; keep it).
- A "Run the Council" button that streams the same live agent-by-agent reasoning view your Council panel already renders, in real time, over the WebSocket you already have.
- At the end: the verdict, the confidence, `trigger_reason` shown honestly (`"novelty"` vs a named scenario), and a one-line explanation of *why* this combination wasn't one of the five pre-authored scenarios — building trust instead of hiding the mechanism.

**Reuses:** Existing Council WebSocket pipeline, existing scenario-engine parameterization, existing novelty detector, existing Council panel rendering.

**New work:** A constrained parameter-picker UI; a backend endpoint that accepts the small parameter set and feeds it into the existing scenario engine instead of a pre-authored YAML config (this is close to what the Open Challenge trigger already does — mostly a UI + exposure task, not new AI).

**Wow factor:** ★★★★★ — this is the feature most likely to make a judge say "wait, let me try something" and then be genuinely impressed when it holds up.

---

#### 3.3 Evaluation & Trust Center (`/proof`) — promote your best evidence out of a modal

**What it is:** `EvaluationReportModal.tsx` already exists and, per your build plan, should already contain real precision/recall/false-negative numbers, the calibration reliability diagram, and the SWaT validation comparison. Right now it's one click away from being missed entirely. Give it a real page, and add the one comparison that's currently the most under-sold thing in the whole project:

**The memory-loop before/after, front and center.** You already do the hard, correct thing — measuring the false-negative-rate improvement only on a held-out split the memory loop never saw. That is a genuinely rare, genuinely rigorous claim (most hackathon "self-improving AI" claims are either fabricated or measured on training data). It deserves its own hero chart: **two bars, "before memory loop" vs "after," held-out set only, with the sample size and split methodology stated directly on the page** — not buried in a methodology doc a judge won't read.

**Also promote to this page:**
- The calibration reliability diagram (stated confidence vs. empirical accuracy, plotted against the diagonal) — this single chart answers "can we trust the confidence numbers?" better than any text.
- The SWaT validation table, with a one-line explanation of what SWaT is and why comparing against a real industrial dataset (even offline) matters.
- A scenario-by-scenario breakdown table: S1–S5 + negative controls, precision/recall/lead-time per scenario, baseline (Step 3 rule-based) vs. full Council — so a judge can see the fusion layer's marginal contribution isolated from the cheap baseline, which is the actual point of the whole project.

**Reuses:** 100% existing evaluation data and existing modal's computation. This is almost entirely a presentation/promotion task, not new engineering.

**New work:** A route, a page layout, and (if not already true) making sure the evaluation numbers are computed from a real run and cached/served rather than needing to be regenerated live.

**Wow factor:** ★★★★☆ — for the subset of judges who actually check rigor (usually the technical judges on the panel), this page is what separates you from every team with a confident-sounding but unverified accuracy claim.

---

#### 3.4 Judge Mode — a guided, timed walkthrough overlay

**What it is:** A toggle (top-right, always visible) that launches a short, spotlighted tour across the whole app — landing → console → sandbox → proof — with a visible countdown ("Tour: ~90 seconds") and a highlighted spotlight over whatever's being explained, using a simple step-based overlay (a small custom implementation is enough; you don't need a new dependency — a fixed-position highlight ring + tooltip driven by Framer Motion, keyed off a step index in Zustand, does this without adding a library).

**Why this matters specifically for your situation:** you said it yourself — thousands of teams, twenty shortlisted, judges skimming fast. Most judges will not discover `/sandbox` or `/proof` on their own in the time they allot you. Judge Mode removes that risk entirely: it guarantees your best three features get seen, in order, in under two minutes, without requiring a live presenter. This is what makes the *public, unattended* deployment (which your README already says exists) actually work as an async judging tool.

**Reuses:** Zustand store, Framer Motion, existing components (it's an overlay, not new views).

**New work:** One small `JudgeModeOverlay` component and a step config array. This is genuinely a low-effort, extremely high-leverage build — probably the best effort-to-impact ratio of anything in this document.

**Wow factor:** ★★★★★ for async/unattended judging specifically; ★★★☆☆ if every project gets a live human demo. Given "thousands of teams," assume a lot of async/recorded review happens — build this.

---

### TIER 2 — Strong differentiators once Tier 1 is solid. Each is a real destination page, not a modal.

#### 3.5 Case File Library (`/incidents`) — depth and storytelling

**What it is:** A browsable library, one card per scenario (S1–S5, negative controls) plus — critically — two or three **real, cited, publicly documented Indian industrial incidents** (e.g., the kind of gas-leak/compound-failure event your own methodology doc already references, like the Visakhapatnam LG Polymers case your Council prompt cites as a validated pattern) presented as "what if Corrix had been watching." Each card opens into a case file: the evidence timeline, the Council's verdict, the counterfactual (legacy systems vs. Corrix), and — for the real incidents — a clearly labeled, honestly-scoped comparison to what was publicly reported, not a fabricated claim that Corrix would have prevented a specific real event.

**Why it's valuable:** it turns your five scenarios from "test fixtures" into a browsable proof library, and it's the single best place to make the human stakes of this problem tangible to a judge who isn't an industrial-safety expert. Numbers persuade some judges; a real, well-told incident narrative persuades others. Cover both.

**Reuses:** Your existing scenario data, existing Counterfactual Replay component (embed it per-case instead of only in the live console).

**New work:** A card-grid + detail-view UI, and the honest-labeling work of writing up 2–3 real reference incidents (this is research/writing, not code — worth the hour, given how much your existing docs already emphasize "radical honesty" as a differentiator).

**Wow factor:** ★★★★☆

---

#### 3.6 Full-Page Regulatory Intelligence + Knowledge Graph View (`/knowledge`)

**What it is:** Your Neo4j GraphRAG is one of the most technically substantial pieces of this project — a real graph of equipment/permit/zone/incident nodes over real OISD/Factories Act/DGMS text — and right now it's accessible through a chat drawer. Give it a full page with the chat on one side and a **live force-directed graph visualization** of the actual Neo4j nodes/edges on the other (a small D3 or React Flow force layout is enough — you don't need a new heavyweight graph library; a simple force-directed SVG using the physics you'd write by hand is genuinely fine for a hackathon-scale graph).

**Why it's valuable:** "GraphRAG" is a claim every team can type into a README. A rendered, explorable graph that a judge can click through — click a clause, see it light up connected incidents and equipment — is a claim that's *visibly, structurally true*, which is a much stronger signal than a chat answer with a citation number in it.

**Reuses:** Neo4j data already ingested (Step 5), existing chat retrieval logic.

**New work:** A `/api/regulatory/graph` endpoint returning a compact node/edge JSON, and a force-directed render component.

**Wow factor:** ★★★★☆

---

#### 3.7 Fleet View (`/network`) — the scale story

**What it is:** Your current demo is one plant, eight zones. Judges scoring "business viability / impact" want to see that this generalizes. A Fleet View shows a stylized map of India with 4–6 plant markers (can be illustrative/mock — label it honestly as a scale illustration, consistent with your project's existing honesty stance), each with a compact risk-state badge, aggregating into one "fleet risk posture" summary. Clicking a plant marker deep-links into `/console` for that (in the demo, still the one real modeled plant, others clearly marked as illustrative future sites).

**Why it's valuable:** this single page answers "does this only work for one demo plant?" before a judge has to ask it, and it's a very cheap way to visually communicate market size and product maturity.

**Reuses:** deck.gl (already installed), existing zone-state color system.

**New work:** A new map view at country scale instead of plant scale, and a small mock fleet-status dataset, clearly labeled as illustrative.

**Wow factor:** ★★★☆☆ (important for business-impact scoring, lower on raw "wow")

---

#### 3.8 Developer / MCP Console (`/developer`)

**What it is:** Your README's most technically distinctive but least *visible* claim is "Corrix as an MCP provider — the compound-risk state is exposed back out over MCP, so any external agent can query it directly." Right now that's a sentence. Build a small live console: a text box where a judge can send a real MCP tool call (or a simplified HTTP proxy to one) against your outward-facing server and see the actual JSON response, live, against the running demo instance.

**Why it's valuable:** for any judge who is themselves technical (very likely on an AI hackathon panel), this is the single fastest way to prove the "dual-role MCP" architecture claim is real rather than a slide bullet. Technical judges disproportionately reward things they can verify themselves in seconds.

**Reuses:** Your existing outward-facing MCP server (Step 9) — this is a UI wrapper around something you've already built and tested.

**New work:** A thin, safe proxy endpoint (read-only, rate-limited) and a minimal request/response console UI.

**Wow factor:** ★★★★☆ for technical judges specifically.

---

### TIER 3 — Polish and stretch. Do these only once Tier 1 and 2 are solid and you still have runway.

#### 3.9 AI Control-Room Narrator (voice)
A short, optional narrated voiceover (via Gemini's TTS or a browser-native `SpeechSynthesis` fallback if you want zero new dependencies) that reads out the Chair's verdict and reasoning summary aloud as it resolves — like a real control-room announcement. Toggleable, off by default. Adds sensory polish to the Sandbox and Console; skip if time is short, it's the most cuttable item here.

#### 3.10 Role-based views (Safety Officer / Plant Manager / Auditor)
A lightweight view-mode switch that re-weights the same console data for three personas: Safety Officer (operational, current-risk-first), Plant Manager (cost/impact-first, links to Fleet View), Auditor (compliance/audit-trail-first, links to `/knowledge`). Communicates product maturity without building three separate products — it's mostly a re-ordering/re-emphasis of panels you already have, gated behind a role toggle.

#### 3.11 Public "live viewers" presence indicator
On the deployed public instance, a small "N people viewing right now" indicator (a trivial WebSocket presence counter). Low effort, adds a "this is a real running system, not a recording" signal for async judges browsing the public URL.

#### 3.12 Mobile Companion strip
A genuinely responsive, minimal single-column view of the console (alert feed + evacuation route + one-tap acknowledge) for phone-width viewports — mainly valuable if you demo on a phone at any point, or want to show real-world field-deployment thinking. Lower priority than everything above.

---

## 4. What NOT to build (protect your remaining time)

Consistent with your own build plan's discipline: a full CesiumJS 3D digital-twin mode is still not worth it — you already have `@react-three/fiber` scenes and a deck.gl isometric view; polishing those is higher-value than adding a third rendering stack. Don't build user accounts/auth, a full CMS, or a generic "settings" page — none of that reads as differentiated to a judge, and all of it costs time better spent on Tier 1.

---

## 5. Judging-criteria mapping

| Feature | Innovation | Technical depth | Impact / viability | UX & presentation | Verifiability |
|---|---|---|---|---|---|
| 3.1 Landing Page | – | – | ● | ●●● | – |
| 3.2 Sandbox | ●●● | ●●● | ● | ●● | ●●● |
| 3.3 Evaluation & Trust Center | ● | ●●● | ● | ●● | ●●● |
| 3.4 Judge Mode | – | – | – | ●●● | ● |
| 3.5 Case File Library | ● | ● | ●● | ●● | ●● |
| 3.6 Knowledge Graph View | ●● | ●●● | – | ●●● | ●●● |
| 3.7 Fleet View | – | – | ●●● | ●● | – |
| 3.8 Developer/MCP Console | ●●● | ●●● | ● | ● | ●●● |

Use this table to decide where to spend remaining hours if the full list doesn't fit: **Sandbox, Judge Mode, and the Evaluation & Trust Center cover the most criteria columns for the least additional backend work**, since all three are primarily surfacing and interaction work over systems you've already built.

---

## 6. Suggested build order (assumes limited remaining time)

1. **Router + site shell** — `react-router-dom`, the eight routes as empty/placeholder pages, nav between them. Do this first; everything else depends on it existing.
2. **Judge Mode overlay** — cheapest build here, guarantees your best material gets seen even without it.
3. **Landing Page** — the 30-second story; do this before polishing anything deeper, since it's what every judge sees first.
4. **Evaluation & Trust Center** — mostly promoting existing modal content to a full page; low new-code, high credibility payoff.
5. **Sandbox** — highest total wow-per-hour, but needs the parameter-exposure backend work from your existing Open Challenge groundwork; budget the most time here.
6. **Case File Library, Knowledge Graph View, Fleet View, Developer Console** — in whatever order remaining time allows, using the criteria-mapping table above to break ties.

---

## 7. Definition of done for "ready to submit"

- [ ] The app has a real router; landing page is the default route, console is a distinct navigable page.
- [ ] Judge Mode runs start-to-finish in under two minutes without a presenter, touching landing, sandbox, and proof.
- [ ] `/sandbox` lets a judge assemble an evidence combination themselves and get a real, live Council verdict — tested with at least five different judge-chosen combinations, not just your five rehearsed scenarios.
- [ ] `/proof` shows the held-out memory-loop before/after numbers and the calibration diagram on first scroll, not behind a click.
- [ ] Every new page works from the public deployed URL, cold, with no local setup — since most judges will never run `npm install`.
- [ ] Nothing added here has weakened the honesty stance already baked into the project (label illustrative/mock content as such, especially in the Fleet View and Case File Library's real-incident comparisons).

