# Curify Design Agent Unified Rubric v0.1

Date: 2026-09-04
Scope: agent-neutral evaluation of routing, planning, visual execution, revision, ranking, and production delivery.

## Decision

The seven existing Codex benchmarks can be reported under one evaluation protocol, but their raw
headline metrics must **not** be averaged. They observe different surfaces:

- routing and safe abstention;
- planner-only workflow recovery;
- single-turn multimodal design execution;
- multi-turn stateful design execution;
- alignment with a historical human selection.

This rubric therefore has one task-level design-quality score, conditional hard gates, four
diagnostic panels, and an explicit evidence-coverage value. A suite report is a scorecard, not one
unsupported scalar.

## Current seven-benchmark Codex scorecard

| Benchmark | Scope and completion | Headline result | What it establishes | Important limitation |
|---|---|---|---|---|
| 21q single-turn multimodal | 21/21 judged; 20/21 first attempt | quality 0.609; gated 0.414; 8/21 pass | Real-pixel generate/edit/rank/export stress test | Only 21 cases; category distribution is skewed |
| Brief Bank v0.2 | 32/32 final conditions | full-rubric interval 0.659–0.909; observable diagnostic 0.874 | Context conditions, revisions, artifact contract | `workflow_completion` and `recovery` were not independently observable; 66 raw attempts included 31 errors and 3 timeouts |
| Routing 118 | 118/118 first attempt | intent F1 0.809; template top-1 0.714; agent route 16/18; gap abstention 0/23 | Intent and candidate recall are strong | The agent over-routes every known capability gap |
| 99designs rank | 61/61 first attempt; 243 pairs | winner top-1 14/61 (23.0%); pairwise 153/243 (63.0%); different-designer 63.6% | Some alignment with observed commercial choices | Top-1 is near the 20.1% chance baseline; selection is not objective visual-quality ground truth |
| Workflow briefs | 11/11 first eligible attempt | intent 81.8%; step F1 48.2%; order LCS 89.1%; gated 0.625; 1/11 pass | Recovers the broad order and deliverables of documented workflows | Planner-only; exact sequence 0%; does not evaluate final design |
| ZCOOL briefs | 7/7 first eligible attempt | reference coverage 100%; deliverable recall 91.7%; class exact 28.6%; gated 0.868; 7/7 pass | Strong external-reference and deliverable handling | Planner-only; thumbnails are neither process truth nor preference gold |
| Brief Bank v0.3 | 43/43 represented | combined interval 0.742–0.928; new external 11 weighted 0.984 and 11/11 gate+score pass | Full multi-turn execution for the 11 new failure-mode cases | The 32 core rows are carried forward from v0.2, not fresh calls; external is one curated, unbalanced sample per condition |

### Evidence-based diagnosis

**Strong:** routing recall, reference loading, deliverable recall, visible craft, production-file
generation, and the 11 new bounded/full-episode tasks.

**Weak:** safe abstention (0/23), exact planner steps (F1 0.482; exact sequence 0), historical
winner top-1 selection (0.230), and the 21q dimensions most sensitive to doing the exact requested
operation: brief adherence 0.438, refinement 0.375, creative diversity 0.400, and cross-asset
consistency 0.500.

The high v0.3 external score does not erase the 21q and 99designs weaknesses. It says Codex performs
very well on eleven fixture-ready cases under a richer file/tool environment; it does not prove
general design taste or production reliability across distributions.

## A. Task-level design-quality rubric

These are the mentor's eight dimensions. Score each applicable dimension from 0–5 using artifact,
pixel, file, and trajectory evidence. Applicability must be declared before execution.

| Dimension | Weight | 1 — major failure | 3 — usable with important weakness | 5 — fully supported |
|---|---:|---|---|---|
| Brief adherence | 15% | Wrong operation or material brief violation | Main intent met but an important requirement is missing | All required outputs, constraints, and exclusions are observably satisfied |
| Visual quality | 20% | Unusable composition, legibility, realism, or visible defects | Usable design with noticeable craft or hierarchy problems | High craft, clear hierarchy, legible, coherent, and free of material defects |
| Creative diversity | 10% | Required alternatives are duplicates or superficial variants | Some distinction, but directions still share the same core idea | Alternatives are meaningfully different concepts with clear trade-offs |
| Brand consistency | 15% | Identity/reference role is broken or copied incorrectly | Mostly coherent with limited drift or unsupported interpretation | Locked identity is preserved and the visual system is consistently applied |
| Refinement ability | 15% | Regenerates the work or changes protected content | Requested change is present but has collateral drift or weak state evidence | Applies only the requested delta and correctly preserves or recovers approved state |
| Cross-asset consistency | 10% | Assets conflict or lose their required roles | A loose shared system with visible inconsistencies | A coherent system spans every asset while preserving format-specific differences |
| Production readiness | 10% | Missing, corrupt, structurally false, or unusable delivery | Usable preview/output but incomplete package or preflight | Required formats, dimensions, structure, preflight, and handoff evidence all pass |
| Efficiency | 5% | Fails, loops, or needs avoidable intervention | Completes with avoidable retries, latency, or waste | Completes in the intended turns, within the declared budget, without unnecessary reruns |

General anchors: 0 = not addressed; 1 = core result wrong; 2 = materially flawed; 3 = usable but
incomplete; 4 = correct with minor weakness; 5 = complete with strong evidence and no material
defect.

## B. Hard gates

Hard gates are evaluated before the weighted score. They are parameterized per case rather than
blindly required for every task.

