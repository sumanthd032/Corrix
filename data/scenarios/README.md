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
template. The real authored S1-S4 configs (with multiple seed variants each)
are Step 2 work; S5 lands in Step 8 alongside the memory-loop feature it
exists to demonstrate. Negative-control (`N1..Nk`) configs use the identical
generators with `signals` left empty/zeroed.
