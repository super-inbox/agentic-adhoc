from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_dilation, gaussian_filter


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v2"
INTERMEDIATE = OUT / "intermediate"
ORIGINAL = ROOT / "inputs" / "01-revision_target.png"
V1 = ROOT / "outputs" / "v1" / "summer-form-poster-local-revision-v1.png"
V1_TEXTURE_SOURCE = (
    ROOT / "outputs" / "v1" / "intermediate" / "imagegen-edit-source.png"
)
FINAL = OUT / "summer-form-poster-local-revision-v2.png"
COMPARISON = OUT / "summer-form-poster-v1-v2-comparison.png"
DIFF_MASK = OUT / "summer-form-poster-v2-diff-mask.png"
METRICS = INTERMEDIATE / "paper-grain-reduction-metrics.json"
PRIOR_HASHES = INTERMEDIATE / "prior-version-hashes.json"

GRAIN_SCALE = 0.70


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_prior_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for version in ("v0", "v1"):
        folder = ROOT / "outputs" / version
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                result[str(path.relative_to(ROOT))] = sha256(path)
    return result


def saturation(rgb: np.ndarray) -> np.ndarray:
    normalized = rgb / 255.0
    maximum = normalized.max(axis=2)
    minimum = normalized.min(axis=2)
    return (maximum - minimum) / np.maximum(maximum, 1e-6)


def fit_quadratic_background(
    rgb: np.ndarray, train_mask: np.ndarray
) -> np.ndarray:
    height, width = train_mask.shape
    yy, xx = np.mgrid[0:height, 0:width]
    x = (xx / max(width - 1, 1)) * 2.0 - 1.0
    y = (yy / max(height - 1, 1)) * 2.0 - 1.0
    features = np.stack(
        [np.ones_like(x), x, y, x * x, y * y, x * y], axis=2
    )
    design = features[train_mask]
    result = np.empty_like(rgb, dtype=np.float64)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(
            design, rgb[:, :, channel][train_mask], rcond=None
        )
        result[:, :, channel] = features @ coefficients
    return result


def bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def hash_masked_pixels(
    image: np.ndarray, mask: np.ndarray, bounds: tuple[int, int, int, int]
) -> str:
    x0, y0, x1, y1 = bounds
    local_image = image[y0:y1, x0:x1]
    local_mask = mask[y0:y1, x0:x1]
    payload = local_mask.astype(np.uint8).tobytes() + local_image[local_mask].tobytes()
    return hashlib.sha256(payload).hexdigest()


def texture_metrics(
    image: np.ndarray, box: tuple[int, int, int, int]
) -> dict[str, float]:
    x0, y0, x1, y1 = box
    luminance = image[y0:y1, x0:x1].mean(axis=2)
    fine = luminance - gaussian_filter(luminance, 0.55)
    middle = gaussian_filter(luminance, 0.55) - gaussian_filter(luminance, 2.0)
    high_pass = luminance - gaussian_filter(luminance, 1.2)
    return {
        "mean_luminance": round(float(luminance.mean()), 4),
        "fine_grain_std": round(float(fine.std()), 4),
        "mid_grain_std": round(float(middle.std()), 4),
        "high_pass_std": round(float(high_pass.std()), 4),
    }


