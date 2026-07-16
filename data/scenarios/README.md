# Scenario configs

Every scenario is a versioned YAML file, validated against
`backend.app.schemas.ScenarioConfig`, per `docs/CORRIX_DATA_METHODOLOGY.md`
§12.1. Nothing here is hardcoded application logic — config in, simulator
parameters out.

Fields:

- `scenario_id`, `name` — identifiers.
- `seed` — fixes every stochastic draw for the run; same scenario + seed
  reproduces bit-for-bit identically.
- `memory_split` — `population` or `held_out` (§12.5). A fixed majority of
  seed variants per scenario type are `population` (their Evaluation Harness
  misses are eligible to populate the self-improving memory loop's exemplar
  index); the remainder are `held_out` and never contribute exemplars, only
  measured against them.
- `duration_minutes`, `zone` — run length and the primary zone the scenario
  is scripted against.
- `signals` — at most one of `compliance` (S1 only, §4) or `gas` (S2-S4,
  §3), plus optional `permit`, `shift`, `worker_location`, and `cv_event`
  injection blocks.
- `ground_truth` — `compound_risk_window_start_minute` and
  `incident_threshold_minute` (§14.1), the code-level definitions the
  Evaluation Harness measures lead time and false-negative rate against.

`s1_anchor.example.yaml` transcribes the doc's own S1 example verbatim, as a
template — kept for reference, not one of the real authored runs.

## Directory layout

- `s1/`, `s2/`, `s3/`, `s4/` — 5 seed variants each (`seed_<seed>.yaml`),
  3 `population` / 2 `held_out`, authored by
  `backend/scripts/author_scenario_configs.py`.
- `s5/` — silent sensor drift (near-miss), authored in Step 8 alongside
  the self-improving memory loop it exists to demonstrate (§12.3). A slow
  OU-process ramp in Z2, deliberately parameterized to never cross the
  Step 3 rule/threshold trigger (neither the z-score HIGH/CRITICAL bar
  nor a permit conflict) — seeds are not simply sequential here, since a
  real gap was found while authoring it: background permits exist in
  every zone regardless of scenario, and the OU process's own noise
  alone occasionally spikes into CAUTION range by chance, so a
  high-hazard zone's permit-conflict rule can fire on pure noise with no
  injected event at all. S5's 5 seeds were selected by running the real
  Step 3 trigger end-to-end and keeping only ones verified never to fire
  (see `author_s5`'s docstring in the authoring script for the full
  account, including the one sequential seed that didn't pass).
- `negative/` — 25 matched negative-control instances (`n01.yaml` ...
  `n25.yaml`, extended from 20 when S5 was added, to keep the harness's
  false-positive measurement fair against the real positive-scenario
  count), identical generators, `signals: {}` (no injected gas or
  compliance signal), cycling across all 8 zones, same 60/40
  population/held_out split. Background permit/shift/worker-location
  traffic still runs — a negative control is a normal, busy day, not an
  empty plant. One seed (originally assigned to `n23`) hit the same
  background-permit/noise-spike overlap S5 had to route around and was
  overridden with a verified-safe replacement (`author_negative_
  controls`'s docstring has the details) — negative controls carry a
  hard, already-tested guarantee (`test_negative_controls_never_trigger`)
  that they never trigger, so this one couldn't be left as "real signal."

**Negative-control and S5 ground truth are sentinels, not real
thresholds.** For negative controls, both `compound_risk_window_start_
minute` and `incident_threshold_minute` are set to `duration_minutes` —
the run never reaches a scripted incident. For S5, `incident_threshold_
minute` is likewise set to `duration_minutes` (a near-miss has no real
point of no return), but `compound_risk_window_start_minute` is a real,
earlier minute — the point in the drift a vigilant system should have
been able to recognize the pattern, used to score lead time once the
memory loop's retrieval-similarity trigger (Step 8) catches a held-out
S5 seed after population-split misses have been stored as exemplars.
The Evaluation Harness (Step 8) uses negative controls only to measure
the false-positive rate, never lead time.

The authoring script is a convenience for regenerating the library when
parameters change; the committed YAML files under `s1/`-`s4/` and
`negative/` are the actual source of truth (§16, Reproducibility) —
diffable, reviewable, and independently re-runnable without depending on
the script that produced them.
