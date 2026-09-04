#!/usr/bin/env python3
"""Render the B3 v1 delta: grounded tabletop contact + softer side light.

The background is an ImageGen edit of the v0 B3 background. The bottle is
composited from the supplied source pixels using a deterministic silhouette
mask; geometry and the blank label are not regenerated or redrawn.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WORKSPACE = Path(__file__).resolve().parents[2]
V1 = WORKSPACE / "outputs" / "v1"
ASSETS = V1 / "assets"
KV_DIR = V1 / "kvs"

CANVAS = (1122, 1402)
BOARD_CREAM = (247, 250, 243)
CHARCOAL = (58, 58, 56)

FONT_AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
FONT_CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"

ENGLISH = "Quiet hours,\nmade tangible."
CHINESE = "让夜晚慢下来。"


def fit_cover(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / im.width, size[1] / im.height)
    resized = im.resize(
        (round(im.width * ratio), round(im.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def paste_scaled(base: Image.Image, asset: Image.Image, xy: tuple[int, int], width: int) -> None:
    height = round(asset.height * width / asset.width)
    scaled = asset.resize((width, height), Image.Resampling.LANCZOS)
    base.alpha_composite(scaled, xy)


def draw_locked_copy(base: Image.Image) -> None:
    # These coordinates and type settings match v0 B3.
    panel = Image.new("RGBA", base.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rectangle((44, 42, 610, 470), fill=BOARD_CREAM + (220,))
    base.alpha_composite(panel)

    logo = Image.open(ASSETS / "mori-wordmark_locked_v1.png").convert("RGBA")
    paste_scaled(base, logo, (72, 66), 235)

    draw = ImageDraw.Draw(base)
    en_font = ImageFont.truetype(FONT_AVENIR, 43)
    zh_font = ImageFont.truetype(FONT_CJK, 29)
    draw.multiline_text((72, 202), ENGLISH, font=en_font, fill=CHARCOAL + (255,), spacing=5)
    en_box = draw.multiline_textbbox((72, 202), ENGLISH, font=en_font, spacing=5)
    draw.text((72, en_box[3] + 20), CHINESE, font=zh_font, fill=CHARCOAL + (255,))


def product_silhouette_mask(size: tuple[int, int]) -> Image.Image:
    """Deterministic mask for the supplied bottle; excludes source backdrop."""
    scale = 4
    mask = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    d = ImageDraw.Draw(mask)

    body = [
        (271, 316), (314, 311), (407, 307), (615, 307),
        (705, 312), (746, 319), (746, 876), (739, 897),
        (716, 919), (681, 936), (645, 944), (350, 945),
        (316, 938), (291, 921), (276, 901), (271, 872),
    ]
    d.polygon([(x * scale, y * scale) for x, y in body], fill=255)
    d.rounded_rectangle(
        (418 * scale, 100 * scale, 604 * scale, 312 * scale),
        radius=13 * scale,
        fill=255,
    )
    mask = mask.resize(size, Image.Resampling.LANCZOS)
    return mask.filter(ImageFilter.GaussianBlur(0.45))


def add_contact_shadow(base: Image.Image, bottle_box: tuple[int, int, int, int]) -> None:
    x0, _, x1, y1 = bottle_box
    width = x1 - x0

    broad = Image.new("RGBA", base.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(broad)
    bd.ellipse(
        (x0 - width * 0.34, y1 - 18, x1 + width * 0.12, y1 + 32),
        fill=(24, 21, 19, 70),
    )
    broad = broad.filter(ImageFilter.GaussianBlur(23))
    base.alpha_composite(broad)

    contact = Image.new("RGBA", base.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(contact)
    cd.ellipse(
        (x0 + width * 0.05, y1 - 8, x1 - width * 0.05, y1 + 8),
        fill=(18, 16, 15, 118),
    )
    contact = contact.filter(ImageFilter.GaussianBlur(6))
    base.alpha_composite(contact)


def composite_locked_product(base: Image.Image) -> tuple[int, int, int, int]:
    source = Image.open(ASSETS / "launch-product_locked_v1.png").convert("RGBA")
    mask = product_silhouette_mask(source.size)
    source.putalpha(mask)

    crop_box = (245, 82, 772, 965)
    product = source.crop(crop_box)
    # Match the perceived bottle scale from v0 B3 while removing its photo tile.
    target_h = 482
    target_w = round(product.width * target_h / product.height)
    product = product.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Match the v0 B3 bottle position; its base now sits directly on the table.
    x = 220
    y = 844
    alpha_box = product.getchannel("A").getbbox()
    if alpha_box is None:
        raise RuntimeError("Product mask is empty")
    bottle_box = (x + alpha_box[0], y + alpha_box[1], x + alpha_box[2], y + alpha_box[3])
    add_contact_shadow(base, bottle_box)
    base.alpha_composite(product, (x, y))
    return bottle_box


def main() -> None:
    KV_DIR.mkdir(parents=True, exist_ok=True)
    background = Image.open(ASSETS / "b3-curtain-hour_tabletop-background_v1.png").convert("RGB")
    canvas = fit_cover(background, CANVAS).convert("RGBA")
    draw_locked_copy(canvas)
    bbox = composite_locked_product(canvas)
    out = KV_DIR / "kv-b3_curtain-hour-grounded_v1.png"
    canvas.convert("RGB").save(out, quality=96)
    print(f"Saved {out}; bottle_box={bbox}")


if __name__ == "__main__":
    main()
