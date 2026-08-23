from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import json


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CANVAS = (1600, 2000)

PRODUCT_PATH = ROOT / "inputs" / "01-launch_product.png"
BG_PATHS = {
    "A": OUT / "sources" / "direction-a-soft-field.png",
    "B": OUT / "sources" / "direction-b-threshold.png",
    "C": OUT / "sources" / "direction-c-tactile-ribbon.png",
}

COLORS = {
    "offwhite": "#F2EBDD",
    "offwhite2": "#E6DCCB",
    "terracotta": "#A44F35",
    "terracotta_dark": "#71311F",
    "charcoal": "#171513",
    "warm_black": "#0D0C0B",
    "grey": "#777069",
}

FONT_SERIF = "/opt/X11/share/system_fonts/NewYork.ttf"
FONT_SANS = "/opt/X11/share/system_fonts/Avenir Next.ttc"
FONT_CJK = "/opt/X11/share/system_fonts/STHeiti Medium.ttc"

APPROVED_EN = "Quiet hours, made tangible."
APPROVED_ZH = "让夜晚慢下来。"


def font(path, size, index=0):
    return ImageFont.truetype(path, size=size, index=index)


def cover(im, size, centering=(0.5, 0.5)):
    return ImageOps.fit(im.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=centering)


def paste_panel(canvas, im, box, centering=(0.5, 0.5)):
    x, y, w, h = box
    canvas.paste(cover(im, (w, h), centering), (x, y))


def place_product(canvas, product, box, matte=20, shadow=22, shadow_offset=(0, 18)):
    """Place the supplied product photo without retouching, warping, recoloring, or overlays."""
    x, y, size = box
    photo = product.resize((size, size), Image.Resampling.LANCZOS)

    if shadow:
        layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        mask = Image.new("L", (size + matte * 2, size + matte * 2), 0)
        md = ImageDraw.Draw(mask)
        md.rectangle((0, 0, mask.width - 1, mask.height - 1), fill=120)
        mask = mask.filter(ImageFilter.GaussianBlur(shadow))
        shadow_patch = Image.new("RGBA", mask.size, (0, 0, 0, 100))
        shadow_patch.putalpha(mask)
        layer.alpha_composite(shadow_patch, (x - matte + shadow_offset[0], y - matte + shadow_offset[1]))
        canvas.alpha_composite(layer)

    draw = ImageDraw.Draw(canvas)
    if matte:
        draw.rectangle((x - matte, y - matte, x + size + matte, y + size + matte), fill=COLORS["offwhite"])
    canvas.alpha_composite(photo.convert("RGBA"), (x, y))


def tracked_text(draw, xy, text, text_font, fill, spacing=0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=text_font, fill=fill)
        x += draw.textlength(ch, font=text_font) + spacing


def copy_block(draw, x, y, width, *, tone="dark", style="serif", en_size=102,
               zh_size=46, line_gap=18, line_break=True, tracking=0, align="left"):
    fill = COLORS["offwhite"] if tone == "light" else COLORS["charcoal"]
    en_font = font(FONT_SERIF if style == "serif" else FONT_SANS, en_size)
    zh_font = font(FONT_CJK, zh_size)

    lines = ["Quiet hours,", "made tangible."] if line_break else [APPROVED_EN]
    yy = y
    for line in lines:
        if tracking:
            measured = sum(draw.textlength(c, font=en_font) for c in line) + tracking * max(0, len(line) - 1)
        else:
            measured = draw.textlength(line, font=en_font)
        xx = x if align == "left" else x + width - measured
        if tracking:
            tracked_text(draw, (xx, yy), line, en_font, fill, tracking)
        else:
            draw.text((xx, yy), line, font=en_font, fill=fill)
        bbox = draw.textbbox((xx, yy), line, font=en_font)
        yy = bbox[3] + line_gap

    yy += 16
    measured_zh = draw.textlength(APPROVED_ZH, font=zh_font)
    xx = x if align == "left" else x + width - measured_zh
    draw.text((xx, yy), APPROVED_ZH, font=zh_font, fill=fill)
    return (x, y, width, yy + zh_size - y)


def base_background(bg, centering=(0.5, 0.5)):
    return cover(bg, CANVAS, centering).convert("RGBA")


def candidate_a1(bg, product):
    c = base_background(bg, (0.56, 0.58))
    d = ImageDraw.Draw(c)
    d.rectangle((92, 90, 1508, 560), fill=COLORS["offwhite"])
    d.rectangle((92, 90, 116, 560), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 170, 160, 1180, style="serif", en_size=112, zh_size=48, line_break=False)
    place_product(c, product, (310, 760, 980), matte=22)
    d.rectangle((92, 1880, 1508, 1892), fill=COLORS["terracotta"])
    return c, copy_box, (310, 760, 980), (1260, 1914, 220, 64)


def candidate_a2(bg, product):
    c = base_background(bg, (0.37, 0.52))
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, 660, 2000), fill=COLORS["offwhite"])
    d.rectangle((598, 0, 660, 2000), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 104, 270, 430, style="serif", en_size=90, zh_size=44, line_break=True)
    place_product(c, product, (555, 760, 930), matte=18)
    d.rectangle((104, 1780, 500, 1791), fill=COLORS["charcoal"])
    return c, copy_box, (555, 760, 930), (104, 112, 220, 72)


