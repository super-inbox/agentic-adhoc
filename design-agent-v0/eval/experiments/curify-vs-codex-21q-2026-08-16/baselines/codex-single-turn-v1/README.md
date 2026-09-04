# Codex 21q single-turn baseline v1

Frozen at `2026-09-04T01:09:31.432932Z`. Baseline SHA-256: `3f201c2e37bcbfb5a57b4fe329dcd54f90fb9124032ea04616c18e55073461e2`.

This is the completed Codex-only quality baseline for the 21 multimodal, single-user-turn cases. The
original first-attempt ledger is preserved separately from the selected quality runs.

## Coverage

| Item | Result |
|---|---:|
| Dataset | 21/21 |
| Original first-attempt completion | 20/21 |
| Selected completed quality runs | 21/21 |
| Independent judge-v2.1 | 21/21 |
| Posthoc generation reruns | 1 (`TIQ-098`) |
| Raw judge attempts | 23 (21 selected + 2 malformed) |

`TIQ-098` originally timed out at 15 minutes after producing 20 images. Its explicitly labelled
completion rerun finished in 11.82 minutes with 22
artifacts. Therefore first-attempt reliability remains 20/21; only the quality baseline is 21/21.

## Headline scores

| Metric | Score |
|---|---:|
| Weighted design mean | 0.609 |
| Gated benchmark total mean | 0.414 |
| Case passes (all gates and score ≥ 0.70) | 8/21 |
| Median latency | 151.27 s |

## Dimensions

| Dimension | n | Mean (0–1) |
|---|---:|---:|
| `brief_adherence` | 21 | 0.438 |
| `visual_quality` | 21 | 0.714 |
| `creative_diversity` | 6 | 0.400 |
| `brand_consistency` | 2 | 1.000 |
| `refinement_ability` | 8 | 0.375 |
| `cross_asset_consistency` | 6 | 0.500 |
| `production_readiness` | 21 | 0.762 |
| `efficiency` | 21 | 0.816 |


## Hard gates

| Gate | Passed |
|---|---:|
| `all_inputs_consumed` | 21/21 |
| `artifact_contract` | 13/21 |
| `completed` | 21/21 |
| `judge_coverage` | 21/21 |
| `judge_no_fatal_issues` | 19/21 |
| `production_gate` | 15/21 |


The largest observed gap is brief adherence, followed by task-specific diversity/refinement. The
gated total is additionally limited by artifact-contract (13/21) and production-gate (15/21)
failures. These are measured separately from visual quality.

## Frozen files

- `results.jsonl`: exactly 21 portable, deduplicated canonical records.
- `judge-v2.1.results.jsonl`: ordered raw judge ledger, including malformed attempts.
- `summary.json`: machine-readable aggregate.
- `manifest.json`: dataset, scripts, selected runs, artifacts and hashes.

This baseline uses one stochastic generation per selected task and one successful independent
judgment per task. Gemini judgments are not human ground truth. Historical Flash scores and the
older incomplete Pro runs are excluded. Do not compare their means directly with this snapshot.
AR-012's selected judgment used the same rubric and prompt with a schema-constrained response after
two malformed responses omitted one required dimension; both failed attempts remain auditable.
Host-specific home and temporary paths are redacted from the committed publication copy.
