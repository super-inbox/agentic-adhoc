# Real client trajectories — capture protocol

The one input that cannot be acquired any other way. §7s measured why: across a
362-post public corpus, selection-with-a-reason appears in **0.8%** and
multi-option ranking in **0%**. Portfolios publish the version that won. The
middle of the process — what lost, and why — exists only while the project is
happening, and only in the hands of the person doing it.

So this is not an archive. **It is a capture discipline**, and its only real
enemy is friction.

## What dies if you don't capture it live

| field | why it cannot be reconstructed later |
|---|---|
| the client's **original wording** | you normalise it within a day, and the normalisation is the thing we want to learn to undo |
| **every option you showed**, including losers | rejected work gets deleted; a system with no rejected options cannot express taste |
| **why they rejected what they rejected** | usually said once, verbally, in passing — this is the single highest-value field |
| the **exact revision request** | "make it more premium" is data; your interpretation of it is not |

Everything else — final files, dates, deliverable types — can be recovered.
These four cannot.

## Four capture moments, ~2 minutes each

Do them **when they happen**, not at project end.

1. **Brief arrives** → `initial_query` verbatim + `inputs` + any stated
   constraints. Paste what they wrote. Do not tidy it.
2. **You show options** → one entry per option in `alternatives`, even the ones
   you already know are weak. Include the ones you made and didn't show.
3. **They choose** → `selection` + **`rejection_rationale` for each option that
   lost**. If they only said "I prefer B", write exactly that and mark
   `rationale_given: false` — a recorded absence is data; an invented reason is
   contamination.
4. **They ask for changes** → `feedback[]` with `message` **verbatim**, plus
   what you actually changed and what you deliberately left alone
   (`invariants`).

At project end add `outcome`. That's it.

## Privacy — read before the first capture

Real client work. The rules are not optional:

- **Never commit client names, brand names pre-launch, contacts, prices, or
  contract terms.** Use the pseudonymous `client_id` (`client-001`) and keep the
  mapping in `.client-key.json`, which is gitignored and must stay local.
- Set `provenance.customer_data: true` on every real capture. The existing brief
  bank sets it `false` on all 24 synthetic briefs; that flag is how anything
  downstream tells them apart.
- Verbatim quotes are the asset, but strip names *inside* quotes:
  `"[client] said the packaging looks cheap"`, not the person's name.
- If a project is under NDA, capture the **shape** (intent, option count,
  rejection reason class) and set `redacted: true`. A redacted trajectory is
  still worth more than no trajectory.

## Three record classes — keep them apart

`customer_data` is the flag everything downstream uses to tell real client work
from synthetic briefs. Diluting it costs more than a missing record, so the id
prefix carries the class:

| id prefix | what it is | `customer_data` | `provenance.kind` |
|---|---|---|---|
| `client-NNN` | a real engagement: they commissioned something | **`true`** | `real_client_project` |
| `internal-NNN` | our own work, or a supplier interaction with no commission | `false` | `internal_exploration` / supplier |
| `lead-NNN` | a real inbound enquiry we have **not** been engaged on | `false` | `inbound_rfq_not_engaged` |

A `lead-NNN` record is legitimate and worth capturing — the enquiry's wording is
real external demand language, and what an enquiry *omits* is itself a finding.
But it has no options, no rejections and no feedback, and it must not borrow a
`client-NNN` id "in advance". If it converts, follow the `_provenance_warning`
inside the record: take the next free `client-NNN`, flip `kind` and
`customer_data`, and **append** the formal brief rather than overwriting the
enquiry wording — enquiry language and brief language are two different corpora.

⚠️ `new_project.py` enforces the `client-` prefix and will refuse `internal-` and
`lead-` ids. That is deliberate. Write those files by hand; do not "fix" the script.

## Start one

```bash
python3 new_project.py --client client-004 --category packaging_sku_family
# → projects/2026-08-27-client-004-packaging.json, prefilled and commented
```

Then edit it as the four moments happen. It is one file per project, and it is
meant to be edited repeatedly, not written once.

## What it turns into

```bash
python3 to_brief.py projects/2026-08-27-client-004-packaging.json
```

Emits a v0.2-shaped brief. Field names deliberately match
`brief_bank/briefs.v0.2.jsonl` — `initial_query`, `feedback[].message`,
`feedback[].invariants`, `preference_memory.{accepted,rejected}_signals`,
`project_state.locked_invariants` — so a real project becomes an eval fixture
without a translation step.

Two things a real capture gives that the synthetic bank cannot:

- **`preference_memory` with a real client's accepted/rejected signals**, which
  is the personalization input §7r-E argues is the only defensible asset.
- **`feedback[].message` in a client's actual voice.** §7p found "make it pop"
  in 1 of 362 public posts — the vocabulary of real revision requests is not
  available anywhere else.

## Target

**20–30 projects.** Not 100. §7r-F's estimate stands: a hundred real decision
chains are likely worth more than a hundred thousand portfolio images, and
20–30 is enough to see whether a client's rejections are consistent.
