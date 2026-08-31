# Reddit demand corpus → audited brief seeds

> ⚠️ **This copy is pending removal.** Per the `8a52dab` split (evaluation / data /
> trajectories live in `agentic-adhoc`), everything here is also in
> `agentic-adhoc/design-agent-v0/eval/reddit_briefs/` via **PR #8**.
> **When that PR merges, delete this directory** so there is one copy, not two.

Public-corpus material for the L3/L4 brief bank. Everything here derives from a single
fetch of public Reddit submissions; there is no customer data in this directory.

| file | what it is |
|---|---|
| `reddit_corpus_2026-08-18.json` | 362 posts, 6 subreddits, title-search fetch via arctic-shift. Fields: `h` (hypothesis the query tested), `sub`, `term`, `title`, `score`, `nc`, `text`. |
| `analyze.py` | pass 1 — §7m pain-hypothesis hit rates + tool mentions. ⚠️ reads a hardcoded `raw.json`; copy or rename the corpus first. |
| `trajectory_scan.py` | pass 2 — can end-to-end decision trajectories be harvested? (2/362) |
| `segment_scan.py` | pass 3 — can process *segments* be harvested? (80/362, S1 only) |
| `task_scan.py` | pass 4 — are there stateable design **tasks**? (118/362 task-shaped) |
| `reddit_brief_seeds_2026-08-30.raw.jsonl` | the 35 hand-extracted seeds, **pre-audit**. Kept for auditability; do not consume it. |
| `audit_seeds.py` | the strict audit — one verdict per seed, with the reason |
| **`reddit_brief_seeds_2026-08-30.jsonl`** | **the output: 20 kept** — 17 cases (L3 8 / L4 9) + 3 reference records |
| `reddit_seeds_rejected_2026-08-30.jsonl` | the 15 rejected, each with `rejected_because`. Still countable as demand signal. |

```bash
python3 task_scan.py reddit_corpus_2026-08-18.json 6 > candidates.txt
python3 audit_seeds.py reddit_brief_seeds_2026-08-30.raw.jsonl   # regenerates both outputs
```

## The audit (2026-08-31): 35 → 20

The first pass over-kept. Three rules cut it down; `audit_seeds.py` carries the reason
for every one of the 35.

1. **Design job, or tool complaint?** *"`--sref` won't hold my character across outfits"*
   is a real need — identity surviving an attribute change — wearing one product's
   controls. Build an eval case from it and you measure *"can we do what Midjourney
   can't"*, which is not the benchmark §7m set out to build. **7 rejected.**
2. **Is there a criterion?** A request whose deliverable is an opinion with no stated
   standard (*"which logo do you prefer?"*) cannot be scored — there is nothing for a
   judge to check an answer against. **3 rejected.**
3. **Would the fixture have to be invented wholesale?** If we author the prior artifact,
   the difficulty becomes whatever we authored and the corpus grounding is gone. Rejected
   unless the fixture is generic (any two images, a road photo). **5 rejected.**

**`level` was re-derived from the shape of the task, not the completeness of the post.**
The raw pass labelled 18 of 35 as L4, but only 8 carried client feedback and 4 carried a
selection — most were L3 batch work wearing an L4 label. After the audit: **L3 8 / L4 9.**

**Three kept records are not cases.** A gold artifact (`RBS-SEL-001`), a verification
checklist (`RBS-PSF-003`) and a deliverable-scope definition (`RBS-CFRY-004`) carry
`record_type: reference_material`, no `level`, and no `input_brief` in `eval_use`, so
nothing downstream mistakes them for briefs.

## Seed schema (`schema_version: seed-0.2`)

Field names align with `brief_bank/briefs.v0.2.jsonl` where they overlap
(`level`, `category`, `primary_intent`, `secondary_intents`, `language`, `provenance`).
Seed-only fields:

- `observed_task` — the job the poster actually had, in our words
- `observed_failure` — **what broke**; the field synthetic briefs cannot invent
- **`constraints_stated` vs `constraints_inferred`** — v0.2 of the schema splits these.
  In v0.1 they sat in one array at equal weight, so a consumer could not tell where the
  post stopped and we started. **35 stated / 19 inferred** across the kept set — a third
  was our reading. Same discipline as §7z: recording an absence is data, inventing a
  reason is contamination.
- `vernacular` — short operator phrases, for brief *wording* and landing-page copy. Per
  `build_briefs.py`'s rule these are never pasted into a brief body.
- `chain` / `eval_use` — which links of the §7r-F gradient are present, and what the
  record may be used for
- `brief_readiness` — `ready_to_author` (11 cases) vs `needs_fixture_assets` (6)
- `audit.kept_because` — why this one survived

`provenance.kind` is `public_corpus_grounded`, a fourth kind alongside the bank's
`reverse_constructed` / `controlled_synthetic` / `internal_scenario`. `customer_data` is
`false` throughout.

**Do not sort by `provenance.score`.** Reddit score tracks how much a post was
*discussed*, and the discussed posts are disproportionately rants. `RBS-REF-003`, one of
the best records here, scores 1. The field is for traceability, not weight.

## What this corpus can and cannot supply

**Can:** input briefs, real failure conditions, reference-contract cases, operator vocabulary.

**Cannot:** decision trajectories (2/362), multi-option ranking (4 genuine cases in 362 —
after the audit only **1** survives with a stated criterion), client feedback verbatim in
a brief context. Those come from `../real-projects/`.

**The intent axis is lopsided and should not be bulk-imported.** Kept cases run
generate 6 / edit 5 / export 4 / evaluate_rank 1 / adapt 1, against v0.2's deliberate
5/5/5/5/4. That skew is a faithful picture of the corpus, not a defect in it — but
appending all 17 would unbalance the bank's second axis.

Findings and caveats: `curify-studio/docs/reddit-design-problem-extraction-2026-08-30.md`
(spec §7aa). Fetch-path notes (reddit.com 403s, pullpush 429s, arctic-shift pacing) are in
`curify-studio/docs/reddit-demand-mining-design-agent-2026-08-18.md`.
