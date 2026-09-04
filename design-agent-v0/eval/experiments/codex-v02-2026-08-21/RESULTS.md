# Codex × Brief Bank v0.2 — Results

Evidence snapshot: `2026-09-02T12:40:48.736Z`.

## Headline

- Candidate execution: **32/32** unique conditions have a primary completed run.
- Attempt ledger: **66** attempts — completed 32, error 31, timeout 3.
- Observable rubric weight: **75.0%** on average across conditions.
- Full-rubric condition-macro interval: **0.659–0.909**; observable-only normalized diagnostic: **0.874**.
- Base-episode macro interval (each of 24 briefs equal-weighted): **0.686–0.919**.

No point estimate is reported for the full rubric: workflow completion and recovery are not independently observable under the v0.2 event contract.

## Dimension coverage

| Dimension | Coverage | Mean | Scale | Method |
|---|---:|---:|---|---|
| Artifact contract | 32/32 | 1.000 | 0-1 | deterministic |
| Brief understanding | 32/32 | 3.469 | 0-5 | gemini-2.5-pro condition-aware artifact-grounded judge-v3 |
| Cross-asset consistency | 24/24 | 3.500 | 0-5 | gemini-2.5-pro condition-aware artifact-grounded judge-v3 |
| Efficiency | 32/32 | 1.000 | 0-1 | deterministic |
| Recovery | 0/32 | — | — | unobservable under v0.2 protocol |
| Revision fidelity | 24/24 | 4.875 | 0-5 | gemini-2.5-pro condition-aware artifact-grounded judge-v3 |
| Tool execution | 8/8 | 4.500 | 0-5 | gemini-2.5-pro condition-aware artifact-grounded judge-v3 |
| Workflow completion | official 0/24; proxy 24/24 | proxy 1.000 | 0-1 proxy | version-progression proxy; excluded from official score bounds |

## Performance slices

These are observable-only diagnostics plus honest full-rubric bounds; they are not fully observed total scores.

| Slice | Conditions | Observable diagnostic | Full-rubric interval |
|---|---:|---:|---:|
| level: `L3` | 8 | 0.944 | 0.850–0.950 |
| level: `L4` | 24 | 0.850 | 0.595–0.895 |
| intent: `adapt` | 4 | 0.850 | 0.695–0.895 |
| intent: `edit` | 5 | 0.860 | 0.664–0.884 |
| intent: `evaluate_rank` | 5 | 0.983 | 0.808–0.988 |
| intent: `export` | 5 | 0.931 | 0.692–0.952 |
| intent: `generate` | 13 | 0.822 | 0.575–0.875 |
| category: `brand_identity_directions` | 5 | 0.863 | 0.644–0.904 |
| category: `client_feedback_revision` | 3 | 0.957 | 0.737–0.970 |
| category: `concept_to_factory_ready` | 3 | 0.886 | 0.687–0.920 |
| category: `ecommerce_launch_suite` | 5 | 0.748 | 0.546–0.806 |
| category: `existing_brand_campaign` | 5 | 0.863 | 0.644–0.904 |
| category: `multi_format_adaptation` | 3 | 0.871 | 0.677–0.910 |
| category: `packaging_sku_family` | 3 | 0.929 | 0.717–0.950 |
| category: `reference_to_original` | 5 | 0.931 | 0.692–0.952 |

## Reliability and cost shape

Selected successful runs: latency p50 **29.92 min**, p95 **63.17 min**, max **94.62 min**.

Execution success and design quality are reported separately. Historical failed and timed-out attempts remain in `run-index.jsonl`; selecting one latest successful primary attempt per condition prevents retries or duplicate runs from changing quality means.

## Context ablation

| Brief | zero-shot BU | reference BU | personalized BU | zero/ref/personalized observable diagnostic |
|---|---:|---:|---:|---|
| DAB-L4-BID-001 | 5 | 2 | 4 | 0.914 / 0.786 / 0.829 |
| DAB-L4-CAM-001 | 2 | 2 | 2 | 0.786 / 0.743 / 0.786 |
| DAB-L4-ECO-001 | 2 | 2 | 2 | 0.786 / 0.743 / 0.743 |
| DAB-L4-RTO-001 | 3 | 3 | 5 | 0.914 / 0.871 / 1.000 |

Each ablation arm has one stochastic run, so the deltas are descriptive rather than causal estimates.

## Low-scoring judged dimensions (0–2/5)

