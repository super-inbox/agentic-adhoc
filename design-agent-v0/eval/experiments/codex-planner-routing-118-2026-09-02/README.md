# Codex planner-only routing — 118-query baseline

This experiment evaluates Codex as a **planner/router only** over the frozen
`eval/queries.jsonl` dataset. It never asks the candidate to generate or edit a
design and it does not pass the gold labels into the prompt.

The source file contains two different benchmark layers, so results are
reported separately rather than collapsed into one misleading accuracy:

- `routing_benchmark` (100): content-intent routing plus ranked Curify template
  candidates;
- `agent_route` (18): exact top-level route selection (`design_vote`,
  `virtual_tryon`, `factory_export`, and so on).

Reference presence and asset roles are provided as planner metadata. Pixels are
not supplied because this is a planner-only baseline, matching the existing
21-query routing probe rather than the multimodal execution benchmark.

## Run

```bash
python3 scripts/run_codex_planner.py --all --allow-model-usage --workers 3
python3 scripts/score.py
```

The runner uses one fresh, ephemeral Codex invocation per query in an empty,
read-only workspace. It requests schema-constrained JSON and records raw JSONL
events, stderr, timing, usage, tool-call count, and the final response. Reruns
skip already completed cases unless `--rerun` is passed.

## Metrics

For the 100-query layer:

- intent any-hit, exact set, macro precision/recall/F1;
- template top-1, any-hit, and macro recall on the 77 cases with labeled
  candidates;
- correct abstention on the 23 coverage-gap cases with no labeled template;
- strict joint pass = intent hit **and** template hit/appropriate abstention.

For the 18-query layer:

- exact route accuracy and per-route confusion.

First-attempt completion is preserved separately from the selected valid run so
retries cannot silently inflate reliability.

## Frozen identity

`results/freeze-manifest.json` pins the candidate configuration, dataset,
output schema, runner, scorer, selected results, summary, and aggregate prompt
set by SHA-256. `results/prompt-manifest.jsonl` additionally records the exact
hash and byte size of every selected case prompt. Codex CLI exposes the model
identifier but not a model-weights digest, so the manifest records that field
as unavailable instead of implying weight-level reproducibility.
