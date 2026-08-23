from pathlib import Path
from PIL import Image, ImageChops
import hashlib
import json


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rect(box):
    x, y, w, h = box
    return (x, y, x + w, y + h)


def intersects(a, b):
    ax1, ay1, ax2, ay2 = rect(a)
    bx1, by1, bx2, by2 = rect(b)
    return max(ax1, bx1) < min(ax2, bx2) and max(ay1, by1) < min(ay2, by2)


def main():
    metadata = json.loads((OUT / "candidate-metadata.json").read_text(encoding="utf-8"))
    product_path = ROOT / metadata["product_source"]
    product = Image.open(product_path).convert("RGB")
    checks = []
    candidate_hashes = []

    checks.append({
        "check": "approved_copy_source",
        "passed": metadata["approved_copy"] == {
            "en": "Quiet hours, made tangible.",
            "zh": "让夜晚慢下来。",
        },
        "observed": metadata["approved_copy"],
    })
    checks.append({
        "check": "candidate_count",
        "passed": len(metadata["candidates"]) == 9,
        "observed": len(metadata["candidates"]),
    })
    checks.append({
        "check": "direction_count",
        "passed": sorted({c["direction"] for c in metadata["candidates"]}) == ["A", "B", "C"],
        "observed": sorted({c["direction"] for c in metadata["candidates"]}),
    })

    per_candidate = []
    for item in metadata["candidates"]:
        path = ROOT / item["artifact"]
        im = Image.open(path).convert("RGB")
        x, y, w, h = item["product_box"]
        expected_product = product.resize((w, h), Image.Resampling.LANCZOS)
        actual_product = im.crop((x, y, x + w, y + h))
        product_exact = ImageChops.difference(expected_product, actual_product).getbbox() is None
        copy_clear = not intersects(item["copy_box"], item["product_box"])
        logo_clear = (
            not intersects(item["logo_safe_zone"], item["product_box"])
            and not intersects(item["logo_safe_zone"], item["copy_box"])
        )
        dimensions_ok = im.size == (1600, 2000)
        candidate_hashes.append(sha256(path))
        per_candidate.append({
            "code": item["code"],
            "dimensions": list(im.size),
            "dimensions_ok": dimensions_ok,
            "product_pixels_match_uniformly_resized_source": product_exact,
            "copy_does_not_overlap_product_photo": copy_clear,
            "reserved_logo_zone_clear": logo_clear,
            "sha256": candidate_hashes[-1],
        })

    checks.extend([
        {
            "check": "candidate_dimensions",
            "passed": all(c["dimensions_ok"] for c in per_candidate),
            "observed": "1600x2000 for all candidates",
        },
        {
            "check": "product_identity_pixel_match",
            "passed": all(c["product_pixels_match_uniformly_resized_source"] for c in per_candidate),
            "observed": "Every pasted product-photo region exactly matches a uniform LANCZOS resize of the supplied source; no recolor, retouch, warp, label overlay, or copy overlay.",
        },
        {
            "check": "copy_product_separation",
            "passed": all(c["copy_does_not_overlap_product_photo"] for c in per_candidate),
            "observed": "No approved-copy bounding box intersects a product-photo bounding box.",
        },
        {
            "check": "logo_safe_zones",
            "passed": all(c["reserved_logo_zone_clear"] for c in per_candidate),
            "observed": "All reserved zones are clear of copy and product-photo boxes; logo itself is pending because no asset was supplied.",
        },
        {
            "check": "candidate_uniqueness",
            "passed": len(set(candidate_hashes)) == 9,
            "observed": len(set(candidate_hashes)),
        },
    ])

    evidence = {
        "product_source": str(product_path.relative_to(ROOT)),
        "product_source_sha256": sha256(product_path),
        "metadata": "outputs/v0/candidate-metadata.json",
        "selection_board": "outputs/v0/kv-hypotheses-selection-board.png",
        "checks": checks,
        "per_candidate": per_candidate,
        "all_automated_checks_passed": all(c["passed"] for c in checks),
    }
    (OUT / "qa-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
