# L3/L4 Design Agent Brief Bank

This directory is the workflow-level companion to `../queries.jsonl`.

- `queries.jsonl` remains the fast 118-case routing regression set.
- `briefs.v0.1.jsonl` evaluates tool use and workflow completion as task episodes.
- A brief is not just a prompt. It contains inputs, constraints, checkpoints, feedback,
  deliverables, failure conditions, and a scoring contract.

## v0.1 pilot

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

- `briefs.v0.1.jsonl` — the benchmark rows.
- `initial_queries.v0.1.jsonl` — generated first-turn projection for legacy query runners.
- `brief.schema.json` — portable JSON Schema for one row.
- `validate_briefs.py` — dependency-free semantic and fixture validator.
- `export_initial_queries.py` — compatibility projection for query-only routing adapters.

Run validation from `design-agent-v0`:

```bash
python3 eval/brief_bank/validate_briefs.py
python3 eval/brief_bank/export_initial_queries.py \
  --output eval/brief_bank/initial_queries.v0.1.jsonl
python3 -m unittest discover -s eval/brief_bank -p 'test_*.py'
```

The validator checks schema-level fields, unique IDs, two-axis coverage, L3/L4 checkpoint shape,
feedback requirements, rubric weights, messy-task ratio, and every referenced image against
`reference-pack-v0.2/manifest.jsonl` and its SHA-256.

## Episode contract

Each row contains:

```text
initial_query
  + inputs / constraints / available tools
  → checkpoints
  → optional simulated client feedback
  → intermediate and final deliverables
  → hard gates + checkpoint rubric
```

`expected_workflow` describes observable checkpoint outcomes, not a single golden chain of thought.
An agent may take a different valid path as long as the required evidence and artifacts exist.

The generated query projection contains only the first user message and input bindings. Do not edit
it directly. It can expand a
legacy routing test, but a passing projection run must never be reported as an L4 workflow pass.

L3 cases focus on bounded tool selection and execution. L4 cases require at least one feedback turn,
four checkpoints, multiple deliverables, and state that survives across the episode.

## Provenance and limitations

This is a harness-ready pilot, not a claim that 24 private client records have been collected.
`provenance.kind` distinguishes:

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