- `DAB-L3-ECO-002@reference_grounded` — `brief_understanding` **1/5**: The agent failed to perform the core requested action of retouching the image. While it correctly preserved all invariants, it also preserved the elements it was explicitly asked to change (reflections, haze), violati...
- `DAB-L4-MFA-002@reference_grounded` — `cross_asset_consistency` **1/5**: The adaptation map shows a clear plan for a visually consistent set of assets. However, the entire channel pack is missing. Without any final assets, there is no 'coherent visual system' to evaluate, which constitutes...
- `DAB-L3-ECO-002@reference_grounded` — `tool_execution` **1/5**: The requested image editing operation did not occur. The output file is perceptually identical to the input, indicating a failure to execute the retouching tools to achieve the specified visual changes. The deliverabl...
- `DAB-L4-BID-001@reference_grounded` — `brief_understanding` **2/5**: The agent correctly interpreted the complex workflow of diverging, clustering, awaiting selection, and converging. However, it failed on multiple explicit deliverable requirements, missing a required JSON file for the...
- `DAB-L4-CAM-001@personalized` — `brief_understanding` **2/5**: The agent correctly understood the creative task, constraints, and multi-step workflow, producing a high-quality exploration and revision. However, it failed to deliver the final and most important output: the three-p...
- `DAB-L4-CAM-001@reference_grounded` — `brief_understanding` **2/5**: The agent correctly understood and executed the initial exploration phase, including the divergence (9 hypotheses), clustering (3 territories), and adherence to all brand constraints. However, it failed to deliver the...
- `DAB-L4-CAM-001@zero_shot` — `brief_understanding` **2/5**: The agent correctly interpreted the creative direction, constraints, and phased workflow, including the human checkpoint. However, it failed to deliver the final and most critical part of the request: the three-asset...
- `DAB-L4-CFR-003@reference_grounded` — `brief_understanding` **2/5**: The agent correctly combined the composition and palette references and followed the multi-round revision workflow. However, it failed a key, explicit instruction in the initial brief by introducing a typo ('低躁运行') in...
- `DAB-L4-CFRY-002@reference_grounded` — `brief_understanding` **2/5**: The agent correctly understood the multi-stage workflow, constraints, and the need to clarify factory parameters. However, it failed on two key deliverable requirements: the intermediate concept package was missing on...
- `DAB-L4-CFRY-003@reference_grounded` — `brief_understanding` **2/5**: The agent correctly executed the core technical print-preparation and revision tasks. However, it failed to meet the specific deliverable packaging requirements for both the intermediate and final stages, omitting req...
- `DAB-L4-ECO-001@personalized` — `brief_understanding` **2/5**: The candidate demonstrated excellent understanding of the multi-stage workflow, constraints, and the client's intent. They correctly identified a key blocker (missing asset for the 'integrated loop' feature) which pre...
- `DAB-L4-ECO-001@reference_grounded` — `brief_understanding` **2/5**: The agent correctly understood the multi-stage workflow, constraints, and the human-in-the-loop decision process. However, it failed to deliver the primary final output of six assets, which is a critical failure to me...
- `DAB-L4-ECO-001@zero_shot` — `brief_understanding` **2/5**: The agent correctly followed the overall workflow, including the crucial human selection checkpoint. However, it failed on multiple explicit deliverable requirements: the exploration map and scene directions were in t...
- `DAB-L4-MFA-002@reference_grounded` — `brief_understanding` **2/5**: The agent correctly identified all channels and key information, and produced a valid adaptation plan. However, it completely failed to produce the primary deliverable: the seven final image files. This is a critical...
- `DAB-L4-PSF-001@reference_grounded` — `brief_understanding` **2/5**: The candidate correctly followed the complex, phased workflow (diverge-cluster-select-converge) and met all hard constraints. However, the score is low because multiple key deliverable requirements were clearly unmet:...
- `DAB-L4-BID-001@personalized` — `cross_asset_consistency` **2/5**: The assets that were produced (v0 concepts, v1 refinement) are internally consistent and consistent with each other across versions. However, the final and most important deliverable, the `identity-starter-kit` contai...
- `DAB-L4-BID-003@reference_grounded` — `cross_asset_consistency` **2/5**: The overall set of assets is critically incomplete and inconsistent in fidelity. The required intermediate visual assets (brand_direction_board) are entirely missing, breaking the logical flow from exploration to fina...
- `DAB-L4-CAM-001@reference_grounded` — `cross_asset_consistency` **2/5**: The assets that were produced are highly consistent. The nine KV options in v0 are well-organized into three coherent, distinct territories. The v1 revision is also consistent with the selected v0 direction. However,...
- `DAB-L4-ECO-001@personalized` — `cross_asset_consistency` **2/5**: The intermediate assets that were produced (v0 exploration and v1 revision) are internally consistent and adhere to the brand guidelines. However, the final, most critical deliverable—the 6-asset launch suite—is missi...
- `DAB-L4-ECO-001@reference_grounded` — `cross_asset_consistency` **2/5**: The few assets that were produced for the v1 revision are visually consistent with each other. However, the core requirement of a consistent 6-asset launch suite was not met because the suite is entirely missing. The...

## Measurement limits

- `workflow_completion` is reported only as a version-count proxy and is excluded from official bounds; the trajectory does not bind required checkpoint IDs.
- `recovery` remains unscored for the same event/check-vocabulary gap.
- Gemini judge-v3 scores are independent model judgments, not human ground truth; raw reasons and check ledgers remain in JSONL for audit.
- The earlier general judge-v2 is excluded from canonical scores: it used the base query for zero-shot arms and lacked a complete evaluator inventory, producing demonstrable false violations.
- The first tool-execution judge was rejected after two counterfactual controls still received 5/5. V2 passed the same controls at 0/5 and 1/5 and excludes candidate-authored self-evidence.

## Reproduce

```bash
python3 scoring/score_rubric_v02.py
python3 scoring/score_selfverification.py
python3 scoring/summarize_v02.py
```
