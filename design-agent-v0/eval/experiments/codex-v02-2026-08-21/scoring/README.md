# Scoring the Codex Brief Bank v0.2 experiment

Final snapshot: 32/32 unique conditions have a primary completed run. All
scorers select one latest primary completed attempt per `brief_id × condition`;
the duplicate successful CFR-003 attempt is not double-counted.

## Canonical outputs

| File | Role |
|---|---|
| `rubric-v02-partial.jsonl` | Deterministic artifact-contract and efficiency results |
| `selfverification-audit.jsonl` | Independent evidence-path and required-artifact audit |
| `rubric-v02-judged-v3.jsonl` | Canonical condition-aware, artifact-grounded model judge |
| `tool-execution-judged-v2.jsonl` | L3 tool-execution cross-check; not double-counted |
| `summary-v02.json` | Machine-readable aggregate and per-condition scores |
| `../RESULTS.md` | Human-readable result report |
| `JUDGE_VALIDATION.md` | Positive review, counterfactual controls, and rejected graders |

`rubric-v02-judged-v2.jsonl` is retained as a negative historical experiment
and explicitly excluded from canonical totals. The invalid temporary
tool-execution v1 result file was discarded after its controls failed.

## Final coverage and scores

| Dimension | Coverage | Mean | Status |
|---|---:|---:|---|
| `artifact_contract` | 32/32 | 1.000 / 1 | deterministic |
| `efficiency` | 32/32 | 1.000 / 1 | deterministic |
| `brief_understanding` | 32/32 | 3.469 / 5 | judge-v3 |
| `tool_execution` | 8/8 L3 | 4.500 / 5 | judge-v3; artifact-only cross-check agrees |
| `revision_fidelity` | 24/24 L4 conditions | 4.875 / 5 | judge-v3 |
| `cross_asset_consistency` | 24/24 L4 conditions | 3.500 / 5 | judge-v3 |
| `workflow_completion` | official 0/24 | proxy 1.000 / 1 | version-count proxy only |
| `recovery` | 0/32 | — | protocol-unobservable |

Observable rubric weight averages **75.0%** per condition. The honest
condition-macro full-rubric interval is **0.659–0.909**; the observable-only
normalized diagnostic is **0.874**. Each of the 24 business briefs equal-weighted
gives **0.686–0.919**. These are intervals because unobservable dimensions are
not silently assigned zero or full credit.

## Deterministic self-verification audit

- Required structured artifacts present: **32/32**.
- Runs whose cited evidence paths all resolve: **20/32**.
- Evidence citations checked: **593**.
- Named checks emitted: **302**.
- Checks with no `id`: **86**.
- Contract binding: **unmeasurable**. Candidate check IDs and the brief's
  verification vocabulary are not protocol-bound.

The candidate's own `verification.json` status is never accepted as its score.
The audit checks file existence independently and keeps self-report separate.

## Why judge-v3 is canonical

The earlier judge-v2 was resumable and violation-first, but later audit found
two structural errors: it graded zero-shot arms against the base query and did
not receive source images or a complete evaluator inventory. This caused false
violations, including a claim that an existing `verification.json` was missing.

Judge-v3 instead receives:

- the exact condition-specific projected query;
- the exact input manifest and labelled source/reference images;
- complete evaluator-computed file facts, hashes, and PNG dimensions;
- labelled final output images and actual business deliverable text;
- no candidate verification, metrics, masks, change-set, or narrative claims
  as proof.

It passed a counterfactual with all CAM business outputs removed at 1/5 on all
three L4 quality dimensions. Details are in `JUDGE_VALIDATION.md`.

## Reproduce

From the experiment directory:

```bash
python3 scoring/score_rubric_v02.py
python3 scoring/score_selfverification.py
python3 scoring/summarize_v02.py
```

Live judge passes additionally require `google-genai`, `GEMINI_API_KEY`, and an
explicit `JUDGE_MODEL` (the recorded run used `gemini-2.5-pro`):

```bash
python3 scoring/judge_rubric_v03.py
python3 scoring/judge_tool_execution_v02.py
```
