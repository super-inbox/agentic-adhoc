from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v1"
SOURCE = ROOT / "inputs" / "01-product_master.png"

BG_ENTRY = OUT / "backgrounds" / "urban-entry-master.png"
BG_CAFE = OUT / "backgrounds" / "cafe-window-master.png"
BG_RAIN = OUT / "backgrounds" / "rainy-riverside-master.png"

ECOM_DIR = OUT / "ecommerce"
SOCIAL_DIR = OUT / "social"
CUTOUT_PATH = OUT / "product-cutout-exact.png"
CONTACT_SHEET_PATH = OUT / "contact-sheet.jpg"

FONT_MEDIUM = Path("/System/Library/Fonts/STHeiti Medium.ttc")
TEXT_COLOR = (35, 43, 45, 255)
SOCIAL_MATTE = (244, 246, 244, 255)


def extract_product() -> Image.Image:
    """Remove only the near-white studio background; keep source RGB pixels unchanged."""
    source = Image.open(SOURCE).convert("RGB")
    rgb = np.asarray(source).astype(np.float32)
    distance_from_white = np.sqrt(np.sum((255.0 - rgb) ** 2, axis=2))

    low, high = 24.0, 72.0
    t = np.clip((distance_from_white - low) / (high - low), 0.0, 1.0)
    smooth = t * t * (3.0 - 2.0 * t)
    # Keep the colored fabric and dark physical base while excluding the neutral
    # gray studio-floor shadow. The soft mask is capped by white-distance alpha,
    # so background pixels cannot become an opaque pale fringe.
    rgb_u8 = rgb.astype(np.uint8)
    channel_span = rgb_u8.max(axis=2).astype(np.int16) - rgb_u8.min(axis=2).astype(np.int16)
    luminance = rgb.mean(axis=2)
    subject_seed = ((channel_span > 12) & (luminance < 238.0)) | (luminance < 126.0)
    subject_seed[875:, :] = False
    seed_image = Image.fromarray(subject_seed.astype(np.uint8) * 255, "L")
    soft_subject = seed_image.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    soft_subject_alpha = np.asarray(soft_subject).astype(np.float32) / 255.0
    alpha = np.rint(np.minimum(smooth, soft_subject_alpha) * 255.0).astype(np.uint8)

    # The crop encloses the original product and its soft studio contact shadow.
    crop_box = (240, 170, 840, 940)
    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    cutout = Image.fromarray(rgba, "RGBA").crop(crop_box)

    # Identity check: extraction adds alpha only; source RGB in the crop is untouched.
    source_crop = np.asarray(source.crop(crop_box))
    assert np.array_equal(np.asarray(cutout)[..., :3], source_crop)
    CUTOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cutout.save(CUTOUT_PATH, compress_level=6)
    return cutout


def grade_background(image: Image.Image) -> Image.Image:
    """Unify only the scene plate into a restrained cool-neutral palette."""
    rgb = image.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(0.72)
    rgb = ImageEnhance.Contrast(rgb).enhance(0.96)
    cool = Image.new("RGB", rgb.size, (235, 241, 242))
    return Image.blend(rgb, cool, 0.055).convert("RGBA")


def fit_background(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    fitted = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    return grade_background(fitted)


def resize_product(product: Image.Image, height: int) -> Image.Image:
    width = round(product.width * height / product.height)
    return product.resize((width, height), Image.Resampling.LANCZOS)


def add_grounded_product(
    canvas: Image.Image,
    product: Image.Image,
    *,
    x: int,
    bottom: int,
    height: int,
    shadow_opacity: int = 55,
) -> tuple[int, int, int, int]:
    scaled = resize_product(product, height)
    y = bottom - scaled.height

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sw = round(scaled.width * 0.66)
    sh = max(18, round(height * 0.045))
    sx = x + (scaled.width - sw) // 2
    sy = bottom - round(sh * 0.56)
    sd.ellipse((sx, sy, sx + sw, sy + sh), fill=(22, 30, 32, shadow_opacity))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(12, round(height * 0.026))))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(scaled, (x, y))
    return (x, y, x + scaled.width, bottom)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_MEDIUM), size=size)


def draw_claim(canvas: Image.Image, claim: str, *, x: int, y: int, size: int) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.text((x, y), claim, font=font(size), fill=TEXT_COLOR, spacing=0)


