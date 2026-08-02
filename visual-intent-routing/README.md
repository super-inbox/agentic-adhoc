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

Put the key in **`visual-intent-routing/.env.local`** (this directory's root, next to
`package.json`) — the scripts load it via `dotenv` from `ROOT/.env.local` and it is
git-ignored:

```
# visual-intent-routing/.env.local
OPENAI_API_KEY=sk-...
```

```
node scripts/eval_template_routing.cjs --path=all     # A / B / union routing accuracy
node scripts/try_kb_matcher.cjs 单词 chiikawa …        # A vs B(desc) vs B(KB) per query
```

## Next

1. Human review of the gold via the checklist → set `review_status: human-reviewed`.
2. Wire cell-level scoring into `eval_template_routing.cjs` (per-axis accuracy + error
   attribution + Template-Diversity@K), reading `vir_routing_gold_on.json`.
3. Scale the gold toward the spec's balanced 100/200 and fold in real user queries.

## VIR v2 — reproducible ranked routing and abstention benchmark

V2 is separate from the unapproved v1 definitions. It preserves the supplied 16
manual anchors exactly, adds a 15-template evidence-grounded capability registry,
and evaluates:

```
query → ranked canonical template IDs, or explicit abstention
```

It does not evaluate rendered-image quality. The design and known label/workflow
conflicts are documented in
[`benchmarks/vir_v2/DESIGN.md`](benchmarks/vir_v2/DESIGN.md).

The committed default is JSON-compatible YAML and requests 680 deterministic
candidate records: 450 single-intent core, 80 content gaps, 60 ambiguous/boundary,
60 multi-intent, and 30 open-ended style-exploration queries. Generated labels
retain `auto_accepted` or `needs_review` status; only the 16 anchors are manually
approved.

The independent `exploration` split quantifies whether a router exposes several
relevant visual directions without contaminating Core Top-1 accuracy. Its
headline metric is:

```
Relevant Effective Style Count@K
  = (relevant predictions / K)
    × exp(Shannon entropy of relevant style-family distribution)
```

At `K=3`, three relevant and registry-distinct style directions score 3; one
relevant direction plus two irrelevant templates scores `1/3`; irrelevant
variety cannot increase the score. `compare` reports the corresponding
`Style Exploration Lift@K` against a baseline. This is a capability-routing
proxy based on frozen registry style/layout families, not a perceptual or
rendered-image diversity score.

### Reproduce the network-free pilot

```bash
npm test
node scripts/vir-eval.cjs inspect \
  --config benchmarks/vir_v2/configs/default.yaml
node scripts/vir-eval.cjs all \
  --config benchmarks/vir_v2/configs/default.yaml \
  --no-resume
```

Every stage is independently resumable:

```bash
node scripts/vir-eval.cjs build-registry --config benchmarks/vir_v2/configs/default.yaml
node scripts/vir-eval.cjs expand         --config benchmarks/vir_v2/configs/default.yaml
node scripts/vir-eval.cjs validate       --config benchmarks/vir_v2/configs/default.yaml
node scripts/vir-eval.cjs split          --config benchmarks/vir_v2/configs/default.yaml
node scripts/vir-eval.cjs run            --config benchmarks/vir_v2/configs/default.yaml --adapter=mock
node scripts/vir-eval.cjs score          --config benchmarks/vir_v2/configs/default.yaml
node scripts/vir-eval.cjs report         --config benchmarks/vir_v2/configs/default.yaml
```

To exercise the current Curify API while the frontend is running:

```bash
node scripts/vir-eval.cjs run \
  --config benchmarks/vir_v2/configs/default.yaml \
  --adapter=http \
  --url=http://localhost:3000/api/search-template-match \
  --no-resume
node scripts/vir-eval.cjs report \
  --config benchmarks/vir_v2/configs/default.yaml
```

CLI adapters accept one JSONL request on stdin and must emit one JSONL response;
this is also the provider-neutral bridge for Python routers. Module-function and
mock adapters are available. Unknown IDs, duplicate IDs, malformed ranks/scores,
parse errors, and unmarked empty outputs are recorded as visible router errors.

Optional LLM expansion is explicit and cached; it never runs in tests:

```bash
node scripts/vir-eval.cjs expand \
  --config benchmarks/vir_v2/configs/default.yaml \
  --provider=llm
```

It requires `OPENAI_API_KEY` and writes raw output, model, prompt version, and
prompt hash to the configured cache. Query generation and independent Gold
validation use different prompts. Rule generation remains the reproducible
default.

