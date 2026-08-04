# VIR v2 Curify Production Track status

Run ID: `2026-08-03-production-gemini`

Pipeline: Curify routing and template parameters → Curify
`/api/generate-image` → `gemini-3-pro-image-preview`.

This is an end-to-end production comparison track. It does not control the
image backend against GPT-direct. The earlier `2026-08-01-full` run remains the
separate `gpt-image-2` controlled track and has not been overwritten.

## Current checkpoint

| Stage | Records | Gemini jobs | Completed | Failed | Pending | Notes |
|---|---:|---:|---:|---:|---:|---|
| Anchors | 16 | 15 | 15 | 0 | 0 | `vir-s16` correctly abstained, so no image job |
| Exploration | 30 | 85 | 81 | 4 | 0 | Four prompts repeatedly returned no image or text only |
| Core | 450 | 450 | 54 | 1 | 395 | Stopped immediately at the Gemini daily request quota |
| Challenge + content gap | 200 | not prepared | 0 | 0 | not prepared | Run after Core |

Current Curify Gemini images: **150** (`15 + 81 + 54`).

The Core stop was a `RESOURCE_EXHAUSTED` response for
`GenerateRequestsPerDayPerProjectPerModel`, with a project limit of 250 daily
requests for `gemini-3-pro-image`. Requests include retries that returned no
image, so the number of completed files is lower than the consumed daily quota.

## Resume after quota reset

From this project, with the Curify frontend running on port 3000:

```bash
node scripts/vir-gemini-production.cjs render --stage core \
  --run-id 2026-08-03-production-gemini \
  --base-url http://localhost:3000 --concurrency 2 --max-attempts 3

node scripts/vir-gemini-production.cjs finalize --stage core \
  --run-id 2026-08-03-production-gemini
```

The renderer scans completed `.jpg`/`.png` files before submission, so this
resume command will not regenerate the 54 successful Core images. The one quota
failure and 395 pending Core records remain eligible for retry.

After Core completes, prepare and run the remaining partition:

```bash
node scripts/vir-gemini-production.cjs prepare --stage challenge-gap \
  --run-id 2026-08-03-production-gemini --base-url http://localhost:3000
node scripts/vir-gemini-production.cjs render --stage challenge-gap \
  --run-id 2026-08-03-production-gemini \
  --base-url http://localhost:3000 --concurrency 2 --max-attempts 3
node scripts/vir-gemini-production.cjs finalize --stage challenge-gap \
  --run-id 2026-08-03-production-gemini
```

Do not interpret image completion or visual inspection as routing accuracy.
Routing metrics continue to use exact template IDs and abstention Gold labels.
