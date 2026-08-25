from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import json
import math


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CANVAS = (1600, 2000)

PRODUCT_PATH = ROOT / "inputs" / "01-launch_product.png"
BACKGROUND_PATH = OUT / "sources" / "direction-b-dark-tabletop-soft-side-light.png"
V0_DARK_REFERENCE = ROOT / "outputs" / "v0" / "candidates" / "kv-b3.png"

FONT_SANS = "/opt/X11/share/system_fonts/Avenir Next.ttc"
FONT_CJK = "/opt/X11/share/system_fonts/STHeiti Medium.ttc"

APPROVED_EN = "Quiet hours, made tangible."
APPROVED_ZH = "让夜晚慢下来。"

COLORS = {
    "offwhite": "#F2EBDD",
    "terracotta": "#A44F35",
    "terracotta_dark": "#71311F",
    "charcoal": "#171513",
    "warm_black": "#0D0C0B",
    "grey": "#746D67",
}


def font(path, size, index=0):
    return ImageFont.truetype(path, size=size, index=index)


def cover(image, size, centering=(0.5, 0.5)):
    return ImageOps.fit(
        image.convert("RGB"),
        size,
        method=Image.Resampling.LANCZOS,
        centering=centering,
    )


def smoothstep(edge0, edge1, value):
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def make_feather_mask(size):
    """Opaque around the whole bottle; feathering happens only in surrounding backdrop pixels."""
    mask = Image.new("L", (size, size), 0)
    px = mask.load()
    scale = size / 1024.0

    left_fade_end = 220 * scale
    right_fade_start = 804 * scale
    top_fade_end = 70 * scale
    bottom_fade_start = 972 * scale

    for y in range(size):
        top_alpha = smoothstep(0, top_fade_end, y)
        bottom_alpha = 1.0 - smoothstep(bottom_fade_start, size, y)
        y_alpha = min(top_alpha, bottom_alpha)
        for x in range(size):
            left_alpha = smoothstep(0, left_fade_end, x)
            right_alpha = 1.0 - smoothstep(right_fade_start, size, x)
            px[x, y] = round(255 * min(left_alpha, right_alpha, y_alpha))
    return mask


def add_soft_ellipse(canvas, box, color, max_alpha, blur_radius):
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    mask = Image.new("L", CANVAS, 0)
    d = ImageDraw.Draw(mask)
    d.ellipse(box, fill=max_alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))
    wash = Image.new("RGBA", CANVAS, color)
    wash.putalpha(mask)
    canvas.alpha_composite(wash)


def draw_copy(canvas):
    draw = ImageDraw.Draw(canvas)
    panel = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rectangle((640, 72, 1518, 584), fill=(13, 12, 11, 228))
    canvas.alpha_composite(panel)

    en_font = font(FONT_SANS, 88)
    zh_font = font(FONT_CJK, 44)
    x, y = 718, 135
    draw.text((x, y), "Quiet hours,", font=en_font, fill=COLORS["offwhite"])
    draw.text((x, y + 116), "made tangible.", font=en_font, fill=COLORS["offwhite"])
    draw.text((x, y + 250), APPROVED_ZH, font=zh_font, fill=COLORS["offwhite"])
    draw.rectangle((x, 482, 1450, 494), fill=COLORS["terracotta"])
    return [640, 72, 878, 512]


