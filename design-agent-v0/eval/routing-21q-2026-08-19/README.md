# 21q routing eval — 2026-08-19 (no generation, no credits)

Measures **only what the planner decides**, by POSTing each of the 21 briefs to
the live `/api/design-agent/plan` on `www.curify-ai.com` with `hasImage: true`.
P0-2 (edit intent) and P0-3 (export step) are routing changes, so they are fully
observable without generating anything.

**What this cannot tell you:** `brief_adherence`, `visual_quality`,
`artifact_contract`, `all_inputs_consumed` — every one of those needs real
artifacts. This is not a substitute for the paid run; it is the half that can be
measured for free, and it is the half that P0-2/P0-3 actually changed.

Expected intents come from the judge rationales recorded in spec §7o, not from
the pattern under test, so this does not mark its own homework.

## Result: 19 pass · 1 fail · 1 known-miss

| Group | Outcome |
|---|---|
| **Edit (class A)** | **11/12** route to `edit` → `generate_freeform`. Was 3/12 before P0-2. |
| **Export (class D)** | **3/3** now plan `export_print_package`. Was 0/3 — the step existed but had no client branch. |
| **Evaluate (class B)** | 3/3 stay out of `edit` — the guard holds. **None is routed correctly**; see below. |
| Batch / generate | 2/2 unchanged |

## The one real failure: TIQ-070

`把白底商品图换成高级感场景` — "replace the white background with a premium
scene". Unambiguously an edit; routed `single`. `EDIT_MODIFY_RE` covers
`换背景` / `换个?背景` / `背景色` but not `…换成…`, which is the more natural
Chinese phrasing here.

⚠️ **Do not reflexively "fix" this.** TIQ-070 scored `brief_adherence` **1.0** in
the corrected 2026-08-18 run — one of only two cases that passed. The template
path demonstrably works for it, and rerouting it to image-to-image could regress
a passing case. The honest position is that the pattern is incomplete AND that
this particular case is not evidence of harm. Decide it with the paid run, not
from the regex.

## Known miss, as documented

`TIQ-086` (`木质家具材质特写详情图`) has no edit verb at all. Spec §7o records
that it needs prompt-level reference anchoring rather than routing; it is scored
here as a known miss rather than quietly counted as a pass.

## Class B is passing on a technicality

The evaluate cases are scored only as "not mis-routed to edit". That guard
works, but none is routed *correctly* because no evaluate/rank deliverable type
exists. `AR-004` is the clearest tell — it lands in `batch` because `4款`
matches `BATCH_RE`, and plans:

    generate_from_template → compose_grid → export_print_package

for what is a request to judge four supplied packaging designs. It will not
produce a ranking. Counting this as a pass would overstate the state of class B.

## Reproduce

    python3 route_eval.py     # writes results.json

21 planner calls; server-side LLM spend only, no image credits.
