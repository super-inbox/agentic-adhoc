# Design Agent v0 evaluation

This directory contains three complementary evaluation layers:

| evaluator | input | purpose |
|---|---|---|
| `routing_eval.py` | `tool_intent_queries.jsonl` | text-only production matcher recall baseline |
| `reference_asset_eval.py` | `queries.jsonl` + `assets/reference-pack-v0.1/` | real-pixel binding, integrity, provenance, privacy, and alpha validation |
| `runtime_eval.py` | `runtime_cases.example.jsonl` | single-turn HTTP black-box route, trace, visual verdict, retry, and artifact scoring |

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

**Deliberately not added:** the 680-row `vir_v2` visual-intent set. It is a
content-generation benchmark (MBTI charts, travel guides, science posters) —
only ~69 of its rows touch brand/packaging/merch — so folding it in would grow a
generic image benchmark rather than the workflow set. It remains useful for
*routing* recall in its own repo.

**Still missing: trajectories.** A brief says what the steps should be; a
trajectory records what actually happened, including which option a human chose
and why. Those only exist once real jobs are run and captured
(`curify-frontend/lib/agent/trajectory.ts`).
