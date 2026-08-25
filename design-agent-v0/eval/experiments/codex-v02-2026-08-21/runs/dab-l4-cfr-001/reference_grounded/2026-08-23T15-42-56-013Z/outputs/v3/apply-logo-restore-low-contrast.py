from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_dilation, gaussian_filter


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v3"
INTERMEDIATE = OUT / "intermediate"
V0 = ROOT / "inputs" / "01-revision_target.png"
V2 = ROOT / "outputs" / "v2" / "summer-form-poster-local-revision-v2.png"
V1_TEXTURE_SOURCE = (
    ROOT / "outputs" / "v1" / "intermediate" / "imagegen-edit-source.png"
)
FINAL = OUT / "summer-form-poster-local-revision-v3.png"
COMPARISON = OUT / "summer-form-poster-v2-v3-comparison.png"
DIFF_MASK = OUT / "summer-form-poster-v3-diff-mask.png"
METRICS = INTERMEDIATE / "logo-restore-low-contrast-metrics.json"
PRIOR_HASHES = INTERMEDIATE / "prior-version-hashes.json"

V2_GRAIN_SCALE = 0.70
LOGO_CONTRAST_SCALE = 0.64


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_prior_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for version in ("v0", "v1", "v2"):
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


def center_and_size(box: tuple[int, int, int, int]) -> dict[str, float]:
    x0, y0, x1, y1 = box
    return {
        "center_x": (x0 + x1) / 2.0,
        "center_y": (y0 + y1) / 2.0,
        "width": float(x1 - x0 + 1),
        "height": float(y1 - y0 + 1),
    }


