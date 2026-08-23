from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_dilation, gaussian_filter


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v1"
INTERMEDIATE = OUT / "intermediate"
SOURCE = ROOT / "inputs" / "01-revision_target.png"
GENERATED_SOURCE = INTERMEDIATE / "imagegen-edit-source.png"
FINAL = OUT / "summer-form-poster-local-revision-v1.png"
COMPARISON = OUT / "summer-form-poster-v1-comparison.png"
DIFF_MASK = OUT / "summer-form-poster-v1-diff-mask.png"
METRICS = INTERMEDIATE / "local-edit-metrics.json"


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


def hash_masked_pixels(
    image: np.ndarray, mask: np.ndarray, bounds: tuple[int, int, int, int]
) -> str:
    x0, y0, x1, y1 = bounds
    local_image = image[y0:y1, x0:x1]
    local_mask = mask[y0:y1, x0:x1]
    payload = local_mask.astype(np.uint8).tobytes() + local_image[local_mask].tobytes()
    return hashlib.sha256(payload).hexdigest()


def texture_metrics(image: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, float]:
    x0, y0, x1, y1 = box
    luminance = image[y0:y1, x0:x1].mean(axis=2)
    fine = luminance - gaussian_filter(luminance, 0.55)
    middle = gaussian_filter(luminance, 0.55) - gaussian_filter(luminance, 2.0)
    return {
        "mean_luminance": round(float(luminance.mean()), 4),
        "fine_grain_std": round(float(fine.std()), 4),
        "mid_grain_std": round(float(middle.std()), 4),
    }


