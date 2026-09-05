#!/usr/bin/env python3
"""Freeze provenance and checksums for Brief Bank v0.3 fixture assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "reddit-fixtures"

PROMPTS = {
    "layout-road-sketch.png": """Use case: sketch-to-render fixture source. Asset type: internal design-agent evaluation input. Create a deliberately plain black-ink layout sketch on white paper in a wide landscape frame. A straight road runs horizontally across the bottom 20 percent. Above it, place a small blocky building on the left, a single round-canopy tree near center, and a sun in the upper-right. Simple thin hand-drawn outlines only, no shading, no color, no texture, no labels, no words, no watermark. The image must communicate geometry and object placement only, with intentionally neutral non-stylized drawing.""",
    "robot-speech-bubble-source.png": """Use case: text-localization fixture source. Asset type: internal precise local-edit benchmark. Create a polished square editorial cartoon panel showing a friendly small robot at a workbench with tools, shelves, plants, and a window around it. Put one large clean white speech bubble in the upper-left, with a crisp dark outline, containing the exact nonsense text \"BLORP ZING?\" in bold uppercase letters. Keep the bubble clearly separated from the robot and background so it can be masked. Rich enough background detail outside the bubble to detect unintended changes. No other text, no logos, no watermark.""",
    "australian-empty-road.png": """Use case: photorealistic-natural fixture source. Asset type: internal local-edit and constraint-verification benchmark. A realistic wide photograph of an empty two-lane rural road in Australia, viewed from a safe elevated roadside perspective, with clear lane markings and enough visible distance to add several cars later. Left-hand traffic geometry should be visually unambiguous from road signs and lane arrows, but there must be no vehicles in the source image. Dry eucalyptus landscape, neutral daylight, natural camera texture. No text overlays, no logos, no watermark.""",
    "owl-shirt-client-photo.png": """Use case: photorealistic-natural fixture source. Asset type: internal artwork-extraction and print-readiness benchmark. A casual smartphone photograph of a plain off-white cotton T-shirt worn on a torso, with a simple original three-color geometric owl emblem screen-printed on the chest. The print should be visible but degraded by fabric folds, perspective, uneven lighting, mild blur, and JPEG-like compression, creating a realistically bad client intake file. No existing brands, no readable words, no watermark.""",
}

ASSETS = [
    ("v03-layout-road-sketch", "layout-road-sketch.png", "layout_reference", "codex_ai_generated"),
    ("v03-robot-speech-bubble-source", "robot-speech-bubble-source.png", "edit_target", "codex_ai_generated"),
    ("v03-robot-speech-bubble-mask", "robot-speech-bubble-mask.png", "edit_mask", "deterministic_mask"),
    ("v03-australian-empty-road", "australian-empty-road.png", "edit_target", "codex_ai_generated"),
    ("v03-australian-road-edit-mask", "australian-road-edit-mask.png", "edit_mask", "deterministic_mask"),
    ("v03-owl-shirt-client-photo", "owl-shirt-client-photo.png", "degraded_client_input", "codex_ai_generated"),
]


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    generation = []
    manifest = []
    for asset_id, name, role, source_type in ASSETS:
        path = FIXTURES / name
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
        data = path.read_bytes()
        prompt = PROMPTS.get(name)
        prompt_sha = digest_bytes(prompt.encode()) if prompt else None
        manifest.append(
            {
                "asset_id": asset_id,
                "path": f"reddit-fixtures/{name}",
                "role": role,
                "pack_version": "v0.3",
                "source_type": source_type,
                "generator": "codex-built-in-imagegen" if prompt else "build_masks.py",
                "model": "built-in-image-generation" if prompt else None,
                "generation_mode": "single_prompt" if prompt else "deterministic_from_source",
                "prompt_sha256": prompt_sha,
                "generated_at": "2026-09-03",
                "license": "project_owned_test_fixture",
                "contains_personal_data": False,
                "synthetic_person": name == "owl-shirt-client-photo.png",
                "width": width,
                "height": height,
                "mode": mode,
                "bytes": len(data),
                "sha256": digest_bytes(data),
            }
        )
        if prompt:
            generation.append(
                {
                    "asset_id": asset_id,
                    "tool": "codex-built-in-imagegen",
                    "model_identity": "not_exposed_by_built_in_tool",
                    "prompt": prompt,
                    "prompt_sha256": prompt_sha,
                    "source_copy_retained": True,
                }
            )
    (HERE / "manifest.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest), encoding="utf-8"
    )
    (HERE / "generation.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in generation), encoding="utf-8"
    )
    print(f"assets={len(manifest)} generated={len(generation)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