def hash_region(image: np.ndarray, box: tuple[int, int, int, int]) -> str:
    x0, y0, x1, y1 = box
    return hashlib.sha256(image[y0:y1, x0:x1].tobytes()).hexdigest()


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

    v0_u8 = np.asarray(Image.open(V0).convert("RGB"))
    v2_u8 = np.asarray(Image.open(V2).convert("RGB"))
    height, width = v2_u8.shape[:2]
    v0 = v0_u8.astype(np.float64)
    v2 = v2_u8.astype(np.float64)
    texture_source = np.asarray(
        Image.open(V1_TEXTURE_SOURCE)
        .convert("RGB")
        .resize((width, height), Image.Resampling.LANCZOS),
        dtype=np.float64,
    )

    # Reconstruct the exact v2 fine-grain paper behind the logo so removing the
    # approved smaller mark does not disturb the v2 background treatment.
    texture_box = (390, 165, 540, 205)
    tx0, ty0, tx1, ty1 = texture_box
    texture_patch = texture_source[ty0:ty1, tx0:tx1].mean(axis=2)
    texture_high_pass = texture_patch - gaussian_filter(texture_patch, 1.2)
    v1_texture_std = float(np.clip(texture_high_pass.std(), 0.75, 1.05))
    rng = np.random.default_rng(20260823)
    grain = gaussian_filter(rng.normal(size=(height, width)), 0.30)
    grain -= grain.mean()
    grain *= v1_texture_std / max(float(grain.std()), 1e-6)

    logo_roi_box = (585, 825, 775, 1010)
    rx0, ry0, rx1, ry1 = logo_roi_box
    v0_roi = v0[ry0:ry1, rx0:rx1]
    v2_roi = v2[ry0:ry1, rx0:rx1]
    v0_roi_sat = saturation(v0_roi)
    v0_roi_value = v0_roi.max(axis=2) / 255.0
    background_train = (v0_roi_sat < 0.075) & (v0_roi_value > 0.72)
    fitted_background = fit_quadratic_background(v0_roi, background_train)
    v2_paper_background = fitted_background + (
        grain[ry0:ry1, rx0:rx1] * V2_GRAIN_SCALE
    )[:, :, None]

    # Recover the original-size logo as a clean antialiased layer using the same
    # projection method as v1. No geometry is redrawn or inferred.
    blue_target = np.array([53.0, 82.0, 150.0])
    coral_target = np.array([232.0, 119.0, 98.0])
    projections = []
    errors = []
    for target in (blue_target, coral_target):
        vector = target[None, None, :] - fitted_background
        delta = v0_roi - fitted_background
        alpha = np.sum(delta * vector, axis=2) / np.maximum(
            np.sum(vector * vector, axis=2), 1e-6
        )
        alpha = np.clip(alpha, 0.0, 1.0)
        reconstruction = (
            fitted_background * (1.0 - alpha[:, :, None])
            + target * alpha[:, :, None]
        )
        errors.append(np.linalg.norm(v0_roi - reconstruction, axis=2))
        projections.append(alpha)

    choose_coral = errors[1] < errors[0]
    projected_alpha = np.where(choose_coral, projections[1], projections[0])
    target_saturation = np.where(choose_coral, 0.578, 0.647)
    background_saturation = float(np.median(v0_roi_sat[background_train]))
    saturation_alpha = np.clip(
        (v0_roi_sat - background_saturation)
        / np.maximum(target_saturation - background_saturation, 1e-6),
        0.0,
        1.0,
    )
    support = binary_dilation(v0_roi_sat > 0.09, iterations=2)
    logo_alpha = np.maximum(projected_alpha, saturation_alpha * 0.92)
    logo_alpha = np.where(support, logo_alpha, 0.0)
    logo_alpha[logo_alpha < 0.015] = 0.0
    source_logo_mask = logo_alpha > 0.015

    selected_target = np.where(
        choose_coral[:, :, None],
        coral_target[None, None, :],
        blue_target[None, None, :],
    )
    safe_alpha = np.maximum(logo_alpha[:, :, None], 0.08)
    foreground = (
        v0_roi - (1.0 - logo_alpha[:, :, None]) * fitted_background
    ) / safe_alpha
    foreground = np.where(
        logo_alpha[:, :, None] > 0.18, foreground, selected_target
    )
    foreground = np.clip(foreground, 0.0, 255.0)

    # Remove the smaller v2 logo completely, then place the v0-size source layer
    # at 64% local contrast relative to the retained v2 paper.
    v2_roi_sat = saturation(v2_roi)
    small_logo_mask = binary_dilation(v2_roi_sat > 0.075, iterations=2)
    edited_roi = v2_roi.copy()
    edited_roi[small_logo_mask] = v2_paper_background[small_logo_mask]

    full_contrast_render = v2_paper_background + logo_alpha[:, :, None] * (
        foreground - v2_paper_background
    )
    low_contrast_render = v2_paper_background + logo_alpha[:, :, None] * (
        LOGO_CONTRAST_SCALE * (foreground - v2_paper_background)
    )
    edited_roi[source_logo_mask] = low_contrast_render[source_logo_mask]

    v3 = v2.copy()
    v3[ry0:ry1, rx0:rx1] = edited_roi
    v3_u8 = np.clip(np.rint(v3), 0, 255).astype(np.uint8)
    Image.fromarray(v3_u8).save(FINAL, optimize=True)

    pixel_difference = np.any(v3_u8 != v2_u8, axis=2)
    allowed_logo_region = np.zeros((height, width), dtype=bool)
    allowed_logo_region[ry0:ry1, rx0:rx1] = small_logo_mask | source_logo_mask
    outside_allowed = pixel_difference & ~allowed_logo_region

    diff_visual = np.zeros_like(v2_u8)
    diff_visual[pixel_difference] = np.array([232, 72, 143], dtype=np.uint8)
    Image.fromarray(diff_visual).save(DIFF_MASK, optimize=True)
    Image.fromarray((source_logo_mask.astype(np.uint8) * 255)).save(
        INTERMEDIATE / "v0-logo-source-mask.png", optimize=True
    )
    Image.fromarray((allowed_logo_region.astype(np.uint8) * 255)).save(
        INTERMEDIATE / "v3-logo-edit-mask.png", optimize=True
    )

    top_margin = 58
    gap = 28
    canvas = Image.new("RGB", (width * 2 + gap, height + top_margin), (235, 232, 224))
    canvas.paste(Image.fromarray(v2_u8), (0, top_margin))
    canvas.paste(Image.fromarray(v3_u8), (width + gap, top_margin))
    draw = ImageDraw.Draw(canvas)
    font = load_label_font(23)
    draw.text((18, 16), "V2 — SMALL LOGO", font=font, fill=(35, 61, 115))
    draw.text(
        (width + gap + 18, 16),
        "V3 — V0 SIZE / LOW CONTRAST",
        font=font,
        fill=(35, 61, 115),
    )
    canvas.save(COMPARISON, optimize=True)

    # Objective measurements and exact invariant checks.
    source_mask_global = np.zeros((height, width), dtype=bool)
    source_mask_global[ry0:ry1, rx0:rx1] = source_logo_mask
    source_box = bbox_from_mask(source_mask_global)
    source_measurement = center_and_size(source_box)

    v0_visible_mask = np.zeros((height, width), dtype=bool)
    v0_visible_mask[ry0:ry1, rx0:rx1] = v0_roi_sat > 0.08
    v3_visible_mask = np.zeros((height, width), dtype=bool)
    v3_visible_mask[ry0:ry1, rx0:rx1] = (
        saturation(v3_u8.astype(np.float64))[ry0:ry1, rx0:rx1] > 0.08
    )
    v0_visible_box = bbox_from_mask(v0_visible_mask)
    v3_visible_box = bbox_from_mask(v3_visible_mask)
    v0_visible_measurement = center_and_size(v0_visible_box)
    v3_visible_measurement = center_and_size(v3_visible_box)

    low_u8 = np.clip(np.rint(low_contrast_render), 0, 255).astype(np.uint8)
    background_u8 = np.clip(np.rint(v2_paper_background), 0, 255).astype(np.uint8)
    full_u8 = np.clip(np.rint(full_contrast_render), 0, 255).astype(np.uint8)
    low_delta = low_u8.astype(np.float64) - background_u8.astype(np.float64)
    full_delta = full_u8.astype(np.float64) - background_u8.astype(np.float64)
    low_rms = float(np.sqrt(np.mean(np.square(low_delta[source_logo_mask]))))
    full_rms = float(np.sqrt(np.mean(np.square(full_delta[source_logo_mask]))))
    measured_contrast_ratio = low_rms / max(full_rms, 1e-6)

    title_box = (250, 295, 755, 485)
    info_box = (470, 580, 760, 750)
    central_object_box = (190, 570, 485, 835)
    paper_sample_box = (390, 165, 540, 205)

    metrics = {
        "sources": {
            "v0_logo_source": {
                "path": str(V0.relative_to(ROOT)),
                "sha256": sha256(V0),
            },
            "v2_edit_base": {
                "path": str(V2.relative_to(ROOT)),
                "sha256": sha256(V2),
            },
        },
        "output": {
            "path": str(FINAL.relative_to(ROOT)),
            "dimensions": {"width": width, "height": height},
        },
        "logo": {
            "requested_source_version": "v0",
            "contrast_scale": LOGO_CONTRAST_SCALE,
            "derivation": "0.80 linear scale squared = 0.64 area/contrast-energy factor",
            "source_mask_bbox": list(source_box),
            "applied_mask_bbox": list(source_box),
            "source_geometry": source_measurement,
            "applied_geometry": source_measurement,
            "v0_visible_color_bbox": list(v0_visible_box),
            "v3_visible_color_bbox": list(v3_visible_box),
            "v0_visible_geometry": v0_visible_measurement,
            "v3_visible_geometry": v3_visible_measurement,
            "visible_width_ratio_to_v0": round(
                v3_visible_measurement["width"]
                / v0_visible_measurement["width"],
                4,
            ),
            "visible_height_ratio_to_v0": round(
                v3_visible_measurement["height"]
                / v0_visible_measurement["height"],
                4,
            ),
            "visible_center_delta_to_v0": {
                "x": round(
                    v3_visible_measurement["center_x"]
                    - v0_visible_measurement["center_x"],
                    4,
                ),
                "y": round(
                    v3_visible_measurement["center_y"]
                    - v0_visible_measurement["center_y"],
                    4,
                ),
            },
            "measured_rms_contrast_ratio": round(measured_contrast_ratio, 4),
            "full_contrast_rms": round(full_rms, 4),
            "low_contrast_rms": round(low_rms, 4),
        },
        "changed_pixel_count": int(pixel_difference.sum()),
        "changed_pixel_fraction": round(float(pixel_difference.mean()), 6),
        "outside_allowed_changed_pixel_count": int(outside_allowed.sum()),
        "locked_regions": {
            "title": {
                "v2_hash": hash_region(v2_u8, title_box),
                "v3_hash": hash_region(v3_u8, title_box),
                "pixel_identical": hash_region(v2_u8, title_box)
                == hash_region(v3_u8, title_box),
            },
            "event_information": {
                "v2_hash": hash_region(v2_u8, info_box),
                "v3_hash": hash_region(v3_u8, info_box),
                "pixel_identical": hash_region(v2_u8, info_box)
                == hash_region(v3_u8, info_box),
            },
            "central_folded_object": {
                "v2_hash": hash_region(v2_u8, central_object_box),
                "v3_hash": hash_region(v3_u8, central_object_box),
                "pixel_identical": hash_region(v2_u8, central_object_box)
                == hash_region(v3_u8, central_object_box),
            },
            "v2_paper_sample": {
                "v2_hash": hash_region(v2_u8, paper_sample_box),
                "v3_hash": hash_region(v3_u8, paper_sample_box),
                "pixel_identical": hash_region(v2_u8, paper_sample_box)
                == hash_region(v3_u8, paper_sample_box),
            },
            "entire_image_outside_logo_roi": {
                "changed_pixel_count": int(
                    (
                        pixel_difference
                        & ~(
                            (np.mgrid[0:height, 0:width][1] >= rx0)
                            & (np.mgrid[0:height, 0:width][1] < rx1)
                            & (np.mgrid[0:height, 0:width][0] >= ry0)
                            & (np.mgrid[0:height, 0:width][0] < ry1)
                        )
                    ).sum()
                )
            },
        },
        "paths": {
            "final": str(FINAL.relative_to(ROOT)),
            "comparison": str(COMPARISON.relative_to(ROOT)),
            "diff_mask": str(DIFF_MASK.relative_to(ROOT)),
            "source_mask": str(
                (INTERMEDIATE / "v0-logo-source-mask.png").relative_to(ROOT)
            ),
            "edit_mask": str(
                (INTERMEDIATE / "v3-logo-edit-mask.png").relative_to(ROOT)
            ),
        },
        "prior_version_hashes": prior_hashes,
    }
    METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
