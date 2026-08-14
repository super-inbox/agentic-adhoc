# Codex vs Curify canary — 2026-08-14

This run evaluates Codex against the same agent-neutral Design Agent Benchmark rows and Curify web
artifacts used by the existing Phase 1 comparison.

## Candidate identity

- Agent: `codex-cli`
- CLI version: `0.146.0`
- Model: `gpt-5.6-sol`
- Reasoning effort: `max`
- Service tier: `default`
- Session mode: `codex exec --ephemeral`
- Visual tool path: built-in image generation/editing through the installed `imagegen` skill
- User configuration: loaded so the installed visual skill remains available

These fields describe the candidate as a complete Agent system, not only its base language model.

## Isolation protocol

Each case runs in a new temporary directory and receives only:

1. the exact benchmark query;
2. that row's source image files;
3. neutral operational instructions to finish in one turn and save final artifacts.

The candidate does not receive Curify outputs, prior scores, success criteria, negative constraints,
judge rubrics, or hidden artifact-count requirements. It is instructed not to inspect unrelated
files outside the isolated working directory. The trace shows that it reads only the installed
`imagegen` skill documentation outside that directory, which is part of the pinned Codex Agent
configuration. The session is ephemeral and is not resumed between cases.

## Canary scope

- AR-001: `把海报的标题放大一点`
- AR-008: `try on this jacket on my photo for a lookbook`

Every trial preserves its input copies, JSONL event trace, stderr, final response, elapsed time, and
whatever files the candidate saved under `outputs/`.

The first AR-001 harness attempt never reached the model because the CLI parsed the positional prompt
as an image argument. It is retained under `runs/ar-001/attempt-0-cli-arg-error/` and excluded from
candidate metrics. `trial-1` is the first valid candidate run.

## Published files

- `codex-vs-curify.summary.md`: evidence-based interpretation and limitations.
- `codex-vs-curify.comparison.json`: structured deterministic comparison.
- `manual-results.jsonl`: normalized candidate observations.
- `artifacts/`: frozen Codex and Curify output images used by the comparison.
- `runs/`: isolated Codex inputs, outputs, metadata, responses, logs, and JSONL execution traces.

## Independent judge status

The Gemini judge-v2 attempt was blocked by the source project's monthly spending cap. No numeric
visual score or official cross-Agent total is claimed. The frozen artifacts can be judged later
without regenerating either Agent. API keys, browser state, and other credentials are not included
in this publication.
