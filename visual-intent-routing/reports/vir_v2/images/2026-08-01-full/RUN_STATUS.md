# VIR v2 paired image run status

Run ID: `2026-08-01-full`

The run follows this locked order: anchors, exploration, remaining Core, then
Challenge plus Content-gap. GPT-direct and Curify use the same `gpt-image-2`
render backend; Curify first selects a template and fills its prompt.

## Current checkpoint

| Stage | GPT-direct | Curify | State |
|---|---:|---:|---|
| Anchors | 16 / 16 | 14 / 15, plus 1 abstention | Executed; one Curify output repeatedly moderation-blocked |
| Exploration | 29 / 90 | 0 / 85 | Paused by `billing_hard_limit_reached` |
| Remaining Core | 0 / 450 | Not planned yet | Not started |
| Challenge + Content-gap | 0 / 200 | Not planned yet | Not started |

The exploration manifest records 61 pending GPT-direct jobs and 85 pending
Curify jobs. The 29 completed exploration images and all 30 Curify routing plans
are preserved. The API log contains 3 moderation blocks and the billing-limit
responses that caused the pause.

## Resume after billing is restored

Keep the Curify frontend running, then execute:

```bash
node scripts/vir-image-tasks.cjs prepare \
  --stage exploration \
  --run-id 2026-08-01-full \
  --base-url http://localhost:3001

node scripts/vir-image-tasks.cjs render \
  --stage exploration \
  --run-id 2026-08-01-full \
  --system paired \
  --python /private/tmp/vir-imagegen-venv/bin/python \
  --concurrency 4

node scripts/vir-image-tasks.cjs finalize \
  --stage exploration \
  --run-id 2026-08-01-full
```

`prepare` regenerates only the pending task files. Existing non-empty images are
never submitted again.