Optional independent validation is a separate explicit stage. Accepted model
verdicts remain `needs_review` until a human approves them:

```bash
node scripts/vir-eval.cjs validate \
  --config benchmarks/vir_v2/configs/default.yaml \
  --llm-validator \
  --validator-model=gpt-4o-mini \
  --limit=20
```

Regression comparison uses paired records, slice deltas, newly fixed/broken
records, seeded paired bootstrap intervals, and Style Exploration Lift:

```bash
node scripts/vir-eval.cjs compare \
  --config benchmarks/vir_v2/configs/default.yaml \
  --baseline=benchmarks/vir_v2/baselines/<baseline-run>
```

Primary artifacts are written to `reports/vir_v2/pilot/`; the manual review queue
is in `reports/vir_v2/review/`. Do not tune router behavior or thresholds on the
locked test manifest in `benchmarks/vir_v2/manifests/test_manifest.json`.

### Generate paired GPT-direct and Curify images

Image generation is an optional, paid artifact stage. It does not alter routing
Gold labels or enter the VIR v2 routing metrics. Both arms use `gpt-image-2` with
the same quality settings: GPT-direct receives the natural-language query;
Curify receives the filled prompt from the template selected by the live Curify
generation-plan API. This isolates the value of routing/template planning from a
change in image backend.

Install the official image client in a temporary environment and start the
sibling Curify frontend first:

```bash
python3 -m venv /private/tmp/vir-imagegen-venv
/private/tmp/vir-imagegen-venv/bin/python -m pip install openai

cd ../../curify-frontend
npm run dev
```

Then run each stage in order from this project. Replace port `3001` with the port
printed by Next.js. `prepare` checkpoints each Curify plan, `render` skips files
already present and writes API logs, and `finalize` hashes completed images.

```bash
cd ../agentic-adhoc/visual-intent-routing

node scripts/vir-image-tasks.cjs prepare --stage anchors --base-url http://localhost:3001
node scripts/vir-image-tasks.cjs render --stage anchors --system paired \
  --python /private/tmp/vir-imagegen-venv/bin/python --concurrency 4
node scripts/vir-image-tasks.cjs finalize --stage anchors

node scripts/vir-image-tasks.cjs prepare --stage exploration --base-url http://localhost:3001
node scripts/vir-image-tasks.cjs render --stage exploration --system paired \
  --python /private/tmp/vir-imagegen-venv/bin/python --concurrency 4
node scripts/vir-image-tasks.cjs finalize --stage exploration

node scripts/vir-image-tasks.cjs prepare --stage core --base-url http://localhost:3001 \
  --plan-concurrency 4
node scripts/vir-image-tasks.cjs render --stage core --system paired \
  --python /private/tmp/vir-imagegen-venv/bin/python --concurrency 4
node scripts/vir-image-tasks.cjs finalize --stage core

node scripts/vir-image-tasks.cjs prepare --stage challenge-gap --base-url http://localhost:3001
node scripts/vir-image-tasks.cjs render --stage challenge-gap --system paired \
  --python /private/tmp/vir-imagegen-venv/bin/python --concurrency 4
node scripts/vir-image-tasks.cjs finalize --stage challenge-gap
```

The 465 supported Core records include the 15 positive anchors, so the `core`
image stage intentionally emits the remaining 450 records. A Curify abstention
has no Curify image; it remains an auditable routing result. On a billing hard
limit the renderer stops immediately, preserves completed files, and resumes
after another `prepare` call. Outputs live under
`reports/vir_v2/images/<run-id>/<stage>/{gpt-direct,curify}/`.

For a large stage, the two systems may be rendered in parallel with separate
`--system gpt-direct` and `--system curify` processes. After a final retry,
persist confirmed moderation-only failures so later resume commands do not
resubmit them, then refresh and finalize the stage:

```bash
node scripts/vir-image-tasks.cjs mark-terminal --stage core --system paired \
  --reason moderation_blocked_after_retry
node scripts/vir-image-tasks.cjs prepare --stage core --base-url http://localhost:3001
node scripts/vir-image-tasks.cjs finalize --stage core
```

Terminal-failure JSONL ledgers retain the query, direction, prompt hash, reason,
and timestamp. They are counted as failed rather than pending in the manifest.
Historical billing errors remain in append-only logs, while `blocking_error`
reflects only the latest execution segment.
