# Codex × external briefs 18 — results

Candidate: `{"agent": "codex-cli", "cli_version": "codex-cli 0.146.0", "model": "gpt-5.6-sol", "reasoning_effort": "max", "sandbox": "read-only", "session_mode": "ephemeral"}`

## Reliability

- Selected valid runs: **18/18**
- First eligible model-attempt completion: **18/18**
- Retried cases: **0**
- Excluded harness preflight failures: **36**

## Case-study workflow layer (11)

| Metric | Result |
|---|---:|
| Completion | 11/11 |
| Intent exact | 81.8% |
| Step F1 | 48.2% |
| Ordered LCS recall | 89.1% |
| Exact sequence | 0.0% |
| Weighted / gated mean | 0.625 / 0.625 |
| Passes | 1/11 |

This layer measures recovery of one documented case-study workflow from a newly
paraphrased task brief. It does not claim that the hidden sequence is the only
valid process and it does not measure design execution or final visual quality.

## ZCOOL portfolio-reference layer (7)

| Metric | Result |
|---|---:|
| Completion | 7/7 |
| Intent exact | 100.0% |
| Brief-class exact | 28.6% |
| Reference coverage | 100.0% |
| Deliverable-concept recall | 91.7% |
| Weighted / gated mean | 0.868 / 0.868 |
| Passes | 7/7 |

This is a low-resolution external-distribution planning canary. The published
portfolio thumbnails are outcome evidence, not a style instruction, workflow
gold, preference label, or permission to copy. No pixel-similarity score is used.

## Failed cases

- `BRF-BRAND-01` — gated=0.675; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-BRAND-02` — gated=0.675; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-BRAND-03` — gated=0.543; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-ECOM-01` — gated=0.664; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-ECOM-03` — gated=0.643; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-EDU-01` — gated=0.494; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-EDU-02` — gated=0.643; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-MERCH-01` — gated=0.630; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-MERCH-02` — gated=0.612; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}
- `BRF-PACK-01` — gated=0.456; gates={'schema_valid': True, 'tool_call_free': True, 'not_executed': True}

## Interpretation boundary

- Planner-only: no design generation/editing was requested or scored.
- Case-study labels describe one observed process, not universal ground truth.
- ZCOOL provides no rejected directions, client feedback, or hidden production files.
- Deterministic concept recall checks scope coverage, not taste or visual quality.
- External pixels remain internal-evaluation-only identification thumbnails.
