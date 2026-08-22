# L3/L4 Design Agent Brief Bank

This directory is the workflow-level companion to `../queries.jsonl`.

- `queries.jsonl` remains the fast 118-case routing regression set.
- `briefs.v0.2.jsonl` is the current protocol for tool use, workflow completion, revision,
  context, and state evaluation.
- `briefs.v0.1.jsonl` is the frozen 24-episode business-task baseline.
- A brief is not just a prompt. It contains inputs, constraints, checkpoints, feedback,
  deliverables, failure conditions, and a scoring contract.

## v0.2 designer-feedback upgrade

v0.2 keeps the same 24 business jobs, IDs, categories, source inputs, business goals, and final
deliverables as v0.1. It changes the **episode protocol**, based on working-designer feedback:

| feedback / failure mode | v0.2 test contract |
|---|---|
| repeated revisions lose context | 8 deep cases have 3 feedback turns across 2 sessions, explicit state versions, resume points, locked invariants, and selective rollback |
| broad exploration needs human filtering | 6 cases require 8–12 cheap hypotheses → 3 Creative Territories → human selection → convergence |
| generated elements still need manual composition | 6 edit/adaptation cases require `design_document.json`, object-level `change_set.json`, `preview.png`, verification, and action trace |
| zero-shot is difficult to align | 4 base briefs run under `zero_shot`, `reference_grounded`, and `personalized` conditions |
| reference roles are easily mixed up | every provided pixel asset has an allowed influence and identity-preservation policy |
| an attractive final image can hide workflow failure | every v0.2 run requires `verification.json` and an observable `trajectory.jsonl` |

Coverage is overlapping rather than 24 mutually exclusive buckets:

| axis | v0.2 coverage |
|---|---|
| base business episodes | 24: L3 8 · L4 16 |
| projected run conditions | 32: reference-grounded 24 · zero-shot 4 · personalized 4 |
| deep multi-turn revision | 8 cases |
| creative exploration | 6 cases |
| structured object editing | 6 cases |
| context ablation | 4 base cases × 3 conditions |
| messy work | 9/24 (37.5%) |

`trajectory.jsonl` means observable action evidence—normalized plan/checkpoint, tool call, state
version, artifact, verification, and user-decision events. It does not require or store private
chain-of-thought.

## Frozen v0.1 pilot

The pilot contains 24 cases: three cases in each of the eight content categories proposed in
Curify Studio's `docs/design-agent-v0-spec.md` §7m. Every category contains one bounded L3 Tool
Agent case and two L4 Workflow Agent cases.

| axis | coverage |
|---|---|
| capability level | L3: 8 · L4: 16 |
| content category | 8 categories × 3 cases |
| primary delivery intent | generate: 5 · edit: 5 · evaluate-rank: 5 · export: 5 · adapt: 4 |
| messy work | 9/24 (37.5%) |
| language | Chinese-first, with realistic mixed English platform/production terms |

The two axes are deliberate. Content category alone cannot expose the failures found by the 21q
evaluation: edit→regenerate, evaluate→generate, and export→explain.

## Files

- `briefs.v0.2.jsonl` — current 24 workflow episodes.
- `initial_queries.v0.2.jsonl` — generated 32-condition first-turn projection.
- `brief.v0.2.schema.json` — v0.2 portable JSON Schema.
- `build_v02.py` — deterministic upgrade from the frozen v0.1 rows.
- `briefs.v0.1.jsonl` — the benchmark rows.
- `initial_queries.v0.1.jsonl` — generated first-turn projection for legacy query runners.
- `brief.schema.json` — frozen v0.1 JSON Schema.
- `validate_briefs.py` — dependency-free semantic and fixture validator.
- `export_initial_queries.py` — condition-aware projection for query-only routing adapters.

Run validation from `design-agent-v0`:

```bash
python3 eval/brief_bank/build_v02.py
python3 eval/brief_bank/validate_briefs.py
python3 eval/brief_bank/export_initial_queries.py \
  --output eval/brief_bank/initial_queries.v0.2.jsonl
python3 -m unittest discover -s eval/brief_bank -p 'test_*.py'
```

The validator checks both versions. For v0.2 it additionally checks exact capability coverage,
state-version continuity, cross-session resume evidence, reference-role completeness, ablation
input boundaries, structured edit artifacts, and that the 24 business episodes still match the
frozen v0.1 source. Every referenced image is verified against
`reference-pack-v0.2/manifest.jsonl` and its SHA-256.

## Episode contract

Each v0.2 row contains:

```text
initial_query
  + condition-filtered inputs / reference contract / optional preference memory
  + constraints / editable parameters / locked project state
  → observable checkpoints + required human decisions
  → hidden-until-due simulated client feedback
  → intermediate and final deliverables
  → structured artifacts + verification + action trajectory
  → hard gates + checkpoint rubric
```

`expected_workflow` describes observable checkpoint outcomes, not a single golden chain of thought.
An agent may take a different valid path as long as the required evidence and artifacts exist.

The generated query projection contains only the first user message, condition-allowed inputs, and
prior preference memory when the condition explicitly permits it. Future client feedback is kept
in the full episode and is never projected into turn 1. Do not edit generated projections directly.
A passing projection run must never be reported as an L4 workflow pass.

L3 cases focus on bounded tool selection and execution. L4 cases require at least one feedback turn,
four checkpoints, multiple deliverables, an explicit human decision, and state that survives across
the episode. The 8 deep cases strengthen that minimum to three feedback turns over two sessions.

## Context conditions

The four ablation briefs use three matched conditions:

- `zero_shot`: preserves task-required source/product inputs while removing only assets explicitly
  marked `optional_for_zero_shot`; its query is rewritten so it does not mention omitted files.
- `reference_grounded`: includes every provided task input, with no preference memory.
- `personalized`: uses the same inputs as reference-grounded plus project-scoped accepted/rejected
  preference signals from simulated prior sessions.

The other 20 briefs run once as `reference_grounded`. Therefore 24 base episodes become 32 run
rows, not 72. Compare conditions within the same `base_brief_id`; do not treat them as independent
business tasks.

## Provenance and limitations

This is a harness-ready benchmark contract, not a completed Agent experiment and not a claim that
24 private client records have been collected. The preference memories and later feedback turns are
controlled fixtures, not real customer histories. `provenance.kind` distinguishes:

- `reverse_constructed`: process facts come from an existing documented public case; wording and
  test constraints are newly authored.
- `internal_scenario`: grounded in Curify's documented customer/factory/ecommerce workflows, with
  identifying details removed or replaced.
- `controlled_synthetic`: created to exercise a specific capability or failure mode.

No row should be presented as verbatim customer data. The 160-case target should progressively
replace controlled rows with consented, anonymized real briefs plus revision histories. Preserve
the same schema so real and synthetic evidence never become indistinguishable.

## Adding a real brief

1. Copy the user's wording only with consent; otherwise paraphrase and mark it.
2. Remove names, contact details, unreleased product information, and signed URLs.
3. Record asset license/privacy status outside the prompt.
4. Encode client feedback as a later turn, not as knowledge available at turn 1.
5. Define invariant regions for edits and hard delivery gates before running an agent.
6. Add the row, run the validator, and keep hidden-test feedback out of agent-visible context.
