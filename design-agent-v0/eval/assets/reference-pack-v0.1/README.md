# Reference Pack v0.1

Project-owned multimodal fixtures for the 21 strictly image-bearing rows in `eval/queries.jsonl`.

| pack | files | evaluation use |
|---|---:|---|
| image-edit | 1 | headline, background, and logo edits |
| design-vote | 2 | four-way packaging and logo voting |
| tryon | 3 | synthetic adult + hoodie/jacket references |
| factory | 2 | transparent sticker cutline and print artwork export |
| logo-upgrade | 1 | before/after brand-refresh board |
| product-retouch | 4 | background, glass, metal, and wood tasks |
| detail-page | 2 | layout reference + replacement product |
| sku-system | 3 | five-color product and 20-SKU brand system |

`manifest.jsonl` is the source of truth for file integrity and provenance. Query bindings refer to
`asset_id`, never raw paths. Ordering in a query's `input_assets` array defines the primary image
first, followed by supporting product/style references.

Run from `dev/jayw/design-agent-v0`:

```bash
python3 eval/reference_asset_eval.py
```

Generation details and the exact final prompts are in `PROMPTS.md`.
