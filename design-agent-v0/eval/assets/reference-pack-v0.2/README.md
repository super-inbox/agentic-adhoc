# Reference Pack v0.2 — Curify-generated

This pack is the Curify Nano/Gemini regeneration of the 18 assets bound to the 21 image-bearing
rows in `eval/queries.jsonl`. It keeps the v0.1 asset IDs so the same query bindings can be evaluated
against either pack.

Status: complete — 18/18 manifest assets, 30 bindings, and 21/21 required multimodal queries pass
the offline integrity validator. v0.2 is the default pack; v0.1 remains available as a baseline.

Key v0.2 corrections:

- A/B/C/D labels are explicit on the men's-grooming vote board.
- The perfume input is deliberately under-retouched, so enhancement has observable headroom.
- The coffee back label contains structured fields instead of an empty panel.
- The MORI board avoids tiny generated alphabet strings.
- The 20-SKU sheet is composed deterministically from 20 separate Curify generations.

Generate from the repository root after setting a valid `GEMINI_API_KEY` in the sibling
`curify-frontend/.env.local`:

```bash
node dev/jayw/design-agent-v0/eval/generate_reference_pack_v02.mjs --concurrency=2
python3 dev/jayw/design-agent-v0/eval/reference_asset_eval.py --pack-version v0.2
```

Generation is resumable. Completed PNGs are skipped unless `--force` is passed; provider attempts
and completion metadata are appended to `generation-results.jsonl`. The pack is complete only when
the manifest contains 18 rows and the v0.2 validator reports PASS.

`provenance/` contains outputs from successful end-to-end Curify tool smoke runs. These files prove
the product route and image engine were exercised, but are not query inputs and therefore are not
listed in the 18-row reference manifest.