def candidate_a3(bg, product):
    c = base_background(bg, (0.58, 0.62))
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, 1600, 520), fill=COLORS["terracotta_dark"])
    copy_box = copy_block(d, 145, 125, 1220, tone="light", style="serif", en_size=108, zh_size=46, line_break=False)
    place_product(c, product, (180, 620, 1240), matte=0, shadow=28)
    d.rectangle((0, 1900, 1600, 2000), fill=COLORS["offwhite"])
    return c, copy_box, (180, 620, 1240), (1290, 1920, 220, 56)


def candidate_b1(bg, product):
    c = base_background(bg, (0.58, 0.52))
    d = ImageDraw.Draw(c)
    d.rectangle((82, 72, 778, 530), fill=COLORS["charcoal"])
    copy_box = copy_block(d, 132, 130, 590, tone="light", style="sans", en_size=86, zh_size=44, line_break=True, tracking=1)
    place_product(c, product, (505, 850, 900), matte=18)
    d.rectangle((130, 1810, 395, 1822), fill=COLORS["terracotta"])
    return c, copy_box, (505, 850, 900), (1280, 96, 220, 72)


def candidate_b2(bg, product):
    c = base_background(bg, (0.55, 0.5))
    d = ImageDraw.Draw(c)
    d.rectangle((808, 88, 1514, 666), fill=COLORS["offwhite"])
    d.rectangle((808, 88, 840, 666), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 890, 180, 540, style="sans", en_size=82, zh_size=43, line_break=True)
    place_product(c, product, (86, 860, 1000), matte=20)
    d.rectangle((1230, 1720, 1514, 1733), fill=COLORS["offwhite"])
    return c, copy_box, (86, 860, 1000), (96, 110, 220, 72)


def candidate_b3(bg, product):
    c = Image.new("RGBA", CANVAS, COLORS["warm_black"])
    paste_panel(c, bg, (0, 0, 640, 2000), centering=(0.72, 0.5))
    d = ImageDraw.Draw(c)
    d.rectangle((640, 0, 680, 2000), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 770, 140, 690, tone="light", style="sans", en_size=88, zh_size=44, line_break=True)
    place_product(c, product, (360, 650, 1160), matte=18)
    d.rectangle((770, 525, 1448, 536), fill=COLORS["terracotta"])
    return c, copy_box, (360, 650, 1160), (98, 110, 220, 72)


def candidate_c1(bg, product):
    c = base_background(bg, (0.50, 0.54))
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, 1600, 540), fill=COLORS["offwhite"])
    d.rectangle((0, 500, 1600, 540), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 140, 120, 1220, style="serif", en_size=108, zh_size=46, line_break=False)
    place_product(c, product, (310, 720, 980), matte=22)
    return c, copy_box, (310, 720, 980), (1280, 1810, 220, 72)


def candidate_c2(bg, product):
    c = Image.new("RGBA", CANVAS, COLORS["offwhite"])
    paste_panel(c, bg, (0, 0, 1600, 1160), centering=(0.5, 0.42))
    d = ImageDraw.Draw(c)
    d.rectangle((0, 1120, 1600, 1160), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 100, 1325, 480, style="serif", en_size=82, zh_size=43, line_break=True)
    place_product(c, product, (665, 1040, 855), matte=18)
    d.rectangle((100, 1830, 510, 1841), fill=COLORS["charcoal"])
    return c, copy_box, (665, 1040, 855), (100, 1200, 220, 72)


def candidate_c3(bg, product):
    c = base_background(bg, (0.50, 0.56))
    d = ImageDraw.Draw(c)
    d.rectangle((76, 72, 1020, 512), fill=COLORS["offwhite"])
    d.rectangle((76, 72, 100, 512), fill=COLORS["terracotta"])
    copy_box = copy_block(d, 150, 145, 790, style="sans", en_size=86, zh_size=44, line_break=True)
    place_product(c, product, (170, 600, 1260), matte=0, shadow=30)
    d.rectangle((80, 1915, 1520, 2000), fill=COLORS["terracotta_dark"])
    return c, copy_box, (170, 600, 1260), (1260, 1918, 220, 56)


SPECS = [
    ("A1", "A", "Paper halo / 纸面光晕", candidate_a1),
    ("A2", "A", "Quiet margin / 安静留边", candidate_a2),
    ("A3", "A", "Clay header / 陶土标题带", candidate_a3),
    ("B1", "B", "Portal focus / 门廊聚焦", candidate_b1),
    ("B2", "B", "Edge light / 边缘光", candidate_b2),
    ("B3", "B", "Shadow split / 暗面切分", candidate_b3),
    ("C1", "C", "Folded touch / 折叠触感", candidate_c1),
    ("C2", "C", "Close fabric / 近身织物", candidate_c2),
    ("C3", "C", "Ribbon gesture / 缎带轨迹", candidate_c3),
]

