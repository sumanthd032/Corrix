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
  `backend/scripts/author_scenario_configs.py`. S5 lands in Step 8
  alongside the memory-loop feature it exists to demonstrate.
- `negative/` — 20 matched negative-control instances (`n01.yaml` ...
  `n20.yaml`), identical generators, `signals: {}` (no injected gas or
  compliance signal), cycling across all 8 zones, same 60/40
  population/held_out split. Background permit/shift/worker-location
  traffic still runs — a negative control is a normal, busy day, not an
  empty plant.

**Negative-control ground truth is a sentinel, not a real threshold.**
Both `compound_risk_window_start_minute` and `incident_threshold_minute`
are set to `duration_minutes` — the run never reaches a scripted incident,
so there is no real lead-time reference point. The Evaluation Harness
(Step 8) uses negative controls only to measure the false-positive rate,
never lead time.

The authoring script is a convenience for regenerating the library when
parameters change; the committed YAML files under `s1/`-`s4/` and
`negative/` are the actual source of truth (§16, Reproducibility) —
diffable, reviewable, and independently re-runnable without depending on
the script that produced them.