def build_candidate():
    background = Image.open(BACKGROUND_PATH).convert("RGB")
    product = Image.open(PRODUCT_PATH).convert("RGB")
    canvas = cover(background, CANVAS).convert("RGBA")

    # Preserve the dark B-direction palette while making the side illumination broad and soft.
    add_soft_ellipse(
        canvas,
        (-180, 380, 1320, 1870),
        (139, 132, 124, 255),
        max_alpha=44,
        blur_radius=150,
    )

    # Extend a low, natural contact shadow into the generated tabletop before compositing.
    add_soft_ellipse(
        canvas,
        (310, 1560, 1245, 1745),
        (13, 12, 11, 255),
        max_alpha=72,
        blur_radius=52,
    )

    product_size = 1120
    product_xy = (240, 620)
    product_resized = product.resize((product_size, product_size), Image.Resampling.LANCZOS)
    mask = make_feather_mask(product_size)

    # No matte, border, pedestal, or floating drop shadow: retain the source's own tabletop contact.
    canvas.paste(product_resized, product_xy, mask)

    copy_box = draw_copy(canvas)
    logo_safe_zone = [82, 82, 220, 72]

    candidate_path = OUT / "candidates" / "kv-dark-direction-refinement-v1.png"
    preview_path = OUT / "previews" / "kv-dark-direction-refinement-v1-preview.jpg"
    mask_path = OUT / "sources" / "product-feather-mask-v1.png"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(candidate_path, quality=95)
    canvas.convert("RGB").resize((640, 800), Image.Resampling.LANCZOS).save(
        preview_path, quality=91, subsampling=0
    )
    mask.save(mask_path)

    metadata = {
        "version": "v1",
        "scope": "single dark-direction KV refinement for approval; no channel extensions",
        "selected_direction": "B / dark nocturnal direction",
        "selected_v0_candidate": None,
        "baseline_visual_reference": "outputs/v0/candidates/kv-b3.png",
        "canvas": {"width": 1600, "height": 2000, "aspect_ratio": "4:5"},
        "approved_copy": {"en": APPROVED_EN, "zh": APPROVED_ZH},
        "product_source": "inputs/01-launch_product.png",
        "product_placement": {
            "x": product_xy[0],
            "y": product_xy[1],
            "size": product_size,
            "policy": "uniform resize plus feathered surrounding-photo blend; product core remains pixel-identical to the resized source",
            "verified_core_bbox_in_source_coordinates": [265, 95, 755, 950]
        },
        "requested_delta": [
            "retain dark nocturnal direction",
            "remove floating white matte and drop shadow",
            "add a real full-width tabletop plane",
            "retain the source photo's natural surface contact and contact shadow",
            "replace hard spotlight with a broader softer left side light"
        ],
        "preserved": [
            "approved bilingual copy",
            "off-white, terracotta, charcoal palette",
            "dark architectural B-direction language",
            "product bottle shape, cap, liquid, and blank label",
            "medical-claim avoidance",
            "reserved logo clearspace; no invented logo"
        ],
        "artifact": "outputs/v1/candidates/kv-dark-direction-refinement-v1.png",
        "preview": "outputs/v1/previews/kv-dark-direction-refinement-v1-preview.jpg",
        "background_source": "outputs/v1/sources/direction-b-dark-tabletop-soft-side-light.png",
        "feather_mask": "outputs/v1/sources/product-feather-mask-v1.png",
        "copy_box": copy_box,
        "logo_safe_zone": logo_safe_zone
    }
    (OUT / "candidate-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return canvas.convert("RGB")


def build_comparison(v1_image):
    board = Image.new("RGB", (2440, 1580), "#F2EBDD")
    d = ImageDraw.Draw(board)
    title_font = font(FONT_SANS, 54)
    label_font = font(FONT_SANS, 32)
    note_font = font(FONT_CJK, 28)
    d.text((100, 72), "Dark-direction grounding refinement · v1", font=title_font, fill=COLORS["charcoal"])
    d.text((100, 145), "Requested delta only: tabletop contact + softer side light", font=note_font, fill=COLORS["grey"])
    d.rectangle((100, 210, 2340, 222), fill=COLORS["terracotta"])

    v0 = Image.open(V0_DARK_REFERENCE).convert("RGB")
    thumb_size = (940, 1175)
    left_x, right_x, y = 180, 1320, 280
    board.paste(cover(v0, thumb_size), (left_x, y))
    board.paste(cover(v1_image, thumb_size), (right_x, y))
    d.text((left_x, 1480), "v0 dark reference (framed / floating)", font=label_font, fill=COLORS["charcoal"])
    d.text((right_x, 1480), "v1 grounded refinement", font=label_font, fill=COLORS["terracotta_dark"])
    board.save(OUT / "dark-direction-v0-v1-comparison.png", quality=95)
    board.resize((1220, 790), Image.Resampling.LANCZOS).save(
        OUT / "previews" / "dark-direction-v0-v1-comparison-preview.jpg",
        quality=91,
        subsampling=0,
    )


def main():
    v1_image = build_candidate()
    build_comparison(v1_image)


if __name__ == "__main__":
    main()
