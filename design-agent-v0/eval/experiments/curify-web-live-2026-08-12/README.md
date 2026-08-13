# Curify deployed Design Agent — 21-case live evaluation

This is the sanitized, versioned publication of the live Curify web-product evaluation run on
2026-08-12. It evaluates the deployed [`/design-agent`](https://www.curify-ai.com/design-agent)
surface, including its one-image upload boundary, planner, browser-side execution, visible terminal
states, generated artifacts, and verification behavior.

## Outcome

| signal | result |
|---|---:|
| cases | 21 |
| complete / partial / blocked | 16 / 5 / 0 |
| program-level errors | 0 |
| output image artifacts | 21 |
| mean latency | 35.3 s |
| weighted design score | 36.2% (`n=16` judgeable outputs) |
| hard-gated benchmark total | 12.2% (`n=21`) |
| benchmark pass | 0 / 21 |

The main finding is a separation between rendering quality and agent task success. Seven of the 16
judgeable outputs scored at least 4/5 on visual quality, while 14/16 scored zero on brief adherence.
The current product can often render a polished template, but it frequently does not execute the
requested edit, comparison, try-on, batch, or production-file operation.

See [`ANALYSIS.zh-CN.md`](ANALYSIS.zh-CN.md) for the diagnostic interpretation and recommended
implementation priorities.

## Protocol

| field | value |
|---|---|
| Braintrust project | `design-agent-benchmark` |
| Dataset | `design-agent-bench-v0.1-multimodal-pilot` |
| Benchmark | `v0.1-pilot` |
| Protocol | `single-turn-v1` |
| Input pack | `reference-pack-v0.2` |
| Target | deployed `curify-web` |
| Runtime | live |
| Judge | independent `judge-v2`, live `gemini-2.5-pro` |
| Trials | 1 per case |

The shared Dataset contains the agent-neutral brief, input roles, success criteria, negative
constraints, deliverable contract, rubric, and budget. Curify-specific routes, template matches,
step states, and omitted inputs are Experiment output diagnostics, not Dataset labels. Judge-v2
receives source/output pixels and the task contract, but not Curify routes, traces, confidence, or
self-reported verdicts.

## Braintrust provenance

- [Consolidated 21-case experiment](https://www.braintrust.dev/app/curify/p/design-agent-benchmark/experiments/curify-web__bench-v0.1-pilot__protocol-web-single-turn-v1__judge-v2__consolidated-21-v1)
- [Initial source experiment](https://www.braintrust.dev/app/curify/p/design-agent-benchmark/experiments/curify-web__bench-v0.1-pilot__protocol-web-single-turn-v1__judge-v2-e2b37aa5)
- [15-case top-up source experiment](https://www.braintrust.dev/app/curify/p/design-agent-benchmark/experiments/curify-web__bench-v0.1-pilot__protocol-web-single-turn-v1__judge-v2-a8c98468)

The first paid all-case attempt produced six artifacts before the shared test account ran out of
credits. After credits were added, only the remaining 15 cases were run. The consolidated
experiment replays those 6 + 15 existing roots and scores; it does not call Curify or Gemini again.
Full nested traces remain in the two source experiments. `TIQ-088` received a judge-only retry after
the first Gemini response omitted one required dimension.

The final 21 output generations consumed 210 Curify credits. A separate one-case canary consumed 10
credits and is not included in the final 21-case score.

## Files

| file | purpose |
|---|---|
| [`dataset.jsonl`](dataset.jsonl) | 21 agent-neutral cases with sanitized v0.2 asset bindings |
| [`input-manifest.jsonl`](input-manifest.jsonl) | 18 fixture IDs, hashes, dimensions, provenance, and relative pack paths |
| [`results.jsonl`](results.jsonl) | 21 sanitized outputs, traces, diagnostics, and scores |
| [`aggregate.json`](aggregate.json) | machine-readable aggregate, latency, capability slices, URLs, and limitations |
| [`ANALYSIS.zh-CN.md`](ANALYSIS.zh-CN.md) | Chinese result analysis and prioritized follow-up plan |

Signed result URLs, local absolute paths, browser storage state, tokens, API keys, and test-account
identity are intentionally excluded. Exact source and output pixels remain as access-controlled
Braintrust attachments; this result snapshot stores fixture hashes rather than duplicating binaries.

## Score interpretation

`weighted_design_score` is computed only for the 16 completed, judgeable outputs. The
`benchmark_total_score` is computed over all 21 cases and becomes zero when a hard gate fails, such
as incomplete artifacts, omitted inputs, missing production requirements, incomplete judge
coverage, or fatal brief contradictions. These two means therefore have different denominators and
must not be compared as if they were the same population.

The published `target_capability_coverage`, `target_stage_coverage`, `reference_fidelity_gate`, and
`efficiency` fields retain the scorer-v2 implementation used during the run. Their naming and
semantics require refinement before an external-agent leaderboard; the caveats are documented in
the analysis.
