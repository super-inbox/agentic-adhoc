# Codex on Design Agent Brief Bank v0.2

This experiment runs Codex CLI against the 24 v0.2 business episodes and their 32 projected
context conditions. It is a Codex-only baseline; no Curify or other Agent output is exposed to the
candidate.

## Candidate

- Agent: Codex CLI
- Model: `gpt-5.6-sol`
- Reasoning effort: `max`
- Service tier: `default`
- CLI: recorded per run
- Thread protocol: one fresh persisted Codex thread per condition; later client feedback resumes
  only that thread

## Information boundary

Turn 0 receives only:

- the condition-specific query;
- inputs allowed by that condition;
- input roles and reference identity policies;
- text/spec inputs and client constraints;
- preference memory only for `personalized` conditions;
- the candidate-side output interface.

It does not receive future client feedback, expected changes, evaluator workflow checkpoints,
rubric weights, hard gates, or any competing Agent result. Later feedback is revealed one turn at a
time. The full runner records `future_feedback_visible_at_turn_0: false` in every result.

## Trajectory policy

The raw Codex JSONL trace is retained under ignored `.private/` paths for local debugging. The
publishable `trajectory.jsonl` contains observable agent messages, command/tool events, state/turn
boundaries, and token usage. Reasoning items, command output bodies, private chain-of-thought, local
user paths, and Codex runtime paths are excluded.

## Run

From this experiment directory:

```bash
# Validate selection, fixture hashes, and intended turn count without model usage
node scripts/run_codex_v02.mjs --all --full-episode --dry-run

# One complete condition, including all feedback turns
node scripts/run_codex_v02.mjs \
  --condition DAB-L4-CFR-003@reference_grounded \
  --full-episode \
  --allow-model-usage

# All 32 conditions; safely skip successful conditions from an interrupted batch
node scripts/run_codex_v02.mjs \
  --all \
  --full-episode \
  --skip-completed \
  --allow-model-usage
```

`--initial-only` is available for the 32-row query projection, but it must not be reported as a
v0.2 workflow result because it omits feedback handling and state continuity.

## Status

Checkpoint captured on 2026-08-24 after resumed-batch Run 17/30:

- 17/32 primary conditions completed successfully;
- 2/32 reached the candidate turn timeout and are retained as reliability/efficiency evidence;
- 13/32 still have earlier infrastructure-error rows and remain to be rerun;
- the next condition is `DAB-L4-CFRY-003@reference_grounded`.

The live runner was interrupted during that next condition before it could be archived, so its
partial raw events remain only under ignored `.private/` storage and are not part of this public
checkpoint. `run-index.jsonl` is the authoritative public attempt ledger. Resume with
`--skip-completed`; successful conditions will not be rerun.
