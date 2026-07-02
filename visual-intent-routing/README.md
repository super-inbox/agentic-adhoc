# Visual Intent Routing — eval track

Rong's track of the Search & Discovery thesis: **Generative Retrieval for Template
Recommendation** — given an open-domain query, route it to the right visual template
out of a finite (~300) label space. (Companion to Baobao's `visual-search-adhoc`.)

North-star framing: [`docs/eval-framework-visual-intent-routing-2026-06-15.md`](docs/eval-framework-visual-intent-routing-2026-06-15.md).

## Status (v1)

Layer-1 (Template Routing Accuracy) is executable end-to-end:
- **Capability KB** built from real template examples (227 templates, 2,804 examples).
- **Routing gold**: 58 queries → `acceptable_template_ids[]` (a set), `primary`, `ambiguity`, `near_miss`. **Still a Claude draft pending human sign-off** — this is the gate.
- **Ontology-enriched gold** (`vir_routing_gold_on.json`): every template carries its
  `(Subject × Info-type × Layout)` cell, so routing errors get **per-axis attribution**
  (a wrong route is a neighbor cell — usually right subject, wrong info-type/layout).
- **Scorers**: Path A (keyword/alias retrieval) + Path B (live gpt-4o-mini matcher) + union.

Full write-up: [`docs/vir-routing-eval-v1-summary.md`](docs/vir-routing-eval-v1-summary.md).
Gate before any KB-lift number: [`docs/vir-routing-eval-v1-review-checklist.md`](docs/vir-routing-eval-v1-review-checklist.md).

## Layout

This directory **mirrors the minimal `curify-frontend` subtree** the scripts need, so
every script runs standalone with **zero path changes** (`ROOT = scripts/..`):

```
scripts/            eval + build scripts (*.cjs)
  configs/          gold, ontology-gold, capability KB, eval notes (derived + labels)
public/data/        FROZEN snapshots: nano_templates.json, nano_inspiration.json
messages/{en,zh}/   FROZEN snapshots: nano.json (Path-B catalog i18n; scorer scans en+zh)
lib/taxonomy.json   FROZEN snapshot: 3-tier ontology maps
docs/               framework + v1 summary + review checklist + eval-set notes
reports/            dated progress updates
```

Snapshots are point-in-time copies from `curify-frontend` — intentional, so the eval is
reproducible and works as a regression baseline. Refresh by re-copying + re-running the
build scripts.

## Run (no API key)

```
node scripts/validate_gold.cjs            # gold integrity (ids exist, allow_generation, slots)
node scripts/build_gold_ontology.cjs      # regenerate vir_routing_gold_on.json
node scripts/build_review_checklist.cjs   # regenerate the human-review checklist
node scripts/kb_lookup.cjs <template-id>  # inspect one template's capability evidence
```

## Run (needs `OPENAI_API_KEY` — Path B calls gpt-4o-mini)

```
node scripts/eval_template_routing.cjs --path=all     # A / B / union routing accuracy
node scripts/try_kb_matcher.cjs 单词 chiikawa …        # A vs B(desc) vs B(KB) per query
```

## Next

1. Human review of the gold via the checklist → set `review_status: human-reviewed`.
2. Wire cell-level scoring into `eval_template_routing.cjs` (per-axis accuracy + error
   attribution + Template-Diversity@K), reading `vir_routing_gold_on.json`.
3. Scale the gold toward the spec's balanced 100/200 and fold in real user queries.
