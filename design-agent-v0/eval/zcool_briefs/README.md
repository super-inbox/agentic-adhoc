# ZCOOL workflow briefs (2026-08-19)

7 workflow-layer briefs harvested from ZCOOL portfolio pages, covering the four
brief classes the design-agent spec flagged as thin: packaging/SKU series (3),
brand visual exploration (2), brand campaign (1), concept-to-production (1).

Schema-aligned with `../briefs.jsonl` — same `id` / `layer` / `brief` (string) /
`domain` / `expected_steps` / `has_reference` / `provenance` / `evidence` fields,
so both files can be read by one loader. IDs continue the existing series
(`BRF-PACK-03…06`, `BRF-BRAND-04…06`).

**Follows `build_briefs.py`'s policy**: only process facts are taken. No ZCOOL
prose is copied — each `brief` line is written fresh from the factual job
description. `provenance.org` keeps the author for attribution.

## Two fields that differ, on purpose

- `evidence: "external_portfolio"` — not `external_case_study`. A portfolio is a
  published outcome, not a documented process.
- `expected_steps: []` — portfolio pages **do not publish their stage sequence**.
  Inventing a plausible one would be the fabrication the spec warns about, so it
  is left empty. These briefs are usable as **inputs and gold references**, not
  as step-sequence ground truth.

## Additive metadata

`chain` marks each item of the value gradient (brief / references / concepts /
alternatives / selection / rejection / client_feedback / revision / final /
outcome) and `gaps` lists what is missing — so no consumer mistakes this for
trajectory data. `eval_use` pins each record to `input_brief` + `gold_reference`.

`brief_text_source` is `html_text` for 3 of 7 and `requires_vlm_image_read` for
the rest: roughly half of ZCOOL keeps its narrative inside the long images.

## Regenerate

    python3 build.py        # works.json -> out/raw_works.json
    python3 finalize.py     # -> jsonl + thumbs/
    python3 convert.py      # -> schema-aligned jsonl

Full-resolution images are **not** redistributed: `assets.image_urls` are
canonical and fetched at runtime; only low-res thumbnails are stored, for
identification. Internal evaluation use only.