DIRECTIONS = {
    "A": ("Soft Field / 柔光留白", "Quietest and most product-forward; paper + linen + restrained clay accent."),
    "B": ("Night Threshold / 夜间门廊", "Architectural transition into night; strongest contrast and ritual cue."),
    "C": ("Tactile Ribbon / 触感轨迹", "Close material detail; strongest tactile and branded color presence."),
}


def make_board(images):
    w, h = 2800, 3360
    board = Image.new("RGB", (w, h), COLORS["offwhite"])
    d = ImageDraw.Draw(board)
    title_font = font(FONT_SANS, 62)
    sub_font = font(FONT_CJK, 32)
    dir_font = font(FONT_SANS, 44)
    note_font = font(FONT_SANS, 27)
    code_font = font(FONT_SANS, 30)

    d.text((120, 86), "KV hypothesis selection board · v0", font=title_font, fill=COLORS["charcoal"])
    d.text((120, 170), "3 directions / 9 low-cost hypotheses / no channel extension yet", font=sub_font, fill=COLORS["grey"])
    d.rectangle((120, 238, 2680, 250), fill=COLORS["terracotta"])

    left = 120
    label_w = 520
    thumb_w, thumb_h = 570, 712
    gap = 54
    row_y = [360, 1340, 2320]

    for row, direction in enumerate(("A", "B", "C")):
        y = row_y[row]
        name, note = DIRECTIONS[direction]
        d.text((left, y + 12), f"Direction {direction}", font=dir_font, fill=COLORS["terracotta_dark"])
        d.text((left, y + 78), name, font=sub_font, fill=COLORS["charcoal"])
        # Manually wrapped internal note; not part of the campaign artwork.
        words = note.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if d.textlength(test, font=note_font) > 410:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        for idx, line in enumerate(lines):
            d.text((left, y + 150 + idx * 38), line, font=note_font, fill=COLORS["grey"])

        for col, code in enumerate((f"{direction}1", f"{direction}2", f"{direction}3")):
            x = left + label_w + col * (thumb_w + gap)
            thumb = cover(images[code], (thumb_w, thumb_h))
            shadow = Image.new("RGBA", (thumb_w + 32, thumb_h + 32), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.rectangle((16, 16, thumb_w + 15, thumb_h + 15), fill=(0, 0, 0, 42))
            shadow = shadow.filter(ImageFilter.GaussianBlur(12))
            board.paste(shadow, (x - 16, y - 6), shadow)
            board.paste(thumb, (x, y))
            d.rectangle((x, y + thumb_h + 18, x + thumb_w, y + thumb_h + 70), fill=COLORS["charcoal"])
            d.text((x + 18, y + thumb_h + 25), code, font=code_font, fill=COLORS["offwhite"])

    footer_y = 3260
    d.rectangle((120, footer_y - 28, 2680, footer_y - 16), fill=COLORS["terracotta"])
    d.text((120, footer_y), "Selection checkpoint: choose one code (A1–C3) before hero / Instagram / email adaptations.", font=note_font, fill=COLORS["charcoal"])
    return board


def main():
    product = Image.open(PRODUCT_PATH).convert("RGB")
    backgrounds = {k: Image.open(v).convert("RGB") for k, v in BG_PATHS.items()}
    candidates_dir = OUT / "candidates"
    previews_dir = OUT / "previews"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "canvas": {"width": CANVAS[0], "height": CANVAS[1], "format": "PNG", "aspect_ratio": "4:5"},
        "approved_copy": {"en": APPROVED_EN, "zh": APPROVED_ZH},
        "product_source": str(PRODUCT_PATH.relative_to(ROOT)),
        "product_policy": "Source photo placed without retouching, recoloring, warping, label edits, or overlays; only uniform scaling and placement used.",
        "logo_policy": "No logo asset was supplied. Each draft reserves a clear area; no placeholder logo was invented.",
        "candidates": [],
    }
    images = {}
    for code, direction, name, fn in SPECS:
        image, copy_box, product_box, logo_safe = fn(backgrounds[direction], product)
        path = candidates_dir / f"kv-{code.lower()}.png"
        image.convert("RGB").save(path, quality=95)
        preview = image.convert("RGB").resize((640, 800), Image.Resampling.LANCZOS)
        preview.save(previews_dir / f"kv-{code.lower()}-preview.jpg", quality=90, subsampling=0)
        images[code] = image.convert("RGB")
        metadata["candidates"].append({
            "code": code,
            "direction": direction,
            "internal_name": name,
            "artifact": str(path.relative_to(ROOT)),
            "preview": str((previews_dir / f"kv-{code.lower()}-preview.jpg").relative_to(ROOT)),
            "copy_box": list(copy_box),
            "product_box": [product_box[0], product_box[1], product_box[2], product_box[2]],
            "logo_safe_zone": list(logo_safe),
        })

    board = make_board(images)
    board.save(OUT / "kv-hypotheses-selection-board.png", quality=95)
    board.resize((1400, 1680), Image.Resampling.LANCZOS).save(
        previews_dir / "kv-hypotheses-selection-board-preview.jpg", quality=90, subsampling=0
    )
    with (OUT / "candidate-metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
