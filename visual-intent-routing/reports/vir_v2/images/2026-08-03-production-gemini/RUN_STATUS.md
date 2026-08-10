# VIR v2 unified production comparison status

Run ID: `2026-08-03-production-gemini`

Systems:

- GPT-direct: query → `gpt-image-2`
- Curify production: routing + template parameters → Curify
  `/api/generate-image` → `gemini-3-pro-image-preview`

Both systems now live in this single run directory. The removed
`2026-08-01-full` directory was the older controlled track; its 158 Curify
`gpt-image-2` images are intentionally excluded from the counts below.

## Current checkpoint

| Stage | GPT-direct images | Curify Gemini images | Combined | Unique queries | Matched query/direction pairs |
|---|---:|---:|---:|---:|---:|
| Anchors | 16 | 15 | 31 | 16 | 15 |
| Exploration | 82 | 81 | 163 | 30 | 76 |
| Core | 68 | 54 | 122 | 69 | 53 |
| **Total** | **166** | **150** | **316** | **115** | **144** |

Among the 115 unique queries, 96 have at least one successful image from both
systems. Exploration may have up to three directions per query, which is why
its matched-pair count is greater than its query count.

## Completion state

| Stage | System | Jobs | Completed | Failed | Pending |
|---|---|---:|---:|---:|---:|
| Anchors | GPT-direct | 16 | 16 | 0 | 0 |
| Anchors | Curify Gemini | 15 | 15 | 0 | 0 |
| Exploration | GPT-direct | 90 | 82 | 8 | 0 |
| Exploration | Curify Gemini | 85 | 81 | 4 | 0 |
| Core | GPT-direct | 450 | 68 | 0 | 382 |
| Core | Curify Gemini | 450 | 54 | 1 | 395 |

`vir-s16` correctly abstained in the Curify anchor run, so Curify created no
image job for that content-gap query. Challenge + content-gap image generation
has not been prepared.

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

## Files

Each stage contains `by-query/<normalized-query>/` directories, result JSONL
files, a combined `gallery.html`, and `stage-manifest.json`. Every Query folder
places `gpt-direct--d<direction>` and `curify-gemini--d<direction>` images side
by side and contains an exact `query-manifest.json`. Each stage records the
move in `query-folder-migration.json`; the root `comparison-manifest.json`
summarizes all three stages.
