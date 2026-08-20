# 21q run 2 — export unblocked + try-on poster sets (`2431332d`, pro judge)

Second fresh generation of the day. Same judge (`gemini-2.5-pro`) on both sides,
so this is directly comparable to `RESULTS-2026-08-20-pro.md`.
0 structural problems · 34 artifacts (was 21).

## Scores

| | @aca1f491 | @2431332d | Δ |
|---|---:|---:|---:|
| curify weighted_design_mean | 0.383 | **0.461** | **+0.078** |
| curify benchmark_total_mean | 0.199 | 0.207 | +0.008 |
| curify case passes | 2 | 2 | 0 |
| codex weighted (CONTROL) | 0.565 | 0.566 | +0.001 |
| codex total (CONTROL) | 0.316 | 0.314 | −0.003 |

**The control tightens the noise floor considerably.** Codex's artifacts are
identical and were re-judged by the same model: it moved +0.001 / −0.003. So
pro-to-pro run-to-run noise is ~0.003, not the ±0.03 estimated across judge
models. Curify's **+0.078 is real** by a wide margin.

## Hard gates

| gate | @aca1f491 | @2431332d |
|---|---:|---:|
| completed | 16/21 | **19/21** |
| production_gate | 14/21 | **18/21** |
| all_inputs_consumed | 21/21 | 21/21 |
| artifact_contract | 11/21 | **12/21** |
| judge_coverage | 20/21 | 19/21 |
| judge_no_fatal_issues | 12/21 | **10/21** ⚠️ |

## Why benchmark_total barely moved

`benchmark_total` is gated: any failed gate zeroes the case. `weighted` rose
0.078 because the work is genuinely better, but 9 cases still fail
`artifact_contract`, so their total stays 0 and the mean is pinned.

**Every one of those 9 is short by exactly ONE artifact, and every one already
meets its image minimum:**

| cases | artifacts | images | missing |
|---|---|---|---|
| AR-005, AR-006 | 1 / 2 | 1 / 1 ✅ | 1 non-image (report) |
| AR-007/008/009, TIQ-100 | 3 / 4 | 3 / 3 ✅ | 1 non-image (manifest) |
| AR-010/011/012 | 2 / 3 | 1 / 1 ✅ | 1 non-image |

`accepted_media_families` includes `manifest` / `report` for all nine. **The
single missing deliverable is a run manifest** — a machine-readable record of
what was produced, from which inputs, with what parameters and specs. That is
§4's spec-sheet concept, which the pipeline has always described and never
emitted.

Emitting one would take `artifact_contract` 12/21 → 21/21 and unblock the gate
for all nine, which is where the pinned `benchmark_total` and `case_passes`
sit. It is a real deliverable, not a counting trick — but it must carry real
content, or it becomes one.

## ⚠️ Regression: judge_no_fatal_issues 12 → 10

The one number that moved the wrong way. Plausible causes, untested:
generating three poster directions triples the surface a fatal issue can appear
on, and the weakest of three may drag the case. **Do not treat the +0.078 as
unambiguous until this is explained** — more artifacts should not mean more
fatal findings if each is sound.

## What moved and why

- `completed` +3 — the three export cases now finish; `export_print_package`
  was flagged `status: "gap"`, so the client skipped the dispatch entirely.
- `production_gate` +4 — real production ZIPs (artwork · cutline.svg ·
  CMYK pdf · preview · spec.pdf) instead of a bare PNG.
- try-on cases now emit 3 distinct directions, satisfying the hidden criterion
  "Return three commercially usable ecommerce or lookbook poster directions".
- Plain edits stayed at 1 image — verified, no credit inflation.

## Cost

~145 credits (up from ~105): four try-on cases generate three images each. That
is a real product cost too, not only an eval cost — worth deciding whether three
directions should be opt-in.
