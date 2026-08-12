# Design Agent v0 — Routing Eval Baseline

_Endpoint: `POST /api/search-template-match` (Section-B matcher) · 100 queries · auto-generated._

## Headline

- **Match rate** (≥1 template returned): **96%** (96/100) — 4 queries return NOTHING.
- **Candidate-template recall** (queries w/ labeled candidates, n=77): mean **27%**; any-hit **34%**.
- **Intent overlap** (matched output_intent ∩ expected_route_intents, n=96): **34%**.
- **Mean top confidence**: 0.79.

## Match rate by coverage class

| coverage | n | match-rate | mean top-conf |
|---|---|---|---|
| adjacent | 42 | 95% | 0.78 |
| direct | 35 | 100% | 0.82 |
| gap | 23 | 91% | 0.75 |

## Match rate by specificity

| specificity | n | match-rate | cand-recall(any) |
|---|---|---|---|
| broad | 7 | 100% | 0% |
| medium | 46 | 96% | 46% |
| specific | 47 | 96% | 26% |

## Zero-match queries → build roadmap (4)

- `TIQ-017` **城市文旅品牌logo和辅助图形** (medium/adjacent/品牌)
- `TIQ-045` **唐代仕女三头身潮玩手办** (specific/adjacent/文创)
- `TIQ-054` **书法字体文具礼盒** (medium/gap/文创)
- `TIQ-086` **木质家具材质特写详情图** (specific/gap/电商设计)
