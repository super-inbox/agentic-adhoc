# Codex × 99designs evaluate/rank baseline

This experiment turns the 61 local 99designs contest records into a blinded,
brief-conditioned ranking benchmark for Codex.

Each case contains the public, incomplete brief excerpt and the four or five
locally stored public preview images from one contest. The true winner is
deterministically shuffled into a balanced A–E position. Codex receives only
the blinded option labels and pixels; winner/designer/selection metadata never
enters the prompt.

One full ranking per contest produces both:

- contest-level top-1 and winner mean reciprocal rank over 61 contests;
- 243 winner-vs-visible-non-winner comparisons derived from that ranking.

The required slices are reported independently:

- all 61 contests;
- 52 contests after excluding the repeated `simbans` client cluster;
- 206 preference pairs after excluding 37 same-designer pairs.

## Build and validate the fixture

```bash
python3 scripts/build_fixture.py
```

The builder verifies all source images against their declared SHA-256 and byte
size. It removes only captured 99designs page chrome beginning at the literal
`It all began with a design brief.` marker; it does not fill ellipses or invent
missing constraints. A leakage audit fails if a winner ID, winner designer, or
selection metadata survives into model-visible input.

## Run and score

```bash
python3 scripts/run_codex_rank.py --all --allow-model-usage --workers 2
python3 scripts/score.py
```

Every contest runs in an independent ephemeral Codex session. Images are copied
to a temporary A–E workspace for the invocation and are not duplicated in the
experiment output. Raw trace, stderr, prompt, response, timing, usage, and input
hashes are retained.

## Frozen identity

`results/freeze-manifest.json` pins the candidate configuration, fixture
datasets, output schema, fixture builder, runner, scorer, results, summary, and
aggregate prompt set by SHA-256. `results/prompt-manifest.jsonl` additionally
records the exact hash and byte size of every selected contest prompt. Codex
CLI exposes the model identifier but not a model-weights digest, so the
manifest records that field as unavailable instead of implying weight-level
reproducibility.

## Interpretation boundary

The gold label is a real commercial selection event, not proof of universal
design quality. Public non-winner previews are not known finalists or
low-quality negatives. Selection rationales are absent for 61/61 cases, 60/61
briefs contain ellipses, previews are 500 px presentation-board crops, and the
industry mix is 52 Travel & Hotel plus 9 Art & Design. Therefore this benchmark
measures recovery of observed winner preference from visible evidence; it does
not measure complete brief adherence.

Rights remain `permission_required` / `not_cleared`. Keep pixels and derived
fixtures local; do not use them for training, distillation, redistribution, or
publication without permission.
