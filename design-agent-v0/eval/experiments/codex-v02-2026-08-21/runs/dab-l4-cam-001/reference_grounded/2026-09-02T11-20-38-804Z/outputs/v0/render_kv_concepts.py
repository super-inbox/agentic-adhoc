#!/usr/bin/env python3
"""Render the v0 MORI KV hypotheses from locked source assets.

Generated backgrounds are used only as atmosphere. The MORI wordmark is
extracted from the supplied brand board, and the supplied product photograph is
placed as an untouched, proportional image tile so bottle geometry and the
blank label remain source-grounded.
"""

from pathlib import Path
import shutil
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


WORKSPACE = Path(__file__).resolve().parents[2]
OUT = WORKSPACE / "outputs" / "v0"
INPUTS = WORKSPACE / "inputs"
BG_DIR = OUT / "generated-backgrounds"
KV_DIR = OUT / "kvs"
ASSET_DIR = OUT / "assets"
BOARD_DIR = OUT / "boards"

CANVAS = (1122, 1402)
CREAM = (237, 232, 212)
BOARD_CREAM = (247, 250, 243)
TERRACOTTA = (175, 84, 63)
CHARCOAL = (58, 58, 56)
PALE_BLUE = (183, 210, 217)
OLIVE = (135, 148, 102)

FONT_AVENIR = "/opt/X11/share/system_fonts/Avenir Next.ttc"
FONT_DIDOT = "/opt/X11/share/system_fonts/Supplemental/Didot.ttc"
FONT_PINGFANG = "/System/Library/Fonts/Hiragino Sans GB.ttc"

ENGLISH = "Quiet hours,\nmade tangible."
CHINESE = "让夜晚慢下来。"


