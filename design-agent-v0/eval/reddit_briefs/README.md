# Reddit demand corpus → brief seeds

Public-corpus material for the L3/L4 brief bank. Everything here is derived from a
single fetch of public Reddit submissions; there is no customer data in this directory.

| file | what it is |
|---|---|
| `reddit_corpus_2026-08-18.json` | 362 posts, 6 subreddits, title-search fetch via arctic-shift. Fields: `h` (hypothesis the query tested), `sub`, `term`, `title`, `score`, `nc` (comment count), `text`. |
| `analyze.py` | pass 1 — §7m pain-hypothesis hit rates + tool mentions. ⚠️ reads a hardcoded `raw.json`; copy or rename the corpus before running. |
| `trajectory_scan.py` | pass 2 — can end-to-end decision trajectories be harvested? (2/362) |
| `segment_scan.py` | pass 3 — can process *segments* be harvested? (80/362, S1 only) |
| `task_scan.py` | pass 4 — are there stateable design **tasks**? (118/362 task-shaped) |
| `reddit_brief_seeds_2026-08-30.jsonl` | **the output**: 35 hand-extracted design problems, L3 17 / L4 18 |

```bash
python3 task_scan.py reddit_corpus_2026-08-18.json 6 > candidates.txt
python3 trajectory_scan.py reddit_corpus_2026-08-18.json
python3 segment_scan.py  reddit_corpus_2026-08-18.json
```

## Seed schema

Field names align with `brief_bank/briefs.v0.2.jsonl` where they overlap
(`level`, `category`, `primary_intent`, `secondary_intents`, `language`, `provenance`)
so a seed becomes a brief without a translation step. Seed-only fields:

- `observed_task` — the job the poster actually had, in our words
- `observed_failure` — **what broke**; the highest-value field, and the one synthetic briefs cannot invent
- `constraints_observed` — constraints the post states or implies
- `vernacular` — short operator phrases, for brief *wording* and landing-page copy.
  Per `build_briefs.py`'s rule these are not to be pasted into a brief body.
- `chain` / `eval_use` — which links of the §7r-F gradient are present, and what the seed may be used for
- `brief_readiness` — `ready_to_author` (22) vs `needs_fixture_assets` (13)

`provenance.kind` is `public_corpus_grounded`, a fourth kind alongside the bank's
`reverse_constructed` / `controlled_synthetic` / `internal_scenario`. `customer_data` is
`false` on every seed.

## What this corpus can and cannot supply

**Can:** input briefs, real failure conditions, reference-contract cases, operator vocabulary.
**Cannot:** decision trajectories (2/362), multi-option ranking (4 genuine cases in 362),
client feedback verbatim in a brief context. Those come from `../real-projects/`.

Findings and caveats: `curify-studio/docs/reddit-design-problem-extraction-2026-08-30.md`
(spec §7aa). Fetch-path notes (reddit.com 403s, pullpush 429s, arctic-shift pacing) are in
`curify-studio/docs/reddit-demand-mining-design-agent-2026-08-18.md`.
