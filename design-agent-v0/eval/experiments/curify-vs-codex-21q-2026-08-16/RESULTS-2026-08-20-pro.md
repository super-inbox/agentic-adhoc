# 21q re-run — fresh generation on `aca1f491`, gemini-2.5-pro judge (2026-08-20)

First end-to-end measurement of this week's fixes. **New artifacts** generated
against a local build of `main@aca1f491`, not a re-judge of the 2026-08-16
export. Judge is `gemini-2.5-pro` on **both** candidates.

Validated before any score was read — 0 structural problems, 42 records,
curify `run_dir` under `scripts/runs`, codex under `candidates/codex`, no
zero-artifact case, **30 assets loaded (was 21)**.

## Headline

| | curify-web@aca1f491 | codex-cli |
|---|---:|---:|
| weighted_design_mean | **0.383** | 0.565 |
| benchmark_total_mean | **0.199** | 0.316 |
| case passes | **2** | 4 |
| median latency | 37.6 s | 151.3 s |
| judge completed | 20/21 (1 blocked) | 18/21 (3 blocked) |

## Codex as a control — separating judge effect from build effect

Codex's artifacts were **not regenerated**. Its flash→pro change is therefore
pure judge-model effect, and it calibrates the comparison:

| metric | codex Δ (control) | curify expected if unchanged | curify actual | **build effect** |
|---|---:|---:|---:|---:|
| weighted_design_mean | −0.102 | 0.295 | 0.383 | **+0.088** |
| benchmark_total_mean | −0.111 | 0.030 | 0.199 | **+0.169** |

pro grades ~0.10 harder than flash on identical work. Read raw pro numbers
against pro only; the 2026-08-18 flash figures are not comparable.

**Gap to Codex narrowed 0.269 → 0.181 (−0.088).**

## Hard gates

| gate | curify (was) | curify (now) | codex |
|---|---:|---:|---:|
| **all_inputs_consumed** | 14/21 | **21/21** ✅ | 21/21 |
| production_gate | 14/21 | 14/21 | 15/21 |
| judge_no_fatal_issues | 12/21 | 12/21 | 17/21 |
| completed | 16/21 | 16/21 | 20/21 |
| **artifact_contract** | 11/21 | **11/21** ❌ | 13/21 |

**`all_inputs_consumed` is the confirmed win**: 14/21 → 21/21, with all 30
assets uploaded and consumed. Multi-reference works end to end — UI, runner,
and agent.

**`artifact_contract` is unchanged at 11/21.** It was never worked on (P0-6),
and this confirms it is a real, independent defect rather than a side effect of
the reference bug. Same for `completed` at 16/21.

## Per-metric (pro judge, both sides)

| metric | curify | codex |
|---|---:|---:|
| brief_adherence | 0.100 (n=20) | 0.322 (n=18) |
| visual_quality | 0.500 (n=20) | 0.711 (n=18) |
| refinement_ability | 0.300 (n=8) | 0.275 (n=8) |
| production_readiness | **0.563** (n=21) | 0.762 (n=21) |
| efficiency | 1.000 (n=21) | 0.813 (n=21) |
| weighted_design_score | 0.370 (n=21) | 0.509 (n=21) |

`refinement_ability` is the one metric where curify now leads (0.300 vs 0.275),
but n=8 per side — **too small to claim anything**.

`brief_adherence` 0.100 vs 0.322 remains the substantive gap, and it is
**not** explained by any bug fixed this week. This is the generation-quality
problem, and it is where the remaining 0.181 lives.

## What this run establishes

1. Multi-reference input is fixed and consumed — the single clearest result.
2. The build genuinely improved once the judge shift is controlled for
   (+0.088 weighted, +0.169 total), and the gap to Codex closed by a third.
3. `artifact_contract` (11/21) and `completed` (16/21) are untouched and are now
   the largest remaining gated losses — both fixable without a judge.
4. Curify still wins only efficiency, and only on latency against a 120 s budget.

## Caveats

- Build is `main@aca1f491`, **ahead of production**. These numbers describe a
  build users do not have until it merges.
- 1 curify and 3 codex cases were judge-blocked; means are over n=20/n=18.
- `refinement_ability` n=8 per side.
- The runner reports `estimated_credits_spent: 10` per case; generation is 5
  since `a6e6b1ba`, so the recorded figure is ~2× the real spend.

Reproduce:

```bash
CURIFY_CANARY_BASE_URL=http://localhost:3100 \
CURIFY_CANARY_COMMIT=aca1f491 \
node scripts/run_curify_benchmark.cjs --all-benchmark --allow-paid-generation
CURIFY_RUNS_ROOT=$PWD/scripts/runs \
python3 scripts/run_full_comparison.py --candidate both --judge-model gemini-2.5-pro
```
