# Judge validation for Brief Bank v0.2

The canonical quality grader is `judge_rubric_v03.py`. Model-judge output is
accepted only after positive-case review and counterfactual negative controls.

## Rejected graders

### General judge-v2

The completed v2 pass is retained in `rubric-v02-judged-v2.jsonl` as an audit
artifact, but excluded from canonical scores. It had two evidence defects:

1. It always used the base brief query. On context-ablation zero-shot runs this
   could penalize the agent for not using optional references that the
   condition intentionally removed.
2. It excluded candidate `verification.json` content, correctly, but supplied
   no independent output inventory. It could therefore call an existing file
   or deliverable “missing.” Source/reference images were also not attached.

Observed corrections after adding condition-specific queries, evaluator file
facts, and labelled source/output images:

| Case | v2 | v3 | Review |
|---|---:|---:|---|
| `DAB-L3-CFR-002@reference_grounded` brief | 1 | 5 | Source/output comparison confirms the requested title scale and mark move; v2 falsely claimed rewritten text. |
| `DAB-L4-RTO-001@zero_shot` brief | 1 | 3 | V2 required analysis of three references intentionally omitted by zero-shot; v3 marks that gate N/A. |
| `DAB-L4-RTO-003@reference_grounded` brief | 1 | 3 | V2 claimed `verification.json` was missing; the evaluator inventory confirms it exists. |
| `DAB-L4-CFR-001@reference_grounded` revision | 2 | 5 | V2 mistook three sequential revision states for an excessive final-deliverable count. |

### Tool-execution judge-v1

V1 included candidate-authored change sets, metrics, masks, and narratives as
evidence. Two temporary counterfactual controls both incorrectly received 5/5:

- all CAM PNG/SVG outputs deleted;
- CFR final preview replaced by the unchanged source while stale self-evidence
  remained.

The temporary v1 result file was therefore discarded and is not a valid score
source.

## Accepted controls

The artifact-only tool judge-v2 removes candidate self-evidence and uses actual
file presence, hashes, PNG dimensions, production-file facts, and labelled
source/final images. On the same controls it returned:

| Counterfactual | Expected | Result |
|---|---:|---:|
| CAM final assets removed | 0–2 | **0** |
| CFR preview replaced by byte-identical source | 0–2 | **1** |

The unified general judge-v3 uses the same evidence boundary plus the
condition-specific query. With all CAM business outputs removed, it returned
**1/5 brief understanding, 1/5 revision fidelity, and 1/5 cross-asset
consistency**. It explicitly cited missing inventory entries rather than stale
candidate claims.

## Canonical scoring rule

- `rubric-v02-judged-v3.jsonl`: canonical independent model-judge results.
- `tool-execution-judged-v2.jsonl`: independent L3 cross-check; not double
  counted in the summary.
- `rubric-v02-judged-v2.jsonl`: negative historical experiment, excluded from
  all totals. The temporary tool-execution v1 output was discarded.
- `rubric-v02-partial.jsonl`: deterministic artifact-contract and efficiency
  scores.
- `workflow_completion` remains a labelled proxy; `recovery` remains
  unobservable. Neither is silently imputed.
