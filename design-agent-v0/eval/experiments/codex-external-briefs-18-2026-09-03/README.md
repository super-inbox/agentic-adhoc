# Codex external-brief planning benchmark (11 + 7)

This experiment closes the evaluation boundary for two older external datasets
without overstating what their evidence can support.

## Layers

| layer | n | candidate input | actual claim |
|---|---:|---|---|
| `case_study_workflow` | 11 | newly paraphrased task context, no source identity | recovery of one documented case-study step sequence |
| `portfolio_reference` | 7 | terse ZCOOL brief plus low-resolution published-outcome thumbnails | grounded brief classification, reference coverage and deliverable planning |

Neither layer asks Codex to generate final designs. The first has process gold
but no complete execution fixture. The second has outcome references but no
process, feedback, rejected options or production-file gold.

## Protocol added to the original 11 briefs

The source rows previously had only a title-like `brief`, `domain`, ordered
`expected_steps`, and provenance. This experiment adds:

- explicit `primary_intent` and `secondary_intents`;
- a candidate-visible, source-grounded task paraphrase;
- a closed workflow vocabulary and schema-constrained plan output;
- an explicit `plan_only` execution boundary;
- missing-input, assumption and stop-condition fields;
- deterministic scoring for intent, step set, order and length;
- hard gates for valid output, zero tool calls and no execution claim;
- a pass threshold of 0.70 and frozen dataset/prompt/runner/scorer hashes.

This is `workflow-planning-v1`, not a replacement for the Brief Bank episode
contract. A full design-agent execution benchmark would additionally need actual
input assets, constraints, deliverable files, feedback turns, human decisions,
verification events and task-specific visual/production rubrics.

## Reproduce

```bash
python3 scripts/build_dataset.py
python3 scripts/run_codex.py --all --allow-model-usage --workers 3
python3 scripts/score.py
```

The runner never exposes source URLs, author identity, gold steps or expected
deliverable labels to the candidate. ZCOOL images are attached in a temporary
workspace and verified by SHA-256 before each invocation.

## Rights and interpretation

- Case-study step labels represent one observed public workflow, not the only
  correct way to design.
- ZCOOL thumbnails remain internal-evaluation-only identification artifacts.
- Published outcomes are not negative/positive preference labels and are never
  scored by pixel similarity.
- The benchmark measures planning and visual grounding, not final design taste,
  manufacturing correctness or client acceptance.
