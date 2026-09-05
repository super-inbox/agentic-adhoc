# Brief Bank v0.3 project-owned fixtures

This pack closes the executable-input gap for four of the 11 selected Reddit-derived
benchmark cases. It contains four newly generated source images and two deterministic
binary edit masks. No image was copied from a Reddit post.

| asset | benchmark role |
|---|---|
| `layout-road-sketch.png` | layout-only reference in a two-reference channel-binding case |
| `robot-speech-bubble-source.png` | approved source for exact masked text replacement |
| `robot-speech-bubble-mask.png` | only region allowed to change in that text edit |
| `australian-empty-road.png` | source photo for a left-hand-traffic object-addition case |
| `australian-road-edit-mask.png` | road-surface region allowed to change |
| `owl-shirt-client-photo.png` | degraded product photograph for artwork extraction/vectorisation |

- `PROMPTS.md` explains the generation intent.
- `generation.jsonl` freezes the exact prompts and available tool identity.
- `manifest.jsonl` freezes dimensions, byte counts, SHA-256, privacy, and license metadata.
- `build_masks.py` deterministically rebuilds the two masks.
- `build_manifest.py` deterministically rebuilds provenance and integrity metadata.

All assets are `project_owned_test_fixture`. The torso in the shirt photo is synthetic and
is marked accordingly; no asset contains personal data.