def fit_cover(im: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """Resize and center-crop an image to exactly fill size."""
    ratio = max(size[0] / im.width, size[1] / im.height)
    resized = im.resize(
        (round(im.width * ratio), round(im.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def make_alpha_from_background(crop: Image.Image, bg_rgb: Tuple[int, int, int], threshold: float = 7.0) -> Image.Image:
    arr = np.asarray(crop.convert("RGB"), dtype=np.float32)
    bg = np.array(bg_rgb, dtype=np.float32)
    dist = np.linalg.norm(arr - bg, axis=2)
    alpha = np.clip((dist - threshold) * 7.5, 0, 255).astype(np.uint8)
    return Image.fromarray(alpha, mode="L")


def extract_locked_assets() -> Tuple[Image.Image, Image.Image, Image.Image]:
    brand = Image.open(INPUTS / "01-brand_guideline.png").convert("RGB")
    product_source = INPUTS / "02-launch_product.png"
    product = Image.open(product_source).convert("RGB")

    # Exact wordmark silhouette from the supplied board; subtitle excluded.
    logo_crop = brand.crop((260, 68, 590, 165))
    logo_alpha = make_alpha_from_background(logo_crop, BOARD_CREAM, threshold=5.0)
    logo = Image.new("RGBA", logo_crop.size, CHARCOAL + (0,))
    logo.putalpha(logo_alpha)
    logo_box = logo.getbbox()
    if logo_box:
        logo = logo.crop(logo_box)
    logo.save(ASSET_DIR / "mori-wordmark_locked.png")

    # Optional exact brand leaf token for the overview board only.
    leaf_crop = brand.crop((900, 62, 1082, 244))
    leaf_alpha = make_alpha_from_background(leaf_crop, BOARD_CREAM, threshold=7.0)
    leaf = leaf_crop.convert("RGBA")
    leaf.putalpha(leaf_alpha)
    leaf_box = leaf.getbbox()
    if leaf_box:
        leaf = leaf.crop(leaf_box)
    leaf.save(ASSET_DIR / "mori-leaf_locked.png")

    shutil.copyfile(product_source, ASSET_DIR / "launch-product_locked.png")
    return logo, leaf, product


def paste_scaled(base: Image.Image, asset: Image.Image, xy: Tuple[int, int], width: int) -> None:
    height = round(asset.height * width / asset.width)
    scaled = asset.resize((width, height), Image.Resampling.LANCZOS)
    base.alpha_composite(scaled, xy)


def rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def paste_product_tile(
    base: Image.Image,
    product: Image.Image,
    xy: Tuple[int, int],
    size: int,
    border: int = 12,
    radius: int = 0,
    shadow: int = 24,
) -> None:
    """Place the supplied full product photo as a proportional, unedited tile."""
    outer_size = size + border * 2
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_box = Image.new("RGBA", (outer_size, outer_size), (0, 0, 0, 0))
    shadow_box.putalpha(rounded_mask((outer_size, outer_size), radius + border))
    solid_shadow = Image.new("RGBA", (outer_size, outer_size), CHARCOAL + (80,))
    solid_shadow.putalpha(shadow_box.getchannel("A"))
    shadow_layer.alpha_composite(solid_shadow, (xy[0] + 7, xy[1] + 12))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow))
    base.alpha_composite(shadow_layer)

    frame = Image.new("RGBA", (outer_size, outer_size), CREAM + (255,))
    frame.putalpha(rounded_mask((outer_size, outer_size), radius + border))
    base.alpha_composite(frame, xy)

    tile = product.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
    if radius:
        tile.putalpha(rounded_mask((size, size), radius))
    base.alpha_composite(tile, (xy[0] + border, xy[1] + border))


def text_panel(base: Image.Image, box: Tuple[int, int, int, int], opacity: int = 208) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle(box, fill=BOARD_CREAM + (opacity,))
    base.alpha_composite(overlay)


def draw_copy(
    base: Image.Image,
    xy: Tuple[int, int],
    style: str,
    fill: Tuple[int, int, int] = CHARCOAL,
    align: str = "left",
) -> None:
    draw = ImageDraw.Draw(base)
    if style == "serif":
        en_font = ImageFont.truetype(FONT_DIDOT, 61)
        zh_font = ImageFont.truetype(FONT_PINGFANG, 31)
        spacing = 2
    elif style == "sans_small":
        en_font = ImageFont.truetype(FONT_AVENIR, 43)
        zh_font = ImageFont.truetype(FONT_PINGFANG, 29)
        spacing = 5
    else:
        en_font = ImageFont.truetype(FONT_AVENIR, 51)
        zh_font = ImageFont.truetype(FONT_PINGFANG, 31)
        spacing = 5

    draw.multiline_text(xy, ENGLISH, font=en_font, fill=fill + (255,), spacing=spacing, align=align)
    en_box = draw.multiline_textbbox(xy, ENGLISH, font=en_font, spacing=spacing, align=align)
    zh_y = en_box[3] + 20
    draw.text((xy[0], zh_y), CHINESE, font=zh_font, fill=fill + (255,))


CONFIG: Dict[str, Dict] = {
    "a1": {
        "bg": "territory-a_still-horizon_a1-clay-horizon.png",
        "out": "kv-a1_clay-horizon.png",
        "logo": (70, 64, 248),
        "copy": (70, 202, "serif"),
        "product": (272, 726, 554),
    },
    "a2": {
        "bg": "territory-a_still-horizon_a2-paper-fold.png",
        "out": "kv-a2_paper-fold.png",
        "logo": (70, 64, 248),
        "copy": (70, 202, "serif"),
        "product": (510, 710, 512),
    },
    "a3": {
        "bg": "territory-a_still-horizon_a3-quiet-aperture.png",
        "out": "kv-a3_quiet-aperture.png",
        "logo": (70, 64, 248),
        "copy": (70, 202, "serif"),
        "product": (140, 733, 500),
    },
    "b1": {
        "bg": "territory-b_held-moment_b1-linen-pause.png",
        "out": "kv-b1_linen-pause.png",
        "panel": (48, 42, 620, 470, 214),
        "logo": (75, 66, 235),
        "copy": (75, 202, "sans_small"),
        "product": (474, 750, 548),
    },
    "b2": {
        "bg": "territory-b_held-moment_b2-ritual-tray.png",
        "out": "kv-b2_ritual-tray.png",
        "panel": (45, 42, 622, 470, 198),
        "logo": (72, 66, 235),
        "copy": (72, 202, "sans_small"),
        "product": (328, 538, 440),
    },
    "b3": {
        "bg": "territory-b_held-moment_b3-curtain-hour.png",
        "out": "kv-b3_curtain-hour.png",
        "panel": (44, 42, 610, 470, 220),
        "logo": (72, 66, 235),
        "copy": (72, 202, "sans_small"),
        "product": (82, 765, 532),
    },
    "c1": {
        "bg": "territory-c_tactile-echo_c1-vein-relief.png",
        "out": "kv-c1_vein-relief.png",
        "panel": (44, 42, 1068, 318, 194),
        "logo": (70, 64, 226),
        "copy": (416, 72, "sans_small"),
        "product": (332, 500, 434),
    },
    "c2": {
        "bg": "territory-c_tactile-echo_c2-quiet-ripple.png",
        "out": "kv-c2_quiet-ripple.png",
        "logo": (70, 64, 238),
        "copy": (70, 202, "serif"),
        "product": (525, 704, 500),
    },
    "c3": {
        "bg": "territory-c_tactile-echo_c3-woven-signal.png",
        "out": "kv-c3_woven-signal.png",
        "panel": (390, 44, 1077, 346, 218),
        "logo": (60, 64, 238),
        "copy": (430, 78, "sans_small"),
        "product": (548, 520, 430),
    },
}


def render_kvs(logo: Image.Image, product: Image.Image) -> Dict[str, Path]:
    rendered: Dict[str, Path] = {}
    for code, cfg in CONFIG.items():
        bg = fit_cover(Image.open(BG_DIR / cfg["bg"]).convert("RGB"), CANVAS).convert("RGBA")
        if "panel" in cfg:
            x0, y0, x1, y1, opacity = cfg["panel"]
            text_panel(bg, (x0, y0, x1, y1), opacity)
        lx, ly, lw = cfg["logo"]
        paste_scaled(bg, logo, (lx, ly), lw)
        cx, cy, style = cfg["copy"]
        draw_copy(bg, (cx, cy), style)
        px, py, ps = cfg["product"]
        paste_product_tile(bg, product, (px, py), ps, border=12, radius=0, shadow=24)
        out_path = KV_DIR / cfg["out"]
        bg.convert("RGB").save(out_path, quality=96)
        rendered[code] = out_path
    return rendered


def make_overview(rendered: Dict[str, Path], leaf: Image.Image) -> Path:
    board_w, board_h = 1710, 2440
    board = Image.new("RGBA", (board_w, board_h), BOARD_CREAM + (255,))
    d = ImageDraw.Draw(board)
    title_font = ImageFont.truetype(FONT_AVENIR, 43)
    sub_font = ImageFont.truetype(FONT_PINGFANG, 24)
    territory_font = ImageFont.truetype(FONT_AVENIR, 26)
    meta_font = ImageFont.truetype(FONT_PINGFANG, 20)
    code_font = ImageFont.truetype(FONT_AVENIR, 22)

    d.text((74, 58), "MORI — KV TERRITORIES / V0", font=title_font, fill=CHARCOAL + (255,))
    d.text((74, 124), "内部方向选择：先选 1 个 KV，再开始官网 hero、Instagram 竖版与邮件头图。", font=sub_font, fill=CHARCOAL + (255,))
    paste_scaled(board, leaf, (1490, 48), 120)
    d.line((74, 178, 1636, 178), fill=TERRACOTTA + (255,), width=4)

    columns = [
        ("A — STILL HORIZON", "静止布景 · 纸张 / 墙面 / 单灯", ["a1", "a2", "a3"]),
        ("B — HELD MOMENT", "亲密仪式 · 亚麻 / 陶盘 / 透光帘", ["b1", "b2", "b3"]),
        ("C — TACTILE ECHO", "品牌触感 · 压纹 / 浅弧 / 编织", ["c1", "c2", "c3"]),
    ]
    x_positions = [74, 610, 1146]
    thumb_w, thumb_h = 470, 587

    for x, (title, meta, codes) in zip(x_positions, columns):
        d.text((x, 218), title, font=territory_font, fill=CHARCOAL + (255,))
        d.text((x, 260), meta, font=meta_font, fill=TERRACOTTA + (255,))
        for row, code in enumerate(codes):
            y = 315 + row * 674
            thumb = fit_cover(Image.open(rendered[code]).convert("RGB"), (thumb_w, thumb_h)).convert("RGBA")
            shadow = Image.new("RGBA", (thumb_w + 24, thumb_h + 24), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.rectangle((12, 12, thumb_w + 12, thumb_h + 12), fill=CHARCOAL + (45,))
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            board.alpha_composite(shadow, (x - 12, y - 8))
            board.alpha_composite(thumb, (x, y))
            d.rectangle((x + 18, y + 18, x + 82, y + 58), fill=TERRACOTTA + (244,))
            d.text((x + 29, y + 23), code.upper(), font=code_font, fill=BOARD_CREAM + (255,))

    d.text((74, 2350), "评审提示：A 偏标志性与适配性；B 偏亲密与仪式感；C 偏触感与品牌资产化。此板不预设推荐项。", font=meta_font, fill=CHARCOAL + (255,))
    out_path = BOARD_DIR / "mori-kv-territory-overview_v0.png"
    board.convert("RGB").save(out_path, quality=96)
    return out_path


def main() -> None:
    for directory in (KV_DIR, ASSET_DIR, BOARD_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    logo, leaf, product = extract_locked_assets()
    rendered = render_kvs(logo, product)
    make_overview(rendered, leaf)
    print(f"Rendered {len(rendered)} KVs and 1 overview board.")


if __name__ == "__main__":
    main()
