# agent_runtime skills verified against production (2026-08-22)

Both skills that `DesignAgentClient` now hands turns to were run against the
deployed backend before relying on them. Neither was reachable from the product
until `a94a9e9e`.

## design-vote — `design_agent_033bda777e5941be`

`allow_paid_generation: false` · **cost: nothing** (deterministic render over the
supplied board).

    status COMPLETED · task_type design_vote (auto-inferred) · skill design-vote
    trace  UNDERSTAND → PLAN → GENERATE → VERIFY → PRESENT · verdict passed
    artifacts 2
      design-vote-report.png     image/png         (kind: report)
      design-vote-analysis.json  application/json  (kind: manifest)

Satisfies AR-005/006 (`minimum_artifacts: 2`, `minimum_image_artifacts: 1`).

## tryon-poster — `design_agent_8e983a78cc27432a`

`allow_paid_generation: true` · 2 images in (selfie + garment).

    status COMPLETED · task_type tryon_poster · skill tryon-poster
    iterations 2 · verdict passed
    summary "已生成 3 张商品参考试穿电商海报，并通过视觉校验"
    trace  UNDERSTAND → PLAN → GENERATE → VERIFY → VERIFY
                      → PLAN → GENERATE → VERIFY → VERIFY → PRESENT
    artifacts 4
      tryon-poster-1.jpg / -2.jpg / -3.jpg   image/jpeg
      tryon-manifest.json                    application/json  (kind: manifest)

Satisfies AR-007/008/009 and TIQ-100 exactly — `minimum_artifacts: 4`,
`minimum_image_artifacts: 3`.

**The two PLAN→GENERATE→VERIFY cycles are the retry loop working**: it generated,
verified, found a failure, re-planned and regenerated only what failed. That is
the behaviour `judge_no_fatal_issues` rewards, and it is what the client's
hand-rolled three-direction expansion (`2431332d`) lacked.

## Consequence for artifact_contract

Six of the nine 21q failures are resolved by wiring already committed, with the
manifest included natively rather than built:

| cases | contract | runtime output |
|---|---|---|
| AR-005 / AR-006 | 2 artifacts, 1 image | 2 ✅ report + manifest |
| AR-007/008/009, TIQ-100 | 4 artifacts, 3 images | 4 ✅ 3 posters + manifest |
| AR-010/011/012 | 3 artifacts, 1 image | 2 ⚠️ still one short |

The export cases remain the gap: the ZIP plus its generated image is 2, and the
contract wants 3.
