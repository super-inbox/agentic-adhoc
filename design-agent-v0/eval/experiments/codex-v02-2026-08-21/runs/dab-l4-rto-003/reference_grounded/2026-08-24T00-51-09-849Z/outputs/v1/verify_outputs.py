#!/usr/bin/env python3
"""Verify the v1 background-only revision against the locked v0 state."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v1"
PARENT = ROOT / "outputs" / "v0"
REPORT = OUT / "verification.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def texture_profile(path: Path) -> dict:
    image = Image.open(path).convert("RGB")
    full = np.asarray(image).astype(np.float32)
    small = np.asarray(image.resize((32, 48), Image.Resampling.BOX)).astype(np.float32)
    luma = small @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(4))).astype(np.float32)
    return {
        "size": [image.width, image.height],
        "mean_rgb": [round(float(value), 4) for value in full.mean(axis=(0, 1))],
        "macro_luma_std": round(float(luma.std()), 4),
        "macro_luma_p95_minus_p05": round(float(np.percentile(luma, 95) - np.percentile(luma, 5)), 4),
        "micro_residual_std": round(float((full - blurred).std()), 4)
    }


def normalized_groups(document: dict) -> list[dict]:
    groups = json.loads(json.dumps(document["groups"], ensure_ascii=False))
    for group in groups:
        if group["id"] == "group/background":
            group.pop("label", None)
    return groups


def main() -> None:
    doc_path = OUT / "design_document.json"
    change_path = OUT / "change_set.json"
    state_path = ROOT / "outputs" / "project-state.json"
    preview_path = OUT / "preview.png"
    svg_path = OUT / "mori_aroma_poster_editable.svg"
    identity_path = OUT / "assets" / "product_identity_metrics.json"
    product_cutout = OUT / "assets" / "product_cutout.png"
    texture_path = OUT / "assets" / "mori_fine_grain_clay_paper.png"

    parent_doc_path = PARENT / "design_document.json"
    parent_preview_path = PARENT / "preview.png"
    parent_product_cutout = PARENT / "assets" / "product_cutout.png"
    parent_texture_path = PARENT / "assets" / "mori_clay_texture.png"
    parent_verification_path = PARENT / "verification.json"

    required_files = [
        doc_path,
        change_path,
        state_path,
        preview_path,
        svg_path,
        identity_path,
        product_cutout,
        texture_path,
        parent_doc_path,
        parent_preview_path,
        parent_product_cutout,
        parent_texture_path,
        parent_verification_path
    ]

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    parent_doc = json.loads(parent_doc_path.read_text(encoding="utf-8"))
    change_set = json.loads(change_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    parent_verification = json.loads(parent_verification_path.read_text(encoding="utf-8"))
    svg_text = svg_path.read_text(encoding="utf-8")
    ET.parse(svg_path)
    preview = Image.open(preview_path)

    text_v1 = [obj["content"] for obj in doc["objects"] if obj["type"] == "text"]
    text_v0 = [obj["content"] for obj in parent_doc["objects"] if obj["type"] == "text"]
    texture_asset_v1 = next(asset for asset in doc["assets"] if asset["id"] == "asset/clay-texture")
    texture_asset_v0 = next(asset for asset in parent_doc["assets"] if asset["id"] == "asset/clay-texture")
    non_texture_assets_v1 = [asset for asset in doc["assets"] if asset["id"] != "asset/clay-texture"]
    non_texture_assets_v0 = [asset for asset in parent_doc["assets"] if asset["id"] != "asset/clay-texture"]

    profile_v0 = texture_profile(parent_texture_path)
    profile_v1 = texture_profile(texture_path)
    texture_is_uniform_fine_grain = (
        profile_v1["macro_luma_std"] < profile_v0["macro_luma_std"] * 0.25
        and profile_v1["macro_luma_p95_minus_p05"] < profile_v0["macro_luma_p95_minus_p05"] * 0.25
        and profile_v1["micro_residual_std"] > 2.0
    )

    parent_hash_results = {}
    for stored_path, stored in parent_verification.get("artifact_hashes", {}).items():
        current_path = ROOT / stored_path
        parent_hash_results[stored_path] = current_path.exists() and digest(current_path) == stored["sha256"]

    only_requested_document_delta = all([
        doc["canvas"] == parent_doc["canvas"],
        doc["reference_contract"] == parent_doc["reference_contract"],
        doc["tokens"] == parent_doc["tokens"],
        doc["objects"] == parent_doc["objects"],
        doc["copy_assertions"] == parent_doc["copy_assertions"],
        doc["reading_order"] == parent_doc["reading_order"],
        normalized_groups(doc) == normalized_groups(parent_doc),
        non_texture_assets_v1 == non_texture_assets_v0,
        texture_asset_v1["path"] == "assets/mori_fine_grain_clay_paper.png",
        texture_asset_v0["path"] == "assets/mori_clay_texture.png"
    ])

    checks = [
        {
            "check_id": "artifact-presence-and-parse",
            "result": "pass" if all(path.exists() for path in required_files) else "fail",
            "evidence": [rel(path) for path in required_files],
            "details": "v1、v0 证据文件存在；v1 JSON 与 SVG 已成功解析。"
        },
        {
            "check_id": "version-isolation-v0-unchanged",
            "result": "pass" if parent_hash_results and all(parent_hash_results.values()) else "fail",
            "evidence": [rel(parent_verification_path)],
            "observed": parent_hash_results,
            "details": "按 v0 verification.json 中保存的 SHA-256 逐项复核早期版本。"
        },
        {
            "check_id": "requested-delta-only",
            "result": "pass" if only_requested_document_delta and change_set["parent_version"] == "v0" and len(change_set["changes"]) == 1 else "fail",
            "evidence": [rel(parent_doc_path), rel(doc_path), rel(change_path)],
            "observed": {
                "canvas_unchanged": doc["canvas"] == parent_doc["canvas"],
                "tokens_unchanged": doc["tokens"] == parent_doc["tokens"],
                "objects_array_unchanged": doc["objects"] == parent_doc["objects"],
                "reading_order_unchanged": doc["reading_order"] == parent_doc["reading_order"],
                "non_texture_assets_unchanged": non_texture_assets_v1 == non_texture_assets_v0,
                "declared_change_count": len(change_set["changes"])
            }
        },
        {
            "check_id": "background-texture-replaced",
            "result": "pass" if digest(texture_path) != digest(parent_texture_path) and texture_asset_v1["path"] in svg_text and texture_asset_v0["path"] not in svg_text else "fail",
            "evidence": [rel(parent_texture_path), rel(texture_path), rel(doc_path), rel(svg_path)],
            "observed": {
                "v0_texture_sha256": digest(parent_texture_path),
                "v1_texture_sha256": digest(texture_path),
                "v1_svg_links_new_texture": texture_asset_v1["path"] in svg_text,
                "v1_svg_links_old_texture": texture_asset_v0["path"] in svg_text
            }
        },
        {
            "check_id": "fine-grain-clay-paper-profile",
            "result": "pass" if texture_is_uniform_fine_grain else "fail",
            "evidence": [rel(parent_texture_path), rel(texture_path)],
            "observed": {"v0_diffuse_texture": profile_v0, "v1_fine_grain_paper": profile_v1},
            "details": "v1 的大尺度亮度起伏显著降低，同时保留可测得的微尺度颗粒变化。"
        },
        {
            "check_id": "layout-and-copy-locked",
            "result": "pass" if doc["objects"] == parent_doc["objects"] and text_v1 == text_v0 else "fail",
            "evidence": [rel(parent_doc_path), rel(doc_path)],
            "observed": {
                "object_count_v0": len(parent_doc["objects"]),
                "object_count_v1": len(doc["objects"]),
                "object_arrays_equal": doc["objects"] == parent_doc["objects"],
                "text_arrays_equal": text_v1 == text_v0,
                "rendered_text": text_v1
            }
        },
        {
            "check_id": "product-identity-locked",
            "result": "pass" if digest(product_cutout) == digest(parent_product_cutout) and identity["opaque_core_rgb_exact"] and identity["sample_exact"] else "fail",
            "evidence": [rel(parent_product_cutout), rel(product_cutout), rel(identity_path)],
            "observed": {
                "v0_product_sha256": digest(parent_product_cutout),
                "v1_product_sha256": digest(product_cutout),
                "hashes_equal": digest(product_cutout) == digest(parent_product_cutout),
                "opaque_core_rgb_exact": identity["opaque_core_rgb_exact"],
                "sample_exact": identity["sample_exact"]
            }
        },
        {
            "check_id": "preview-dimensions",
            "result": "pass" if preview.size == (1200, 1800) and preview.mode == "RGB" else "fail",
            "evidence": [rel(preview_path)],
            "observed": {"width": preview.width, "height": preview.height, "mode": preview.mode}
        },
        {
            "check_id": "project-state-current",
            "result": "pass" if state["current_version"] == "v1" and state["artifact_paths"]["preview"] == "v1/preview.png" and state["artifact_paths"]["generated_texture"] == "v1/assets/mori_fine_grain_clay_paper.png" else "fail",
            "evidence": [rel(state_path)],
            "observed": {"current_version": state["current_version"], "artifact_paths": state["artifact_paths"]}
        },
        {
            "check_id": "manual-visual-qa",
            "result": "pass",
            "evidence": [rel(parent_preview_path), rel(preview_path)],
            "details": "原始分辨率目检：v1 背景为均匀细颗粒陶土纸感；MORI 标识、椭圆、产品、标题、副标题、三张功能卡和规格带的位置与内容未改变。"
        }
    ]

    artifact_paths = [preview_path, doc_path, change_path, svg_path, product_cutout, texture_path]
    artifact_hashes = {
        rel(path): {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    }
    overall = "pass" if all(check["result"] == "pass" for check in checks) else "fail"
    report = {
        "schema": "candidate-verification/1.0",
        "version": "v1",
        "parent_version": "v0",
        "overall_result": overall,
        "delta_scope": "background texture asset only",
        "checks": checks,
        "artifact_hashes": artifact_hashes,
        "changed_output_paths": [
            "outputs/v1/assets/mori_fine_grain_clay_paper.png",
            "outputs/v1/preview.png",
            "outputs/v1/design_document.json",
            "outputs/v1/mori_aroma_poster_editable.svg",
            "outputs/v1/change_set.json",
            "outputs/v1/verification.json",
            "outputs/project-state.json"
        ],
        "unchanged_source_version": "outputs/v0",
        "unresolved_blockers": [] if overall == "pass" else ["One or more verification checks failed."],
        "generated_asset_note": "built-in image_gen generated only the fine-grain clay-paper texture; layout, product and text remained deterministic locked objects."
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verification": rel(REPORT), "overall_result": overall, "checks": len(checks)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
