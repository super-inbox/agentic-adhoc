#!/usr/bin/env python3
"""Resolve and validate the versioned reference-image pack used by queries.jsonl."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


HERE = Path(__file__).resolve().parent
QUERIES_PATH = HERE / "queries.jsonl"
PACK_ROOT = HERE / "assets" / "reference-pack-v0.1"
MANIFEST_PATH = PACK_ROOT / "manifest.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def load_queries() -> list[dict[str, Any]]:
    return _read_jsonl(QUERIES_PATH)


def load_manifest() -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for item in _read_jsonl(MANIFEST_PATH):
        asset_id = item["asset_id"]
        if asset_id in manifest:
            raise ValueError(f"duplicate asset_id in manifest: {asset_id}")
        manifest[asset_id] = item
    return manifest


def is_image_required(row: dict[str, Any]) -> bool:
    return (
        row.get("layer") == "routing_benchmark"
        and row.get("reference_image") == "required"
    ) or (
        row.get("layer") == "agent_route"
        and row.get("has_reference") is True
    )


def resolve_assets(
    row: dict[str, Any],
    manifest: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    manifest = manifest or load_manifest()
    resolved: list[dict[str, Any]] = []
    root = PACK_ROOT.resolve()
    for binding in row.get("input_assets", []):
        asset_id = binding["asset_id"]
        if asset_id not in manifest:
            raise ValueError(f"{row.get('id')}: unknown asset_id {asset_id}")
        meta = manifest[asset_id]
        path = (PACK_ROOT / meta["path"]).resolve()
        if root not in path.parents:
            raise ValueError(f"{asset_id}: path escapes reference pack: {path}")
        resolved.append({"binding": binding, "metadata": meta, "path": path})
    return resolved


def primary_image_bytes(row: dict[str, Any]) -> bytes | None:
    """Load the first bound image; ordering in input_assets defines the primary input."""
    assets = resolve_assets(row)
    return assets[0]["path"].read_bytes() if assets else None


def validate_pack() -> dict[str, Any]:
    manifest = load_manifest()
    errors: list[str] = []
    total_bytes = 0
    transparent_assets = 0

    for asset_id, meta in manifest.items():
        path = PACK_ROOT / meta["path"]
        if not path.is_file():
            errors.append(f"{asset_id}: missing file {path}")
            continue
        raw = path.read_bytes()
        total_bytes += len(raw)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != meta["sha256"]:
            errors.append(f"{asset_id}: sha256 mismatch")
        if len(raw) != meta["bytes"]:
            errors.append(f"{asset_id}: byte-size mismatch")
        try:
            with Image.open(path) as image:
                image.load()
                actual = (image.width, image.height, image.mode)
                expected = (meta["width"], meta["height"], meta["mode"])
                if actual != expected:
                    errors.append(f"{asset_id}: image metadata {actual} != {expected}")
                if image.mode == "RGBA":
                    transparent_assets += 1
                    alpha = image.getchannel("A")
                    corners = (
                        alpha.getpixel((0, 0)),
                        alpha.getpixel((image.width - 1, 0)),
                        alpha.getpixel((0, image.height - 1)),
                        alpha.getpixel((image.width - 1, image.height - 1)),
                    )
                    if any(corners):
                        errors.append(f"{asset_id}: expected transparent corners, got {corners}")
                    if alpha.getextrema()[1] != 255:
                        errors.append(f"{asset_id}: no fully opaque subject pixels")
        except Exception as exc:  # Pillow exposes decoder-specific errors.
            errors.append(f"{asset_id}: cannot decode image: {exc}")

    rows = load_queries()
    targets = [row for row in rows if is_image_required(row)]
    bound = [row for row in targets if row.get("input_assets")]
    binding_count = 0
    used_ids: set[str] = set()
    layer_counts: dict[str, int] = {}
    for row in targets:
        layer = row["layer"]
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        if not row.get("input_assets"):
            errors.append(f"{row['id']}: required image query has no input_assets")
            continue
        try:
            resolved = resolve_assets(row, manifest)
            binding_count += len(resolved)
            used_ids.update(item["metadata"]["asset_id"] for item in resolved)
        except ValueError as exc:
            errors.append(str(exc))

    unused = sorted(set(manifest) - used_ids)
    if unused:
        errors.append(f"manifest assets not bound by a required query: {unused}")

    return {
        "ok": not errors,
        "errors": errors,
        "query_rows": len(rows),
        "required_queries": len(targets),
        "bound_queries": len(bound),
        "asset_bindings": binding_count,
        "unique_assets": len(manifest),
        "used_assets": len(used_ids),
        "total_bytes": total_bytes,
        "transparent_assets": transparent_assets,
        "synthetic_person_assets": sum(bool(x.get("synthetic_person")) for x in manifest.values()),
        "personal_data_assets": sum(bool(x.get("contains_personal_data")) for x in manifest.values()),
        "layer_counts": layer_counts,
    }


if __name__ == "__main__":
    result = validate_pack()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