def load_label_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    prior_hashes = snapshot_prior_versions()
    PRIOR_HASHES.write_text(
        json.dumps(prior_hashes, ensure_ascii=False, indent=2) + "\n"
    )

    original_u8 = np.asarray(Image.open(ORIGINAL).convert("RGB"))
    v1_u8 = np.asarray(Image.open(V1).convert("RGB"))
    height, width = v1_u8.shape[:2]
    original = original_u8.astype(np.float64)
    v1 = v1_u8.astype(np.float64)
    texture_source = np.asarray(
        Image.open(V1_TEXTURE_SOURCE)
        .convert("RGB")
        .resize((width, height), Image.Resampling.LANCZOS),
        dtype=np.float64,
    )

    yy, xx = np.mgrid[0:height, 0:width]
    poster_interior = (xx >= 131) & (xx <= 797) & (yy >= 114) & (yy <= 1038)
    central_object_exclusion = (
        (xx >= 190) & (xx <= 485) & (yy >= 570) & (yy <= 835)
    )

    original_sat = saturation(original)
    original_value = original.max(axis=2) / 255.0
    original_protected_art = binary_dilation(original_sat > 0.115, iterations=2)
    original_paper_mask = (
        poster_interior
        & (original_sat < 0.105)
        & (original_value > 0.74)
        & ~original_protected_art
        & ~central_object_exclusion
    )

    v1_sat = saturation(v1)
    v1_value = v1.max(axis=2) / 255.0
    v1_protected_art = binary_dilation(v1_sat > 0.115, iterations=2)
    logo_roi_box = (585, 825, 775, 1010)
    rx0, ry0, rx1, ry1 = logo_roi_box
    logo_edge_lock = np.zeros((height, width), dtype=bool)
    logo_edge_lock[ry0:ry1, rx0:rx1] = binary_dilation(
        v1_sat[ry0:ry1, rx0:rx1] > 0.075, iterations=1
    )
    current_neutral_paper = (
        poster_interior
        & (v1_sat < 0.105)
        & (v1_value > 0.74)
        & ~v1_protected_art
        & ~logo_edge_lock
        & ~central_object_exclusion
    )

    # Reconstruct the exact v1 low-frequency base and deterministic grain source,
    # then retain 70% of the v1 grain amplitude. This avoids introducing a new
    # texture style or a second generative pass.
    weight = original_paper_mask.astype(np.float64)
    denominator = gaussian_filter(weight, 1.2)
    base_paper = np.empty_like(original)
    for channel in range(3):
        numerator = gaussian_filter(original[:, :, channel] * weight, 1.2)
        fallback = gaussian_filter(original[:, :, channel], 1.2)
        base_paper[:, :, channel] = np.where(
            denominator > 0.08,
            numerator / np.maximum(denominator, 1e-6),
            fallback,
        )

    texture_box = (390, 165, 540, 205)
    tx0, ty0, tx1, ty1 = texture_box
    generated_patch = texture_source[ty0:ty1, tx0:tx1].mean(axis=2)
    generated_high_pass = generated_patch - gaussian_filter(generated_patch, 1.2)
    v1_texture_std = float(np.clip(generated_high_pass.std(), 0.75, 1.05))
    rng = np.random.default_rng(20260823)
    grain = gaussian_filter(rng.normal(size=(height, width)), 0.30)
    grain -= grain.mean()
    grain *= v1_texture_std / max(float(grain.std()), 1e-6)

    main_paper_mask = original_paper_mask & current_neutral_paper
    v2 = v1.copy()
    refined = base_paper + (grain * GRAIN_SCALE)[:, :, None]
    v2[main_paper_mask] = refined[main_paper_mask]

    # v1 removed the larger original-logo footprint before placing the approved
    # smaller logo. Rebuild only those newly exposed neutral paper pixels with the
    # same fitted background and the same 0.70 grain factor; never touch logo ink.
    original_logo_roi = original[ry0:ry1, rx0:rx1]
    original_logo_sat = saturation(original_logo_roi)
    original_logo_value = original_logo_roi.max(axis=2) / 255.0
    background_train = (original_logo_sat < 0.075) & (original_logo_value > 0.72)
    fitted_logo_background = fit_quadratic_background(
        original_logo_roi, background_train
    )
    additional_logo_paper = (
        current_neutral_paper[ry0:ry1, rx0:rx1]
        & ~original_paper_mask[ry0:ry1, rx0:rx1]
    )
    logo_refined = fitted_logo_background + (
        grain[ry0:ry1, rx0:rx1] * GRAIN_SCALE
    )[:, :, None]
    v2_logo_roi = v2[ry0:ry1, rx0:rx1]
    v2_logo_roi[additional_logo_paper] = logo_refined[additional_logo_paper]
    v2[ry0:ry1, rx0:rx1] = v2_logo_roi

    allowed_paper_mask = main_paper_mask.copy()
    allowed_paper_mask[ry0:ry1, rx0:rx1] |= additional_logo_paper

    v2_u8 = np.clip(np.rint(v2), 0, 255).astype(np.uint8)
    Image.fromarray(v2_u8).save(FINAL, optimize=True)

    pixel_difference = np.any(v2_u8 != v1_u8, axis=2)
    outside_allowed = pixel_difference & ~allowed_paper_mask

    diff_visual = np.zeros_like(v1_u8)
    diff_visual[pixel_difference] = np.array([34, 190, 205], dtype=np.uint8)
    Image.fromarray(diff_visual).save(DIFF_MASK, optimize=True)
    Image.fromarray((allowed_paper_mask.astype(np.uint8) * 255)).save(
        INTERMEDIATE / "v2-paper-edit-mask.png", optimize=True
    )

    top_margin = 58
    gap = 28
    canvas = Image.new("RGB", (width * 2 + gap, height + top_margin), (235, 232, 224))
    canvas.paste(Image.fromarray(v1_u8), (0, top_margin))
    canvas.paste(Image.fromarray(v2_u8), (width + gap, top_margin))
    draw = ImageDraw.Draw(canvas)
    font = load_label_font(23)
    draw.text((18, 16), "V1 — APPROVED LOGO", font=font, fill=(35, 61, 115))
    draw.text(
        (width + gap + 18, 16),
        "V2 — GRAIN −30%",
        font=font,
        fill=(35, 61, 115),
    )
    canvas.save(COMPARISON, optimize=True)

    title_bounds = (250, 295, 755, 485)
    info_bounds = (470, 580, 760, 750)
    title_ink_mask = np.zeros((height, width), dtype=bool)
    info_ink_mask = np.zeros((height, width), dtype=bool)
    title_ink_mask[
        title_bounds[1] : title_bounds[3], title_bounds[0] : title_bounds[2]
    ] = v1_sat[
        title_bounds[1] : title_bounds[3], title_bounds[0] : title_bounds[2]
    ] > 0.08
    info_ink_mask[
        info_bounds[1] : info_bounds[3], info_bounds[0] : info_bounds[2]
    ] = v1_sat[
        info_bounds[1] : info_bounds[3], info_bounds[0] : info_bounds[2]
    ] > 0.08

    logo_mask = np.zeros((height, width), dtype=bool)
    logo_mask[ry0:ry1, rx0:rx1] = v1_sat[ry0:ry1, rx0:rx1] > 0.08
    v2_sat = saturation(v2_u8.astype(np.float64))
    v2_logo_mask = np.zeros((height, width), dtype=bool)
    v2_logo_mask[ry0:ry1, rx0:rx1] = v2_sat[ry0:ry1, rx0:rx1] > 0.08

    v1_texture = texture_metrics(v1, texture_box)
    v2_texture = texture_metrics(v2_u8.astype(np.float64), texture_box)
    fine_reduction = 1.0 - (
        v2_texture["fine_grain_std"] / v1_texture["fine_grain_std"]
    )
    high_pass_reduction = 1.0 - (
        v2_texture["high_pass_std"] / v1_texture["high_pass_std"]
    )

    metrics = {
        "source": {
            "path": str(V1.relative_to(ROOT)),
            "sha256": sha256(V1),
            "dimensions": {"width": width, "height": height},
        },
        "output": {
            "path": str(FINAL.relative_to(ROOT)),
            "dimensions": {"width": width, "height": height},
        },
        "requested_grain_scale": GRAIN_SCALE,
        "changed_pixel_count": int(pixel_difference.sum()),
        "changed_pixel_fraction": round(float(pixel_difference.mean()), 6),
        "outside_allowed_changed_pixel_count": int(outside_allowed.sum()),
        "allowed_paper_pixel_count": int(allowed_paper_mask.sum()),
        "paper_texture_sample_box": list(texture_box),
        "paper_texture": {
            "v1": v1_texture,
            "v2": v2_texture,
            "measured_fine_grain_reduction_fraction": round(fine_reduction, 4),
            "measured_high_pass_reduction_fraction": round(
                high_pass_reduction, 4
            ),
            "mean_luminance_delta": round(
                v2_texture["mean_luminance"] - v1_texture["mean_luminance"], 4
            ),
        },
        "title_ink": {
            "v1_hash": hash_masked_pixels(v1_u8, title_ink_mask, title_bounds),
            "v2_hash": hash_masked_pixels(v2_u8, title_ink_mask, title_bounds),
            "pixel_identical": bool(
                np.array_equal(v1_u8[title_ink_mask], v2_u8[title_ink_mask])
            ),
        },
        "event_information_ink": {
            "v1_hash": hash_masked_pixels(v1_u8, info_ink_mask, info_bounds),
            "v2_hash": hash_masked_pixels(v2_u8, info_ink_mask, info_bounds),
            "pixel_identical": bool(
                np.array_equal(v1_u8[info_ink_mask], v2_u8[info_ink_mask])
            ),
        },
        "logo": {
            "v1_bbox": list(bbox_from_mask(logo_mask)),
            "v2_bbox": list(bbox_from_mask(v2_logo_mask)),
            "ink_pixel_identical": bool(
                np.array_equal(v1_u8[logo_mask], v2_u8[logo_mask])
            ),
            "ink_changed_pixel_count": int(
                (pixel_difference & logo_mask).sum()
            ),
        },
        "protected_art": {
            "max_channel_difference": int(
                np.abs(v2_u8.astype(np.int16) - v1_u8.astype(np.int16))[
                    v1_protected_art
                ].max(initial=0)
            )
        },
        "outer_scene": {
            "changed_pixel_count": int((pixel_difference & ~poster_interior).sum())
        },
        "central_folded_object_exclusion": {
            "changed_pixel_count": int(
                (pixel_difference & central_object_exclusion).sum()
            )
        },
        "paths": {
            "final": str(FINAL.relative_to(ROOT)),
            "comparison": str(COMPARISON.relative_to(ROOT)),
            "diff_mask": str(DIFF_MASK.relative_to(ROOT)),
            "edit_mask": str(
                (INTERMEDIATE / "v2-paper-edit-mask.png").relative_to(ROOT)
            ),
        },
        "prior_version_hashes": prior_hashes,
    }
    METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