def make_ecommerce(
    out_path: Path,
    bg_path: Path,
    product: Image.Image,
    *,
    claim: str | None,
    product_x: int,
    product_bottom: int,
    product_height: int,
    claim_x: int = 78,
) -> None:
    canvas = fit_background(bg_path, (1200, 1200))
    add_grounded_product(
        canvas,
        product,
        x=product_x,
        bottom=product_bottom,
        height=product_height,
    )
    if claim:
        draw_claim(canvas, claim, x=claim_x, y=78, size=58)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, compress_level=6)


def make_social(
    out_path: Path,
    bg_path: Path,
    product: Image.Image,
    *,
    claim: str,
    product_x: int,
    product_bottom_in_panel: int,
    product_height: int,
) -> None:
    canvas = Image.new("RGBA", (1080, 1350), SOCIAL_MATTE)
    photo_top = 270
    plate = fit_background(bg_path, (1080, 1080))
    canvas.alpha_composite(plate, (0, photo_top))
    draw_claim(canvas, claim, x=72, y=94, size=54)
    add_grounded_product(
        canvas,
        product,
        x=product_x,
        bottom=photo_top + product_bottom_in_panel,
        height=product_height,
        shadow_opacity=52,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, compress_level=6)


def create_contact_sheet() -> None:
    items = [
        (ECOM_DIR / "ecom-01-urban-entry-hero.png", "E01 · URBAN ENTRY"),
        (ECOM_DIR / "ecom-02-cafe-12h.png", "E02 · 12H"),
        (ECOM_DIR / "ecom-03-riverside-ipx4.png", "E03 · IPX4"),
        (SOCIAL_DIR / "social-01-entry-loop.png", "S01 · LOOP"),
        (SOCIAL_DIR / "social-02-cafe-12h.png", "S02 · 12H"),
        (SOCIAL_DIR / "social-03-riverside-ipx4.png", "S03 · IPX4"),
    ]
    sheet = Image.new("RGB", (2460, 1960), (239, 241, 239))
    draw = ImageDraw.Draw(sheet)
    draw.text((90, 54), "CITY COMMUTE · V1 CONTACT SHEET", font=font(36), fill=(35, 43, 45))
    for index, (path, label) in enumerate(items):
        col = index % 3
        row = index // 3
        x = 90 + col * 790
        y = 130 + row * 880
        cell = Image.open(path).convert("RGB")
        thumb = ImageOps.contain(cell, (720, 790), method=Image.Resampling.LANCZOS)
        px = x + (720 - thumb.width) // 2
        py = y + (790 - thumb.height) // 2
        sheet.paste(thumb, (px, py))
        draw.text((x, y + 808), label, font=font(24), fill=(73, 83, 85))
    sheet.save(CONTACT_SHEET_PATH, quality=92, subsampling=0)


def main() -> None:
    for path in (BG_ENTRY, BG_CAFE, BG_RAIN, SOURCE, FONT_MEDIUM):
        if not path.exists():
            raise FileNotFoundError(path)

    product = extract_product()

    make_ecommerce(
        ECOM_DIR / "ecom-01-urban-entry-hero.png",
        BG_ENTRY,
        product,
        claim=None,
        product_x=438,
        product_bottom=1070,
        product_height=720,
    )
    make_ecommerce(
        ECOM_DIR / "ecom-02-cafe-12h.png",
        BG_CAFE,
        product,
        claim="12 小时续航",
        product_x=520,
        product_bottom=1085,
        product_height=690,
        claim_x=760,
    )
    make_ecommerce(
        ECOM_DIR / "ecom-03-riverside-ipx4.png",
        BG_RAIN,
        product,
        claim="IPX4 防泼水",
        product_x=530,
        product_bottom=1080,
        product_height=670,
    )

    make_social(
        SOCIAL_DIR / "social-01-entry-loop.png",
        BG_ENTRY,
        product,
        claim="一体式挂环",
        product_x=396,
        product_bottom_in_panel=910,
        product_height=620,
    )
    make_social(
        SOCIAL_DIR / "social-02-cafe-12h.png",
        BG_CAFE,
        product,
        claim="12 小时续航",
        product_x=430,
        product_bottom_in_panel=935,
        product_height=600,
    )
    make_social(
        SOCIAL_DIR / "social-03-riverside-ipx4.png",
        BG_RAIN,
        product,
        claim="IPX4 防泼水",
        product_x=438,
        product_bottom_in_panel=925,
        product_height=590,
    )
    create_contact_sheet()


if __name__ == "__main__":
    main()