| Gate | Applies to | Pass condition |
|---|---|---|
| Completion | all cases | Required turns finish and a final response/artifact set exists |
| Task boundary / safe abstention | routing and unsupported tasks | Correct operation is selected, or the agent explicitly abstains when no supported capability exists |
| Required input and reference contract | reference/image cases | Every required input is consumed and only allowed reference channels are transferred |
| Hard constraints | all cases | Every case-specific invariant, exact-copy/count, privacy, and forbidden-action constraint passes |
| Artifact contract | execution cases | Required count, type, format, and structured evidence files are present and readable |
| Approval order and state continuity | L4/revision cases | Human selection precedes convergence; later turns preserve locked state and requested rollback scope |
| Production validity | print/export cases | Claimed vector/raster/PDF/package properties pass independent file inspection |

An agent hard-gate failure sets `gated_score = 0`, while retaining the ungated quality score for
diagnosis.

Evaluator-validity gates are separate: fixture integrity, complete independent-judge coverage,
scorer version/hash, and sufficient evidence. If one fails, the result is **incomplete**, not an
agent score of zero.

## C. Scoring and missing-evidence rules

For the dimensions declared applicable before a run:

```text
quality_score = Σ(weight_d × score_d / 5) / Σ(applicable weight_d)
gated_score   = quality_score if all applicable agent hard gates pass, otherwise 0
benchmark_pass = evaluator-valid result AND all agent gates pass AND quality_score >= 0.70
```

- A candidate fails to provide required evidence: score that dimension 0.
- Evaluator instrumentation is missing: report a lower/upper interval for the missing weight and
  do not award a benchmark pass. This is the v0.2 rule.
- A dimension is genuinely irrelevant: mark `NOT_APPLICABLE` only if declared before execution;
  renormalize over the remaining applicable weights.
- Always publish `rubric_coverage = observed applicable weight / required applicable weight`.
- Report sample count, first-attempt completion, retry/timeout count, latency, model/prompt/dataset/
  scorer hashes, and a confidence interval where repeated human-choice events exist.

### Legacy scorer crosswalk

New runs should emit the eight canonical IDs directly. Existing results may be projected only with
a documented, task-specific crosswalk:

| Legacy dimension | Canonical destination | Rule |
|---|---|---|
| `brief_understanding` | `brief_adherence` | Partial evidence only; it cannot prove final-output adherence by itself |
| `revision_fidelity`, `edit_fidelity`, `preservation_fidelity` | `refinement_ability` | Use only on edit/revision tasks and retain the original evidence |
| `reference_contract` | `brand_consistency` | Use only when brand/reference identity is an applicable requirement |
| `artifact_contract`, `verification_quality`, `scalability` | `production_readiness` | Treat as components; no single component automatically becomes the whole production score |
| `workflow_completion`, `recovery` | approval/state gate plus workflow diagnostic | Do not silently fold into a visual-quality dimension |
| `tool_execution`, `output_fidelity` | no global automatic mapping | Map only against the task's predeclared success contract |

Do not average multiple legacy dimensions into one canonical dimension after seeing the result.
Freeze the mapping before a cross-Agent rerun.

## D. Diagnostic panels outside the quality score

| Panel | Canonical metrics | Current source |
|---|---|---|
| Routing and boundary | intent F1/exact, template top-1/recall, route exact, gap abstention | Routing 118 |
| Workflow planning | step F1, ordered LCS, deliverable recall, boundary awareness | Workflow 11 + ZCOOL 7 |
| Preference alignment | winner top-1, MRR, pairwise accuracy, bootstrap CI, position bias | 99designs |
| Reliability and cost | first-attempt rate, attempts, retry/timeout/error, p50/p95 latency, normalized cost | every runner |

These panels must remain visible. For example, high intent recall cannot compensate for 0% safe
abstention, and an attractive output cannot compensate for a broken edit or production gate.

## E. How the seven datasets map into the unified protocol

| Dataset | Canonical role | Quality score? | Gates/panels | Counting rule |
|---|---|---:|---|---|
| 21q | single-turn multimodal stress | yes | artifact, inputs, hard constraints, production, reliability | independent stress set |
| Brief Bank v0.2 | legacy multi-turn core | interval only | artifact, revision, workflow/recovery observability | lineage only after v0.3; never double-count |
| Routing 118 | fast routing regression | no | routing/boundary panel | report separately |
| 99designs | external preference canary | no | preference panel | human choice signal, not quality gold |
| Workflow 11 | known-sequence planner regression | no | workflow-planning panel | no final-design claim |
| ZCOOL 7 | external planner/reference regression | no | workflow-planning panel | no process/quality-gold claim |
| Brief Bank v0.3 | primary L3/L4 execution benchmark | yes | full conditional gates plus reliability | count 32 core + 11 external once; report partitions separately |

## F. Canonical cross-Agent report

Every Curify/Codex/Canva/other-Agent comparison should publish, in order:

1. dataset and adapter coverage;
2. task-level `quality_score`, `gated_score`, and pass rate for 21q and Brief Bank v0.3;
3. routing/boundary panel;
4. workflow-planning panel;
5. preference-alignment panel;
6. first-attempt reliability, retries, timeouts, latency, and cost;
7. hard-gate failure ledger and scorer/model/dataset hashes.

Do not publish a seven-dataset average. If a single executive number is eventually required, first
freeze one common task mixture, rerun every Agent under this v0.1 rubric, deduplicate v0.2/v0.3,
and attach coverage plus confidence intervals to that number.
