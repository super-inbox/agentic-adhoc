# Codex × Brief Bank v0.3 — Results

## Headline

- Dataset coverage: **43/43 conditions** across **35 episodes**.
- Core partition: **32/32** conditions carried forward from the unchanged, frozen v0.2 baseline; interval **0.659–0.909**.
- External v0.3 extension: **11/11** conditions newly executed and independently judged; weighted macro **0.984**.
- Combined 43-condition interval: **0.742–0.928**.
- External hard-gate pass: **11/11**; score+gate pass: **11/11**.

The 32 inherited rows are explicitly marked `carried_forward_v0.2`; they are not reported as fresh model calls.

## External v0.3 results

| Condition | Category | Weighted score | Hard gates | Benchmark pass |
|---|---|---:|---:|---:|
| `DAB-L3-RDT-001@reference_grounded` | `multi_format_adaptation` | 1.000 | PASS | PASS |
| `DAB-L3-RDT-002@reference_grounded` | `reference_to_original` | 0.980 | PASS | PASS |
| `DAB-L3-RDT-003@reference_grounded` | `reference_to_original` | 0.950 | PASS | PASS |
| `DAB-L3-RDT-004@reference_grounded` | `reference_to_original` | 0.980 | PASS | PASS |
| `DAB-L3-RDT-005@reference_grounded` | `client_feedback_revision` | 1.000 | PASS | PASS |
| `DAB-L3-RDT-006@reference_grounded` | `client_feedback_revision` | 1.000 | PASS | PASS |
| `DAB-L3-RDT-010@reference_grounded` | `concept_to_factory_ready` | 1.000 | PASS | PASS |
| `DAB-L3-RDT-011@reference_grounded` | `concept_to_factory_ready` | 1.000 | PASS | PASS |
| `DAB-L4-RDT-007@reference_grounded` | `brand_identity_directions` | 0.910 | PASS | PASS |
| `DAB-L4-RDT-008@reference_grounded` | `concept_to_factory_ready` | 1.000 | PASS | PASS |
| `DAB-L4-RDT-009@reference_grounded` | `concept_to_factory_ready` | 1.000 | PASS | PASS |

## Hard-gate failures

- None.

## Reliability

- New execution attempts: **11** — completed 11.
- Selected external latency: p50 **12.84 min**, p95 **52.15 min**, max **52.15 min**.

## Measurement boundaries

- Core v0.2 workflow/recovery gaps remain bounds, not invented point scores.
- External scores are artifact-grounded Gemini judgments with independent file, vector, PDF, and masked-pixel facts; they are not human ground truth.
- The judge counterfactual passed: retaining stale candidate claims while replacing the edited output with the unchanged source reduced edit fidelity from 5/5 to 0/5.
- Candidate-visible structured-artifact requirements named the files, not the hidden schema-validation prose; presence is measured, but hidden prose is not used as a penalty.
- One candidate sample per external condition does not measure variance.

## Reproduce

```bash
BUNDLED_PY=/path/from/codex-workspace-dependencies/python/bin/python3
PYTHONPATH=.private/judge-python:scoring "$BUNDLED_PY" scoring/judge_v03.py
PYTHONPATH=.private/judge-python:scoring "$BUNDLED_PY" scoring/validate_judge_v03.py
PYTHONPATH=.private/judge-python:scoring "$BUNDLED_PY" scoring/summarize_v03.py
"$BUNDLED_PY" scripts/freeze_v03_experiment.py
```
