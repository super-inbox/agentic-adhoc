# Codex × 99designs evaluate/rank — results

Candidate: `{"agent": "codex-cli", "cli_version": "codex-cli 0.146.0", "model": "gpt-5.6-sol", "reasoning_effort": "max", "sandbox": "read-only", "session_mode": "ephemeral"}`

Fixture: `de871a55b8dc9d1bb93b0f439f2cb19efb8fafb69871d56d0bea335540b0abc0` (61 contests) / `f82017430e2854dc092809da87fdebf5e69d16e22e5dcf60000be53b6a4461b0` (243 derived pairs)

## Headline

| Slice | n | Completion | Top-1 / pair accuracy | 95% clustered bootstrap CI | Winner MRR |
|---|---:|---:|---:|---:|---:|
| All contests | 61 | 61/61 | 23.0% (14/61) | [13.1%, 34.4%] | 0.521 |
| Exclude `simbans` | 52 | 52/52 | 21.2% (11/52) | [11.5%, 32.7%] | 0.518 |
| All winner pairs | 243 | 243/243 | 63.0% (153/243) | [55.4%, 70.1%] | — |
| Exclude same-designer pairs | 206 | 206/206 | 63.6% (131/206) | [55.1%, 71.8%] | — |

Random expectation for within-contest top-1 is 20.1%; pairwise is 50.0%.

## Reliability and leakage controls

- Selected valid rankings: **61/61**
- First-attempt completion: **61/61**
- Retried contests: **0**
- Planner-only/no-tool invariant: **100.0%**
- Predicted best-position distribution: `{'A': 17, 'B': 12, 'C': 9, 'D': 12, 'E': 11}`
- Winner rank distribution: `{'1': 14, '2': 20, '3': 15, '4': 8, '5': 4}`
- Mean self-reported confidence **84.6%** vs top-1 accuracy **23.0%**; Brier **0.561**.
- Same-designer pairs: **59.5%** (22/37); different-designer pairs: **63.6%** (131/206).
- Sum of independent case latency **1531.6s**, mean **25.1s**; CLI usage `{'input_tokens': 998672, 'cached_input_tokens': 204288, 'cache_write_input_tokens': 0, 'output_tokens': 69018, 'reasoning_output_tokens': 56448}`.

## By design type

| Design type | contests | clients | top-1 | MRR | pair acc. |
|---|---:|---:|---:|---:|---:|
| Art & Illustration Design | 5 | 5 | 20.0% | 0.517 | 65.0% |
| Banner Design | 9 | 1 | 33.3% | 0.541 | 57.1% |
| Brand Design | 14 | 14 | 14.3% | 0.427 | 50.0% |
| Environmental & Signage Design | 3 | 3 | 33.3% | 0.611 | 75.0% |
| Merchandise Design | 6 | 6 | 16.7% | 0.506 | 62.5% |
| Packaging & Label Design | 6 | 6 | 16.7% | 0.542 | 70.8% |
| Print & Editorial Design | 12 | 11 | 41.7% | 0.632 | 72.9% |
| Web & App Design | 6 | 6 | 0.0% | 0.444 | 66.7% |

## Interpretation boundary

- This is observed-winner preference recovery, not an objective design-quality score.
- Non-winner previews are neither known finalists nor known low-quality negatives.
- Selection rationale is unavailable for 61/61; 60/61 briefs retain source ellipses.
- 52/61 contests are Travel & Hotel; the 9 Banner cases are one repeated `simbans` client.
- The 243 pair results are derived from 61 multi-option rankings, not 243 independent model calls.
- Confidence intervals resample whole contests so four pairs from one ranking are not treated as independent.
- Rights are not cleared for redistribution or training; this remains a local evaluation artifact.
