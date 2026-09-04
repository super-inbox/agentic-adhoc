# Design Agent v0 evaluation

This directory contains three complementary evaluation layers:

| evaluator | input | purpose |
|---|---|---|
| `routing_eval.py` | `tool_intent_queries.jsonl` | text-only production matcher recall baseline |
| `reference_asset_eval.py` | `queries.jsonl` + `assets/reference-pack-v0.1/` | real-pixel binding, integrity, provenance, privacy, and alpha validation |
| `runtime_eval.py` | `runtime_cases.example.jsonl` | single-turn HTTP black-box route, trace, visual verdict, retry, and artifact scoring |

## Runtime and structured-editing research

- [`runtime-verification/2026-08-26-canva-magic-layers-agent-json.md`](runtime-verification/2026-08-26-canva-magic-layers-agent-json.md)
  summarizes Canva Magic Layers, the public MCP/Apps SDK editing boundaries, transaction-based
  JSON operations, and a platform-neutral Design IR proposal mapped to Curify's
  `design_document.json`, `change_set.json`, `verification.json`, and `trajectory.jsonl` contract.
- [`runtime-verification/2026-08-22-runtime-skills.md`](runtime-verification/2026-08-22-runtime-skills.md)
  records the deployed `design-vote` and `tryon-poster` runtime verification.

## Published live experiment

[`experiments/curify-web-live-2026-08-12/`](experiments/curify-web-live-2026-08-12/)
publishes the sanitized 21-case live evaluation of the deployed Curify Design Agent. It includes
the agent-neutral Dataset, reference-pack-v0.2 manifest, per-case runtime/score output, aggregate
metrics, Braintrust provenance, and a Chinese diagnostic analysis. Headline result: 16 complete,
5 partial, 0 program errors, 36.2% weighted design score on 16 judgeable outputs, 12.2%
hard-gated total over all 21 cases, and 0/21 benchmark pass.

The snapshot contains no API keys, browser session state, signed download URLs, local absolute
paths, or user account identity. Exact source/output pixels and full nested source traces remain as
access-controlled Braintrust attachments.

## Codex execution baselines (2026-09-02)

- [`experiments/curify-vs-codex-21q-2026-08-16/baselines/codex-single-turn-v1/`](experiments/curify-vs-codex-21q-2026-08-16/baselines/codex-single-turn-v1/)
  freezes the completed Codex-only 21-case multimodal baseline. All 21 cases have an independent
  `gemini-2.5-pro / judge-v2.1` result; first-attempt completion remains 20/21 because `TIQ-098`
  required one explicitly labelled posthoc completion run. Weighted design mean is 0.609, the
  hard-gated mean is 0.414, and 8/21 cases pass all gates at the 0.70 threshold.
- [`experiments/codex-v02-2026-08-21/`](experiments/codex-v02-2026-08-21/)
  contains the completed Brief Bank v0.2 run and scoring snapshot: 32/32 context conditions over
  24 episodes, with condition-aware artifact-grounded judging. The observable-only diagnostic is
  0.874; the full-rubric condition-macro interval is 0.659–0.909 because workflow completion and
  recovery are not independently observable under the current protocol.

## Codex planner/ranking baselines (2026-09-02)

- [`experiments/codex-planner-routing-118-2026-09-02/`](experiments/codex-planner-routing-118-2026-09-02/)
  runs all 118 consolidated queries as independent, schema-constrained, planner-only Codex cases.
  It completed 118/118 on the first attempt with no tool calls. On the 100-query layer it reached
  98.0% intent any-hit and 100.0% candidate any-hit, but 0.0% correct abstention on the 23 known
  catalog gaps; exact top-level agent routing was 16/18.
- [`experiments/codex-99designs-evaluate-rank-2026-09-02/`](experiments/codex-99designs-evaluate-rank-2026-09-02/)
  builds and runs the blinded 61-contest / 243-pair 99designs preference fixture. Codex recovered
  the observed winner at top-1 in 14/61 contests (23.0%) and ranked it above a visible alternative
  in 153/243 pairs (63.0%); excluding same-designer pairs gives 131/206 (63.6%). Rights remain
  uncleared, so this experiment is local-only and must not be used for training or redistribution.

## Published cross-Agent canaries

- [`experiments/canva-vs-curify-canary-2026-08-14/`](experiments/canva-vs-curify-canary-2026-08-14/)
  records four manually observed Canva cases and preserves downloaded outputs plus UI evidence.
- [`experiments/codex-vs-curify-canary-2026-08-14/`](experiments/codex-vs-curify-canary-2026-08-14/)
  records two isolated Codex CLI cases, frozen comparison artifacts, and JSONL execution traces.

Both are small canaries rather than overall Agent rankings. Their independent Gemini judge-v2 run
was blocked by the source project's monthly spending cap, so their published conclusions are
limited to deterministic checks and evidence-based manual comparison.

## Consolidated multimodal queries

`queries.jsonl` has 118 rows:

- 100 `routing_benchmark` rows;
- 18 `agent_route` rows;
- 9 routing rows where an image is strictly required;
- 12 agent-route rows where `has_reference=true`.

