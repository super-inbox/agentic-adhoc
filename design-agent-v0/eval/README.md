# Design Agent v0 evaluation

This directory contains three complementary evaluation layers:

| evaluator | input | purpose |
|---|---|---|
| `routing_eval.py` | `tool_intent_queries.jsonl` | text-only production matcher recall baseline |
| `reference_asset_eval.py` | `queries.jsonl` + `assets/reference-pack-v0.1/` | real-pixel binding, integrity, provenance, privacy, and alpha validation |
| `runtime_eval.py` | `runtime_cases.example.jsonl` | single-turn HTTP black-box route, trace, visual verdict, retry, and artifact scoring |

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