def resize_float_plane(plane: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(
        Image.fromarray(plane.astype(np.float32), mode="F").resize(
            size, Image.Resampling.LANCZOS
        ),
        dtype=np.float64,
    )


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

    original_u8 = np.asarray(Image.open(SOURCE).convert("RGB"))
    height, width = original_u8.shape[:2]
    original = original_u8.astype(np.float64)
    generated = np.asarray(
        Image.open(GENERATED_SOURCE)
        .convert("RGB")
        .resize((width, height), Image.Resampling.LANCZOS),
        dtype=np.float64,
    )

    sat = saturation(original)
    value = original.max(axis=2) / 255.0
    yy, xx = np.mgrid[0:height, 0:width]

    # The large sheet begins around (126, 109). A small inset protects its edge,
    # outer backdrop, and cast shadow. The central folded object is explicitly
    # excluded because the client asked only for the background sheet texture.
    poster_interior = (xx >= 131) & (xx <= 797) & (yy >= 114) & (yy <= 1038)
    central_object_exclusion = (
        (xx >= 190) & (xx <= 485) & (yy >= 570) & (yy <= 835)
    )
    chromatic_art = sat > 0.115
    protected_art = binary_dilation(chromatic_art, iterations=2)
    neutral_paper = (sat < 0.105) & (value > 0.74)
    paper_mask = (
        poster_interior
        & neutral_paper
        & ~protected_art
        & ~central_object_exclusion
    )

    # Derive the intended finer-grain amplitude from a blank generated-paper
    # patch, while retaining the original image's color and low-frequency light.
    texture_box = (390, 165, 540, 205)
    tx0, ty0, tx1, ty1 = texture_box
    generated_patch = generated[ty0:ty1, tx0:tx1].mean(axis=2)
    generated_high_pass = generated_patch - gaussian_filter(generated_patch, 1.2)
    target_texture_std = float(np.clip(generated_high_pass.std(), 0.75, 1.05))

    paper_weight = paper_mask.astype(np.float64)
    denominator = gaussian_filter(paper_weight, 1.2)
    base_paper = np.empty_like(original)
    for channel in range(3):
        numerator = gaussian_filter(original[:, :, channel] * paper_weight, 1.2)
        fallback = gaussian_filter(original[:, :, channel], 1.2)
        base_paper[:, :, channel] = np.where(
            denominator > 0.08,
            numerator / np.maximum(denominator, 1e-6),
            fallback,
        )

    rng = np.random.default_rng(20260823)
    fine_noise = gaussian_filter(rng.normal(size=(height, width)), 0.30)
    fine_noise -= fine_noise.mean()
    fine_noise *= target_texture_std / max(float(fine_noise.std()), 1e-6)
    refined_paper = base_paper + fine_noise[:, :, None]

    final = original.copy()
    final[paper_mask] = refined_paper[paper_mask]

    # Extract the complete bottom-right logo (including its thin outer circle),
    # clear the old footprint with locally fitted paper, and scale the logo layer
    # to 80% around the exact same center.
    logo_roi_box = (585, 825, 775, 1010)
    rx0, ry0, rx1, ry1 = logo_roi_box
    roi = original[ry0:ry1, rx0:rx1]
    roi_sat = saturation(roi)
    roi_value = roi.max(axis=2) / 255.0
    background_train = (roi_sat < 0.075) & (roi_value > 0.72)
    fitted_background = fit_quadratic_background(roi, background_train)

    blue_target = np.array([53.0, 82.0, 150.0])
    coral_target = np.array([232.0, 119.0, 98.0])
    projections = []
    errors = []
    for target in (blue_target, coral_target):
        vector = target[None, None, :] - fitted_background
        delta = roi - fitted_background
        alpha = np.sum(delta * vector, axis=2) / np.maximum(
            np.sum(vector * vector, axis=2), 1e-6
        )
        alpha = np.clip(alpha, 0.0, 1.0)
        reconstruction = fitted_background * (1.0 - alpha[:, :, None]) + target * alpha[:, :, None]
        error = np.linalg.norm(roi - reconstruction, axis=2)
        projections.append(alpha)
        errors.append(error)

    choose_coral = errors[1] < errors[0]
    projected_alpha = np.where(choose_coral, projections[1], projections[0])
    target_saturation = np.where(choose_coral, 0.578, 0.647)
    background_saturation = float(np.median(roi_sat[background_train]))
    saturation_alpha = np.clip(
        (roi_sat - background_saturation)
        / np.maximum(target_saturation - background_saturation, 1e-6),
        0.0,
        1.0,
    )
    support = binary_dilation(roi_sat > 0.09, iterations=2)
    logo_alpha = np.maximum(projected_alpha, saturation_alpha * 0.92)
    logo_alpha = np.where(support, logo_alpha, 0.0)
    logo_alpha[logo_alpha < 0.015] = 0.0
    logo_mask = logo_alpha > 0.015

    local_logo_box = bbox_from_mask(logo_mask)
    lx0, ly0, lx1, ly1 = local_logo_box
    padding = 4
    cx0 = max(lx0 - padding, 0)
    cy0 = max(ly0 - padding, 0)
    cx1 = min(lx1 + padding + 1, logo_mask.shape[1])
    cy1 = min(ly1 + padding + 1, logo_mask.shape[0])

    alpha_crop = logo_alpha[cy0:cy1, cx0:cx1]
    fitted_crop = fitted_background[cy0:cy1, cx0:cx1]
    image_crop = roi[cy0:cy1, cx0:cx1]
    selected_target = np.where(
        choose_coral[cy0:cy1, cx0:cx1, None],
        coral_target[None, None, :],
        blue_target[None, None, :],
    )
    safe_alpha = np.maximum(alpha_crop[:, :, None], 0.08)
    foreground_crop = (
        image_crop - (1.0 - alpha_crop[:, :, None]) * fitted_crop
    ) / safe_alpha
    foreground_crop = np.where(
        alpha_crop[:, :, None] > 0.18, foreground_crop, selected_target
    )
    foreground_crop = np.clip(foreground_crop, 0.0, 255.0)
    premultiplied_crop = foreground_crop * alpha_crop[:, :, None]

    # Clear every antialiased remnant of the original logo.
    removal_mask = binary_dilation(logo_mask, iterations=3)
    roi_final = final[ry0:ry1, rx0:rx1]
    local_noise = fine_noise[ry0:ry1, rx0:rx1, None]
    logo_background = fitted_background + local_noise
    roi_final[removal_mask] = logo_background[removal_mask]
    final[ry0:ry1, rx0:rx1] = roi_final

    crop_height, crop_width = alpha_crop.shape
    scaled_width = int(round(crop_width * 0.80))
    scaled_height = int(round(crop_height * 0.80))
    scaled_alpha = resize_float_plane(alpha_crop, (scaled_width, scaled_height))
    scaled_alpha = np.clip(scaled_alpha, 0.0, 1.0)
    scaled_premultiplied = np.stack(
        [
            resize_float_plane(
                premultiplied_crop[:, :, channel], (scaled_width, scaled_height)
            )
            for channel in range(3)
        ],
        axis=2,
    )

    crop_center_x = rx0 + (cx0 + cx1 - 1) / 2.0
    crop_center_y = ry0 + (cy0 + cy1 - 1) / 2.0
    paste_x = int(round(crop_center_x - (scaled_width - 1) / 2.0))
    paste_y = int(round(crop_center_y - (scaled_height - 1) / 2.0))
    # Preserve the original integer-pixel vertical center after the odd/even
    # resampling change; horizontal centering is necessarily within 0.5 px.
    paste_y += 1
    destination = final[
        paste_y : paste_y + scaled_height, paste_x : paste_x + scaled_width
    ]
    destination[:] = scaled_premultiplied + destination * (
        1.0 - scaled_alpha[:, :, None]
    )

    final_u8 = np.clip(np.rint(final), 0, 255).astype(np.uint8)
    Image.fromarray(final_u8).save(FINAL, optimize=True)

    # Difference evidence: cyan = refined paper; magenta = logo footprint.
    pixel_difference = np.any(final_u8 != original_u8, axis=2)
    logo_allowed = (
        (xx >= rx0) & (xx < rx1) & (yy >= ry0) & (yy < ry1)
    )
    allowed_mask = paper_mask | logo_allowed
    outside_allowed = pixel_difference & ~allowed_mask

    diff_visual = np.zeros_like(original_u8)
    diff_visual[paper_mask & pixel_difference] = np.array([34, 190, 205], dtype=np.uint8)
    diff_visual[logo_allowed & pixel_difference] = np.array([232, 72, 143], dtype=np.uint8)
    Image.fromarray(diff_visual).save(DIFF_MASK, optimize=True)
    Image.fromarray((paper_mask.astype(np.uint8) * 255)).save(
        INTERMEDIATE / "paper-edit-mask.png", optimize=True
    )
    Image.fromarray((logo_alpha * 255.0).astype(np.uint8)).save(
        INTERMEDIATE / "logo-alpha-mask.png", optimize=True
    )

    # Native-resolution side-by-side comparison.
    top_margin = 58
    gap = 28
    canvas = Image.new("RGB", (width * 2 + gap, height + top_margin), (235, 232, 224))
    canvas.paste(Image.fromarray(original_u8), (0, top_margin))
    canvas.paste(Image.fromarray(final_u8), (width + gap, top_margin))
    draw = ImageDraw.Draw(canvas)
    font = load_label_font(23)
    draw.text((18, 16), "ORIGINAL", font=font, fill=(35, 61, 115))
    draw.text((width + gap + 18, 16), "V1 — LOCAL REVISION", font=font, fill=(35, 61, 115))
    canvas.save(COMPARISON, optimize=True)

    original_logo_mask_global = np.zeros((height, width), dtype=bool)
    original_logo_mask_global[ry0:ry1, rx0:rx1] = roi_sat > 0.08
    final_sat = saturation(final_u8.astype(np.float64))
    final_logo_mask_global = np.zeros((height, width), dtype=bool)
    final_logo_mask_global[ry0:ry1, rx0:rx1] = final_sat[ry0:ry1, rx0:rx1] > 0.08
    original_logo_box = bbox_from_mask(original_logo_mask_global)
    final_logo_box = bbox_from_mask(final_logo_mask_global)
    original_logo_measurement = center_and_size(original_logo_box)
    final_logo_measurement = center_and_size(final_logo_box)

    title_bounds = (250, 295, 755, 485)
    info_bounds = (470, 580, 760, 750)
    title_ink_mask = np.zeros((height, width), dtype=bool)
    info_ink_mask = np.zeros((height, width), dtype=bool)
    title_ink_mask[title_bounds[1] : title_bounds[3], title_bounds[0] : title_bounds[2]] = (
        sat[title_bounds[1] : title_bounds[3], title_bounds[0] : title_bounds[2]]
        > 0.08
    )
    info_ink_mask[info_bounds[1] : info_bounds[3], info_bounds[0] : info_bounds[2]] = (
        sat[info_bounds[1] : info_bounds[3], info_bounds[0] : info_bounds[2]]
        > 0.08
    )
    title_original_hash = hash_masked_pixels(original_u8, title_ink_mask, title_bounds)
    title_final_hash = hash_masked_pixels(final_u8, title_ink_mask, title_bounds)
    info_original_hash = hash_masked_pixels(original_u8, info_ink_mask, info_bounds)
    info_final_hash = hash_masked_pixels(final_u8, info_ink_mask, info_bounds)

    original_texture = texture_metrics(original, texture_box)
    final_texture = texture_metrics(final_u8.astype(np.float64), texture_box)

    def logo_palette(image: np.ndarray) -> dict[str, list[float]]:
        local = image[ry0:ry1, rx0:rx1].astype(np.float64)
        local_sat = saturation(local)
        core = local[local_sat > 0.35]
        blue = core[core[:, 2] > core[:, 0]]
        coral = core[core[:, 0] > core[:, 2]]
        return {
            "blue_median_rgb": [round(float(value), 2) for value in np.median(blue, axis=0)],
            "coral_median_rgb": [round(float(value), 2) for value in np.median(coral, axis=0)],
        }

    metrics = {
        "source_dimensions": {"width": width, "height": height},
        "output_dimensions": {
            "width": int(final_u8.shape[1]),
            "height": int(final_u8.shape[0]),
        },
        "changed_pixel_count": int(pixel_difference.sum()),
        "changed_pixel_fraction": round(float(pixel_difference.mean()), 6),
        "outside_allowed_changed_pixel_count": int(outside_allowed.sum()),
        "paper_edit_pixel_count": int((paper_mask & pixel_difference).sum()),
        "logo_region_changed_pixel_count": int((logo_allowed & pixel_difference).sum()),
        "logo": {
            "requested_scale": 0.8,
            "original_bbox": list(original_logo_box),
            "final_bbox": list(final_logo_box),
            "original": original_logo_measurement,
            "final": final_logo_measurement,
            "width_ratio": round(
                final_logo_measurement["width"] / original_logo_measurement["width"],
                4,
            ),
            "height_ratio": round(
                final_logo_measurement["height"] / original_logo_measurement["height"],
                4,
            ),
            "center_delta": {
                "x": round(
                    final_logo_measurement["center_x"]
                    - original_logo_measurement["center_x"],
                    4,
                ),
                "y": round(
                    final_logo_measurement["center_y"]
                    - original_logo_measurement["center_y"],
                    4,
                ),
            },
            "palette": {
                "original": logo_palette(original_u8),
                "final": logo_palette(final_u8),
            },
        },
        "paper_texture_sample_box": list(texture_box),
        "paper_texture": {
            "imagegen_reference_high_pass_std": round(target_texture_std, 4),
            "original": original_texture,
            "final": final_texture,
        },
        "title_ink": {
            "original_hash": title_original_hash,
            "final_hash": title_final_hash,
            "pixel_identical": title_original_hash == title_final_hash,
        },
        "event_information_ink": {
            "original_hash": info_original_hash,
            "final_hash": info_final_hash,
            "pixel_identical": info_original_hash == info_final_hash,
        },
        "approved_colored_art_outside_logo": {
            "max_channel_difference": int(
                np.abs(final_u8.astype(np.int16) - original_u8.astype(np.int16))[
                    protected_art & ~logo_allowed
                ].max(initial=0)
            )
        },
        "outer_scene": {
            "changed_pixel_count": int(
                (pixel_difference & ~poster_interior & ~logo_allowed).sum()
            )
        },
        "central_folded_object_exclusion": {
            "changed_pixel_count": int(
                (pixel_difference & central_object_exclusion & ~logo_allowed).sum()
            )
        },
        "paths": {
            "source": str(SOURCE.relative_to(ROOT)),
            "generated_texture_source": str(GENERATED_SOURCE.relative_to(ROOT)),
            "final": str(FINAL.relative_to(ROOT)),
            "comparison": str(COMPARISON.relative_to(ROOT)),
            "diff_mask": str(DIFF_MASK.relative_to(ROOT)),
        },
    }
    METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
