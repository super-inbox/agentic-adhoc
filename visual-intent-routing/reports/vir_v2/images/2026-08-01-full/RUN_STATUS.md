# VIR v2 paired image run status

Run ID: `2026-08-01-full`

The run follows this locked order: anchors, exploration, remaining Core, then
Challenge plus Content-gap. GPT-direct and Curify use the same `gpt-image-2`
render backend; Curify first selects a template and fills its prompt.

## Current checkpoint

| Stage | GPT-direct | Curify | State |
|---|---:|---:|---|
| Anchors | 16 / 16 | 14 / 15, plus 1 abstention | Executed; one Curify output repeatedly moderation-blocked |
| Exploration | 82 / 90 | 79 / 85 | Complete; 8 GPT and 6 Curify outputs terminally moderation-blocked |
| Remaining Core | 68 / 450 | 65 / 450; all 450 plans complete | Paused by a new `billing_hard_limit_reached` response |
| Challenge + Content-gap | 0 / 200 | Not planned yet | Not started |

The exploration manifest records no pending jobs. All 30 Curify routing plans
completed. Eight GPT-direct directions and six Curify directions remained
moderation-blocked after a final retry and are preserved in terminal-failure
ledgers so resume commands do not submit them again. Historical billing-limit
responses remain in the append-only API log; the latest run has no billing
blocker.

Core planning completed for all 450 records with no plan failures or
abstentions. Parallel rendering then produced 68 GPT-direct and 65 Curify
images before the account returned a new billing hard-limit response. The Core
checkpoint contains 382 pending GPT-direct and 385 pending Curify jobs. Four GPT
and two Curify attempts were moderation-blocked during the interrupted pass;
they remain pending for one final retry because the pass ended on billing rather
than completing normally.

## Reproduce or resume

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