All 21 strictly image-bearing rows now include explicit `input_assets`. The 30 bindings resolve to
18 project-owned PNG fixtures through `assets/reference-pack-v0.1/manifest.jsonl`. Ordering defines
the primary image first, followed by supporting product/style references.

## Validate the reference pack

```bash
cd design-agent-v0
python3 eval/reference_asset_eval.py
```

The check covers query binding completeness, manifest resolution, path containment, SHA-256, byte
size, image decoding, dimensions/mode, privacy flags, and transparent-corner integrity. Current
baseline: 21/21 queries and 18/18 unique assets pass.

## Load images in a runner

```python
from reference_assets import load_queries, resolve_assets

row = next(item for item in load_queries() if item["id"] == "AR-007")
inputs = resolve_assets(row)
person_bytes = inputs[0]["path"].read_bytes()
garment_bytes = inputs[1]["path"].read_bytes()
```

The production matcher endpoint is still text-only. This pack supplies the real inputs for live
Vision intent extraction, multi-image slot filling, executor task-success scoring, missing-image
abstention, and mismatched-image rejection.

## Workflow briefs (`briefs.jsonl`)

11 multi-step **workflow briefs** — a whole design job with a known-good step
sequence, which is what evaluation and distillation need and what the query
layers do not provide (spec §7f). Built by `build_briefs.py` from the 18
documented real jobs in
`visual-search-adhoc/docs/daily_report/8.8/workflow-research-5-domains/candidates/`.

| field | meaning |
|---|---|
| `brief` | the job stated as a user would state it |
| `expected_steps` | ordered controlled-vocabulary step slugs (`intake_brief`, `research`, `explore_concepts`, `dieline`, `production_file`, `deliver`, …) |
| `expected_step_count` | expected plan length |
| `provenance` | case file, org, source URL |

Coverage: brand 3 · packaging 2 · merch 2 · education 2 · product 2 · step counts 3–7.

Only **process facts** are taken from the sources (domain, ordered stage labels,
provenance); each `brief` is written fresh from those facts, so no source prose
is reproduced.

```bash
python3 eval/build_briefs.py eval/briefs.jsonl   # re-extract
```

## L3/L4 episode benchmark (`brief_bank/`)

[`brief_bank/briefs.v0.2.jsonl`](brief_bank/briefs.v0.2.jsonl) extends the process-only workflow
briefs into 24 executable Design Agent episodes and 32 matched run conditions. Each episode
specifies inputs, constraints, available tools, observable checkpoints, simulated client feedback,
project state, reference roles, human decisions, intermediate/final deliverables, verification,
hard gates, and a weighted rubric. The original
[`briefs.v0.1.jsonl`](brief_bank/briefs.v0.1.jsonl) remains frozen as the business-task baseline.

| axis | v0.2 coverage |
|---|---|
| capability | L3 Tool Agent: 8 · L4 Workflow Agent: 16 |
| content | 8 benchmark categories × 3 cases |
| primary intent | generate: 5 · edit: 5 · evaluate-rank: 5 · export: 5 · adapt: 4 |
| messy work | 9/24 cases (37.5%) |
| designer-feedback probes | 8 multi-turn/state-recovery · 6 creative-exploration · 6 structured-editing |
| context conditions | 24 reference-grounded · 4 zero-shot · 4 personalized = 32 runs |

The directory also contains versioned schemas, a deterministic v0.1→v0.2 builder,
semantic/fixture validation, unit tests, and a generated 32-row first-turn projection. That
projection intentionally excludes future feedback and is a routing/input smoke test only; it
cannot establish L4 workflow success without later turns, checkpoint evidence, state continuity,
verification, and final deliverables. `trajectory.jsonl` denotes observable actions and artifacts,
not private chain-of-thought.

```bash
python3 eval/brief_bank/build_v02.py
python3 eval/brief_bank/validate_briefs.py
python3 eval/brief_bank/export_initial_queries.py \
  --output eval/brief_bank/initial_queries.v0.2.jsonl
python3 -m unittest discover -s eval/brief_bank -p 'test_*.py'
```

## ZCOOL workflow briefs (`zcool_briefs/`)

7 further workflow briefs (2026-08-19) covering the four brief classes the spec
flagged as under-represented — packaging/SKU 3, brand visual exploration 2, brand
campaign 1, concept-to-production 1. Same schema as `briefs.jsonl`; IDs continue
the series (`BRF-PACK-03…06`, `BRF-BRAND-04…06`), so one loader reads both.

Two deliberate differences: `evidence: "external_portfolio"` rather than
`external_case_study`, and an empty `expected_steps` — portfolio pages publish
outcomes, not stage sequences, and guessing one would be fabrication. Usable as
**inputs and gold references**, not as step-sequence ground truth.

See `zcool_briefs/README.md`.

**Deliberately not added:** the 680-row `vir_v2` visual-intent set. It is a
content-generation benchmark (MBTI charts, travel guides, science posters) —
only ~69 of its rows touch brand/packaging/merch — so folding it in would grow a
generic image benchmark rather than the workflow set. It remains useful for
*routing* recall in its own repo.

**Still missing: trajectories.** A brief says what the steps should be; a
trajectory records what actually happened, including which option a human chose
and why. Those only exist once real jobs are run and captured
(`curify-frontend/lib/agent/trajectory.ts`).
