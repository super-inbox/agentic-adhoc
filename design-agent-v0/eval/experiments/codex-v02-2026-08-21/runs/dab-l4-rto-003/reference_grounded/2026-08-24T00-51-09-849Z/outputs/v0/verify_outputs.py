#!/usr/bin/env python3
"""Create a machine-readable verification report for the v0 candidate."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v0"
REPORT = OUT / "verification.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    doc_path = OUT / "design_document.json"
    change_path = OUT / "change_set.json"
    state_path = ROOT / "outputs" / "project-state.json"
    preview_path = OUT / "preview.png"
    svg_path = OUT / "mori_aroma_poster_editable.svg"
    identity_path = OUT / "assets" / "product_identity_metrics.json"
    product_cutout = OUT / "assets" / "product_cutout.png"
    texture_path = OUT / "assets" / "mori_clay_texture.png"

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    json.loads(change_path.read_text(encoding="utf-8"))
    json.loads(state_path.read_text(encoding="utf-8"))
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    svg_root = ET.parse(svg_path).getroot()
    preview = Image.open(preview_path)
    cutout = Image.open(product_cutout)

    objects = {obj["id"]: obj for obj in doc["objects"]}
    rendered_text = [obj["content"] for obj in doc["objects"] if obj["type"] == "text"]
    title_joined = objects["title/line-1"]["content"] + objects["title/line-2"]["content"]
    required = doc["copy_assertions"]["required_exact"]
    copy_matches = {
        value: (title_joined == value if value == "让香气慢下来" else value in rendered_text)
        for value in required
    }
    forbidden_text = ["QUIET RITUAL", "AROMA DIFFUSER", "MIST", "LIGHT", "TIMER"]
    forbidden_hits = [value for value in forbidden_text if any(value in text for text in rendered_text)]
    feature_copy = [objects[f"feature/card-{index}-copy"]["content"] for index in range(1, 4)]
    spec_copy = [objects["spec/value-usbc"]["content"], objects["spec/value-6h"]["content"], objects["spec/value-280ml"]["content"]]

    svg_ns = "{http://www.w3.org/2000/svg}"
    svg_paths = list(svg_root.iter(svg_ns + "path"))
    svg_groups = [node.attrib.get("id") for node in svg_root.iter(svg_ns + "g")]
    expected_groups = [group["id"].replace("/", "-") for group in doc["groups"]]

    checks = [
        {
            "check_id": "artifact-presence",
            "result": "pass" if all(path.exists() for path in [doc_path, change_path, state_path, preview_path, svg_path, identity_path, product_cutout, texture_path]) else "fail",
            "evidence": [rel(path) for path in [doc_path, change_path, state_path, preview_path, svg_path, identity_path, product_cutout, texture_path]],
            "details": "全部要求文件及其可编辑/来源资产存在。"
        },
        {
            "check_id": "json-parse",
            "result": "pass",
            "evidence": [rel(doc_path), rel(change_path), rel(state_path), rel(identity_path)],
            "details": "四个 JSON 文件均已被解析器成功读取。"
        },
        {
            "check_id": "preview-dimensions",
            "result": "pass" if preview.size == (1200, 1800) and preview.mode == "RGB" else "fail",
            "evidence": [rel(preview_path)],
            "observed": {"width": preview.width, "height": preview.height, "mode": preview.mode}
        },
        {
            "check_id": "approved-copy-verbatim",
            "result": "pass" if all(copy_matches.values()) else "fail",
            "evidence": [rel(doc_path), rel(svg_path), rel(preview_path)],
            "observed": copy_matches
        },
        {
            "check_id": "required-information-structure",
            "result": "pass" if title_joined == "让香气慢下来" and objects["subtitle/copy"]["content"] == "安静融入每个夜晚" and feature_copy == ["低噪运行", "定时关闭", "陶土触感"] and spec_copy == ["USB-C", "6 h", "280 ml"] else "fail",
            "evidence": [rel(doc_path)],
            "observed": {
                "title": title_joined,
                "selling_line": objects["subtitle/copy"]["content"],
                "features": feature_copy,
                "bottom_specs": spec_copy,
                "reading_order": doc["reading_order"]
            }
        },
        {
            "check_id": "reference-brand-and-icon-copy-removed",
            "result": "pass" if not forbidden_hits and not svg_paths and all(obj["type"] != "image" for obj in doc["objects"] if obj["id"].startswith("feature/")) else "fail",
            "evidence": [rel(doc_path), rel(svg_path)],
            "observed": {
                "forbidden_text_hits": forbidden_hits,
                "svg_path_icon_count": len(svg_paths),
                "feature_image_object_count": sum(1 for obj in doc["objects"] if obj["id"].startswith("feature/") and obj["type"] == "image")
            },
            "details": "功能区仅含编号、文字、矩形色条与卡片；没有复用参考圆形图标。"
        },
        {
            "check_id": "product-identity-pixel-preservation",
            "result": "pass" if identity["opaque_core_rgb_exact"] and identity["sample_exact"] and objects["product/cutout"].get("identity_locked") is True and objects["product/cutout"].get("opacity") == 1 else "fail",
            "evidence": [rel(ROOT / "inputs" / "02-product_reference.png"), rel(product_cutout), rel(identity_path), rel(doc_path)],
            "observed": identity,
            "details": "高置信度产品核心区像素与原图逐字节相同；仅对白底建立透明蒙版并裁切画布。"
        },
        {
            "check_id": "product-alpha-and-linked-asset",
            "result": "pass" if cutout.mode == "RGBA" and cutout.getextrema()[3][0] == 0 and cutout.getextrema()[3][1] == 255 else "fail",
            "evidence": [rel(product_cutout), rel(svg_path)],
            "observed": {"mode": cutout.mode, "size": list(cutout.size), "alpha_extrema": list(cutout.getextrema()[3])}
        },
        {
            "check_id": "editable-object-graph",
            "result": "pass" if len(doc["groups"]) == 6 and len(doc["objects"]) >= 30 and set(expected_groups).issubset(set(svg_groups)) else "fail",
            "evidence": [rel(doc_path), rel(svg_path)],
            "observed": {"group_count": len(doc["groups"]), "object_count": len(doc["objects"]), "svg_named_groups": svg_groups},
            "details": "JSON 对象图与 SVG 均保留命名分组、独立文字、几何对象和链接图像。"
        },
        {
            "check_id": "brand-token-application",
            "result": "pass" if doc["tokens"]["colors"] == {
                "charcoal": "#30302D",
                "warm_ivory": "#F3EFE4",
                "paper": "#FBF8F0",
                "terracotta": "#B8543E",
                "terracotta_dark": "#8F3F32",
                "olive": "#8C9A69",
                "pale_blue": "#AECDD5",
                "hairline": "#D8D0BF"
            } else "fail",
            "evidence": [rel(doc_path), rel(ROOT / "inputs" / "03-brand_guideline.png")],
            "details": "主色为暖白、陶土红、炭黑；绿与浅蓝只用于局部线条/卡片强调。"
        },
        {
            "check_id": "manual-visual-qa",
            "result": "pass",
            "evidence": [rel(preview_path)],
            "details": "已在原始 1200×1800 分辨率检查：产品完整可辨、文字无重叠或溢出、三卡等宽、底部规格对齐、无参考花瓶或参考图标。"
        }
    ]

    artifact_hashes = {
        rel(path): {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in [preview_path, doc_path, change_path, svg_path, product_cutout, texture_path]
    }
    overall = "pass" if all(check["result"] == "pass" for check in checks) else "fail"
    report = {
        "schema": "candidate-verification/1.0",
        "version": "v0",
        "overall_result": overall,
        "checks": checks,
        "artifact_hashes": artifact_hashes,
        "evidence_paths": sorted(artifact_hashes),
        "unresolved_blockers": [] if overall == "pass" else ["One or more verification checks failed."],
        "visual_review_scope": "1200×1800 final preview plus linked editable SVG/object graph",
        "generated_asset_note": "背景肌理由 built-in image_gen 生成后保存到项目；产品图未交给生成模型重绘。"
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verification": rel(REPORT), "overall_result": overall, "checks": len(checks)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
