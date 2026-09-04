# Grain & Glow — Taobao main-image delta request v2

## Client decisions recorded

- The v1 gift-box direction is approved and locked.
- The Territory B visual system is locked and must not be rebuilt.
- On the existing Taobao main image, remove only the price label.
- Compress the existing selling-point copy to one sentence.

## Exact edit boundary

Allowed changes:

1. Remove the existing price label and reconstruct only the immediately covered background.
2. Replace the existing selling-point block with one sentence derived from the existing copy.

Everything else must remain pixel-aligned and unchanged, including the gift box, Logo, product imagery, background, lighting, palette, spacing outside the affected copy region, and the approved visual system.

## Blocking input

No Taobao main image exists in `inputs`, `outputs/v0`, or `outputs/v1`. Both earlier verification files explicitly state that no Taobao main image was produced.

Required to continue:

- The current full-resolution Taobao main image or its editable source file containing the price label and existing selling-point copy.
- If the selling-point text is not legible in that file, provide the current text verbatim.

No replacement main image or new selling-point claim has been invented in v2.
