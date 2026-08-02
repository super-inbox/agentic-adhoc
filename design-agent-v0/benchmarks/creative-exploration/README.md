# Creative Exploration — benchmark cases

A **capability** of Design Agent v0 distinct from routing / generation / factory:
the agent doesn't just make *one* asset — it explores a **design space** (N variants),
runs a **simulated consumer panel** to score them on a subjective axis, and returns a
**clean decision graphic**. This is the "which one is better?" loop designers actually
run with clients.

## The loop (what the agent must do)

```
brief + variant set  ->  UNDERSTAND      (vision: read each variant's design language;
                                           LLM: name the axis being judged, e.g. 质感/premium)
                     ->  SEGMENT          (LLM: define plausible consumer segments + population weights
                                           for THIS product category — men's grooming ≠ kids' toys)
                     ->  SIMULATE PANEL   (per segment, score each variant on the axis;
                                           reason from design cues -> preference distribution)
                     ->  AGGREGATE        (weight by segment share -> overall ranking + winner)
                     ->  PRESENT          (deterministic viz: variant thumbnails + %, winner highlight,
                                           per-segment breakdown; minimal text; brand watermark)
```

Two-layer split holds: **LLM plans** (axis, segments, per-segment preference reasoning);
**code renders** the infographic deterministically (PIL, never AI-drawn text — CJK-safe).

## Why it's a good benchmark

- **Subjective axis, defensible reasoning** — tests whether the agent can tie *design cues*
  (brand placement, hierarchy, whitespace) to *segment preference* with a tellable story,
  not just emit random numbers.
- **Category-conditioned segments** — the segment set + weights must fit the product; a
  generic panel is a fail.
- **Output discipline** — "整洁、干净、文字不要太多": the presentation layer is graded on
  restraint, not completeness.
- **Honest framing** — simulated ≠ real. The graphic must label it (`模拟投票 · 加权合成`),
  and the agent should offer to swap in real votes when available.

## Cases

| id | brief | variants | axis | winner | assets |
|---|---|---|---|---|---|
| `faceo-packaging-2026-07` | FaCeo 男士洁面泡沫 packaging | 4 (A/B/C/D) | 质感 / premium feel | D款 43% | [dir](faceo-packaging-2026-07/) |

## Eval dimensions (for scoring the agent's output)

1. **Segment plausibility** — are the segments + weights right for the category?
2. **Reasoning fidelity** — does each variant's score follow from its actual design cues?
3. **Ranking sanity** — winner + spread defensible to a human designer?
4. **Presentation** — clean, minimal-text, correct labels, honest ("simulated") framing?
5. **Actionability** — does the client get a clear go decision + why?

v0 baseline case (`faceo-packaging-2026-07`) was produced semi-manually (crops + weighted
panel + PIL render in `curify-frontend/raw/creative-exploration-07-29/build_vote.py`); the
agent target is to run the whole loop from `brief + variant image` with no hand-authoring.
