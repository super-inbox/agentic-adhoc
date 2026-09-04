from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "v1"
ASSETS = OUT / "assets"

BLANK_BOX = ASSETS / "b-layers-in-light-premium-gift-box-blank.png"
LOCKED_LOGO = ASSETS / "locked-current-logo-reference.png"
LOGO_DECAL = ASSETS / "locked-current-logo-decal.png"
COMPOSITE = OUT / "b-layers-in-light-premium-gift-box-logo-locked.png"
BOARD = OUT / "b-layers-in-light-v1-refinement-board.png"

FONT_MED = "/opt/X11/share/system_fonts/STHeiti Medium.ttc"
FONT_LIGHT = "/opt/X11/share/system_fonts/STHeiti Light.ttc"
FONT_LATIN = "/opt/X11/share/system_fonts/Supplemental/Arial Unicode.ttf"


def font(size, medium=False, latin=False):
    path = FONT_LATIN if latin else (FONT_MED if medium else FONT_LIGHT)
    return ImageFont.truetype(path, size=size)


def extract_logo_decal(logo_rgb):
    """Remove only the white source background; retain original colored logo pixels."""
    arr = np.asarray(logo_rgb.convert("RGB"), dtype=np.float32)
    distance_from_white = np.max(255.0 - arr, axis=2)
    alpha = np.clip((distance_from_white - 2.0) * (255.0 / 34.0), 0, 255).astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    return Image.fromarray(rgba, mode="RGBA")


def solve_output_to_input_coeffs(destination, source):
    """Solve Pillow perspective coefficients mapping output points to source points."""
    matrix = []
    vector = []
    for (x, y), (u, v) in zip(destination, source):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        vector.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        vector.append(v)
    return np.linalg.solve(np.asarray(matrix, dtype=np.float64), np.asarray(vector, dtype=np.float64))


def make_logo_locked_box():
    base = Image.open(BLANK_BOX).convert("RGBA")
    locked_logo = Image.open(LOCKED_LOGO).convert("RGB")
    decal = extract_logo_decal(locked_logo)
    decal.save(LOGO_DECAL)

    # Measured from the blank lid panel. The smaller quad keeps generous clear space.
    destination = [(855.2, 490.1), (1048.6, 521.8), (967.7, 648.8), (769.5, 613.3)]
    source = [(0, 0), (decal.width - 1, 0), (decal.width - 1, decal.height - 1), (0, decal.height - 1)]
    coeffs = solve_output_to_input_coeffs(destination, source)
    warped = decal.transform(
        base.size,
        Image.Transform.PERSPECTIVE,
        data=coeffs,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )

    polygon_mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(polygon_mask).polygon(destination, fill=255)
    alpha = ImageChops_multiply(warped.getchannel("A"), polygon_mask)
    warped.putalpha(alpha)

    composite = Image.alpha_composite(base, warped).convert("RGB")
    composite.save(COMPOSITE, quality=96)
    return composite, locked_logo


def ImageChops_multiply(a, b):
    # Import locally to keep the main dependency list explicit.
    from PIL import ImageChops

    return ImageChops.multiply(a, b)


def cover(image, size):
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def rounded_paste(base, image, box, radius=28):
    x, y, w, h = box
    fitted = cover(image, (w, h))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    base.paste(fitted, (x, y), mask)


def wrap_chars(draw, text, fnt, max_width):
    lines, current = [], ""
    for char in text:
        if char == "\n":
            lines.append(current.rstrip())
            current = ""
            continue
        candidate = current + char
        if current and draw.textlength(candidate, font=fnt) > max_width:
            lines.append(current.rstrip())
            current = char.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return "\n".join(lines)


def draw_wrapped(draw, xy, text, fnt, fill, max_width, spacing=9):
    wrapped = wrap_chars(draw, text, fnt, max_width)
    draw.multiline_text(xy, wrapped, font=fnt, fill=fill, spacing=spacing)
    return draw.multiline_textbbox(xy, wrapped, font=fnt, spacing=spacing)[3]


