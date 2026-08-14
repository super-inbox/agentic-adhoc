# Canva vs Curify canary — 2026-08-14

This directory records manually observed Canva responses to the agent-neutral
`design-agent-bench-v0.1-multimodal-pilot` cases. The capture date is 2026-08-14.

The records combine UI observations with the original AR-001 and AR-008 files downloaded from
Canva. A blind judge-v2 comparison was attempted after the raw files arrived, but Gemini rejected
the first request because the project had exceeded its monthly spending cap. The deterministic
contract comparison remains valid; numeric visual scores remain pending.

## Recorded cases

| Case | Canva terminal status | Benchmark delivery | Main observation |
| --- | --- | --- | --- |
| AR-001 | `COMPLETED` | `DELIVERED` | Canva enlarged “SUMMER FORM” modestly while preserving the rest of the poster and adding no unrelated brand mark. One original output file is stored under `artifacts/canva/`. |
| AR-008 | `COMPLETED` | `PARTIAL` | Both UI-visible try-on originals are stored. The first broadly preserves the supplied person; the second changes the person to a different model. Both show a related navy bomber but invent a sleeve zipper pocket. The benchmark asks for three image directions plus a manifest. |
| AR-006 | `COMPLETED` | `PARTIAL` | Canva selected D, named B runner-up, and discussed A-D using visible design evidence. It did not provide a full 1-4 ranking, identify the result as an AI simulation, or return the required image/report deliverables. |
| TIQ-088 | `NEEDS_INPUT` | `NOT_DELIVERED` | Canva recognized the reference page and product, then asked for missing replacement copy. No design was generated. The benchmark row itself is underspecified because the brief refers to “我的文案” but supplies no copy asset or copy fields. |

## Interpretation rules

- `Canva terminal status` describes what Canva did, independently of the benchmark contract.
- `Benchmark delivery` compares only observable output against the Dataset deliverable contract.
- `manual-results.jsonl` contains no inferred judge-v2 scores. Unknown latency, cost, trace, and raw
  file properties remain `null` rather than being guessed.
- UI screenshots live under `evidence/` and are classified as non-scoring evidence.
- Downloaded output files live under `artifacts/` and may be sent to judge-v2.
- `canva-vs-curify.comparison.json` and the accompanying summary separate deterministic checks,
  manual visual findings, and unavailable judge-v2 scores.

## Follow-up required for a fair cross-agent comparison

1. Re-run AR-006 with a prompt that requests a complete 1-4 ranking and an explicit AI-simulation
   disclosure only if those requirements are made visible to every tested agent.
2. Add replacement copy to TIQ-088's input contract, or explicitly permit one clarification turn.
3. When judge capacity is available, score the frozen artifacts with the independent judge-v2
   harness without regenerating either Agent.
4. Record the remaining canary cases: TIQ-096 and AR-010.

This publication contains no API keys, browser session state, or account identity. The source
comparison runner is intentionally omitted; this directory is a frozen result-and-evidence snapshot.