def build_board(composite, locked_logo):
    w, h = 2200, 1400
    # Preserve the four approved Territory B tokens from v0; only their area ratio changes.
    bg = "#F1D5A2"
    espresso = "#1D110C"
    muted = "#79624F"
    amber = "#A9531F"
    gold = "#E5A03C"
    paper = "#FFF9EF"
    canvas = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(canvas)

    f_kicker = font(22, medium=True, latin=True)
    f_title = font(72, medium=True)
    f_en = font(25, medium=True, latin=True)
    f_section = font(22, medium=True)
    f_body = font(27)
    f_small = font(23)
    f_num = font(19, medium=True, latin=True)

    draw.text((82, 64), "SELECTED TERRITORY B  /  DELTA REFINEMENT  /  v1", font=f_kicker, fill=muted)
    draw.rectangle((82, 108, 500, 114), fill=amber)
    draw.text((82, 148), "酥层见光", font=f_title, fill=espresso)
    draw.text((86, 240), "LAYERS IN LIGHT", font=f_en, fill=muted)

    card_x, card_y, card_w, card_h = 1740, 55, 380, 230
    draw.rounded_rectangle((card_x + 8, card_y + 8, card_x + card_w + 8, card_y + card_h + 8), radius=22, fill="#D7C7B3")
    draw.rounded_rectangle((card_x, card_y, card_x + card_w, card_y + card_h), radius=22, fill="#FFFFFF")
    logo_fit = ImageOps.contain(locked_logo, (335, 158), method=Image.Resampling.LANCZOS)
    canvas.paste(logo_fit, (card_x + (card_w - logo_fit.width) // 2, card_y + 14))
    draw.text((card_x + 20, card_y + 183), "Logo 锁定：同一源图", font=f_section, fill=espresso)
    draw.text((card_x + 20, card_y + 209), "不重绘／不改色／不拆分", font=font(16), fill=muted)

    rounded_paste(canvas, composite, (82, 320, 1320, 990), radius=34)
    draw.rounded_rectangle((108, 1224, 720, 1284), radius=16, fill=paper)
    draw.text((132, 1242), "留白约 60%＋单一礼盒＋单一产品证据", font=f_small, fill=muted)

    x, max_w = 1480, 640
    draw.text((x, 332), "本轮只改", font=f_section, fill=amber)
    changes = [
        ("01", "留白增加：暖石背景成为主面积，盒体退到画面下右。"),
        ("02", "价格感增加：硬盒比例、细纹裱纸、盲压边与极细金属线。"),
        ("03", "Logo 原样上盒：只做平面透视合成，不生成替代标识。"),
    ]
    y = 378
    for number, text in changes:
        draw.rounded_rectangle((x, y + 2, x + 42, y + 44), radius=10, fill=espresso)
        draw.text((x + 9, y + 11), number, font=f_num, fill=paper)
        y = draw_wrapped(draw, (x + 62, y), text, f_body, espresso, max_w - 62, spacing=8) + 22

    y += 10
    draw.text((x, y), "保持不变", font=f_section, fill=amber)
    y += 43
    unchanged = [
        "“层／脆／光”仍是 B 的识别核心。",
        "沿用深棕、酥金、烘烤橙、暖石四色。",
        "以产品工艺证据年轻化，不加网红道具。",
    ]
    for item in unchanged:
        draw.ellipse((x, y + 11, x + 8, y + 19), fill=gold)
        y = draw_wrapped(draw, (x + 24, y), item, f_body, espresso, max_w - 24, spacing=7) + 15

    y += 15
    draw.text((x, y), "礼盒高级感护栏", font=f_section, fill=amber)
    y += 43
    guardrail = "昂贵感来自克制比例与真实材质，不来自厚重金箔、复杂纹样、丝带或道具堆叠。当前为视觉概念，不代表已确认盒型、工艺或成本。"
    y = draw_wrapped(draw, (x, y), guardrail, f_body, espresso, max_w, spacing=9) + 28

    draw.line((x, y, x + max_w, y), fill="#C5A981", width=2)
    y += 22
    draw.text((x, y), "范围边界", font=f_section, fill=amber)
    draw_wrapped(draw, (x + 112, y - 3), "未制作淘宝主图或门店物料；中文标准字仍待准确源文件。", f_small, muted, max_w - 112, spacing=7)

    swatches = [("#1D110C", "深棕"), ("#A9531F", "烘烤橙"), ("#E5A03C", "酥金"), ("#F1D5A2", "暖石")]
    sy = 1250
    for idx, (color, label) in enumerate(swatches):
        sx = x + idx * 155
        draw.rounded_rectangle((sx, sy, sx + 128, sy + 42), radius=9, fill=color, outline="#9B816A", width=1)
        draw.text((sx, sy + 49), label, font=font(17), fill=muted)

    draw.text((1990, 1350), "v1  /  B", font=f_kicker, fill=muted)
    canvas.save(BOARD, quality=96)
    return canvas


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    composite, locked_logo = make_logo_locked_box()
    build_board(composite, locked_logo)
    print(COMPOSITE.relative_to(ROOT))
    print(BOARD.relative_to(ROOT))
    print(LOGO_DECAL.relative_to(ROOT))


if __name__ == "__main__":
    main()
