from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "creative-territories-board.png"
PRODUCT = ROOT / "product-reference-exact.png"

W, H = 1800, 1200
PAPER = "#F7F3E9"
WARM = "#F3EEDF"
CANVAS = "#E8E1D4"
INK = "#2E2F2C"
MUTED = "#74766F"
RULE = "#C8C2B6"
CLAY = "#B85B49"
SAGE = "#8B9872"
BLUE = "#B8D1D6"
SAND = "#DED2BC"

CN_MED = "/System/Library/Fonts/STHeiti Medium.ttc"
CN_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"
LATIN = "/System/Library/Fonts/Supplemental/Arial.ttf"


def font(path, size):
    return ImageFont.truetype(path, size=size)


F = {
    "board": font(CN_MED, 34),
    "sub": font(CN_LIGHT, 17),
    "index": font(LATIN, 16),
    "territory": font(CN_MED, 30),
    "en": font(LATIN, 15),
    "hero": font(CN_MED, 38),
    "hero_small": font(CN_MED, 24),
    "micro": font(CN_MED, 13),
    "meta": font(CN_LIGHT, 16),
    "hyp": font(CN_LIGHT, 16),
    "risk": font(CN_LIGHT, 14),
}


def tx(draw, xy, text, kind, fill=INK, anchor=None):
    draw.text(xy, text, font=F[kind], fill=fill, anchor=anchor)


def product_cutout():
    src = Image.open(PRODUCT).convert("RGBA")
    # Crop and scale only; silhouette, color, lid, seam and button stay untouched.
    crop = src.crop((155, 248, 869, 823))
    px = crop.load()
    for yy in range(crop.height):
        for xx in range(crop.width):
            r, g, b, a = px[xx, yy]
            whiteness = min(r, g, b)
            if whiteness >= 250:
                px[xx, yy] = (r, g, b, 0)
            elif whiteness > 238:
                px[xx, yy] = (r, g, b, int((250 - whiteness) / 12 * a))
    return crop


def paste_product(base, cutout, box):
    x, y, w, h = box
    scaled = cutout.copy()
    scaled.thumbnail((w, h), Image.Resampling.LANCZOS)
    px = x + (w - scaled.width) // 2
    py = y + (h - scaled.height) // 2
    base.alpha_composite(scaled, (px, py))


def panel_header(draw, x, index, cn, en):
    tx(draw, (x, 190), index, "index", MUTED)
    tx(draw, (x, 224), cn, "territory")
    cn_w = draw.textlength(cn, font=F["territory"])
    tx(draw, (x + cn_w + 24, 224), en, "en", MUTED)


def swatches(draw, x, colors):
    for i, color in enumerate(colors):
        draw.rectangle((x + i * 64, 1044, x + i * 64 + 56, 1062), fill=color, outline=RULE if i == 0 else None)


img = Image.new("RGBA", (W, H), CANVAS)
draw = ImageDraw.Draw(img)
draw.rectangle((24, 24, 1776, 1176), fill=PAPER)

tx(draw, (64, 80), "陶土红香薰机 · CREATIVE TERRITORIES", "board")
tx(draw, (64, 116), "原则提炼 / 10 个低成本假设 / 等待方向选择", "sub", "#62645E")
tx(draw, (1736, 80), "V0 · 2026", "index", MUTED, "ra")
draw.line((64, 145, 1736, 145), fill=RULE, width=1)

cutout = product_cutout()

# A — Slow Arc Field
x = 72
panel_header(draw, x, "A / 01", "慢弧场", "SLOW ARC FIELD")
draw.rectangle((x, 250, x + 512, 740), fill=WARM, outline="#D3CCBF")
draw.arc((-48, 286, 700, 1000), start=191, end=344, fill=CLAY, width=38)
draw.arc((-16, 322, 660, 954), start=191, end=345, fill=PAPER, width=30)
draw.arc((24, 357, 620, 910), start=190, end=345, fill=SAGE, width=3)
tx(draw, (105, 294), "AROMA / 01", "micro")
tx(draw, (105, 342), "让香气", "hero")
tx(draw, (105, 392), "慢下来", "hero")
for cx, cy, r, alpha in [(178, 492, 4, 220), (204, 478, 3, 170), (226, 458, 3, 120), (242, 434, 2, 90), (254, 408, 2, 65)]:
    rgba = (184, 91, 73, alpha)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=rgba)
paste_product(img, cutout, (290, 430, 282, 250))
draw.line((105, 693, 271, 693), fill=INK, width=2)
tx(draw, (105, 716), "弧线接续下一模块", "micro")
# Clip the bold arc back to its own preview so the three territories remain comparable.
draw.rectangle((0, 250, 23, 740), fill=CANVAS)
draw.rectangle((24, 250, 71, 740), fill=PAPER)
draw.rectangle((585, 250, 643, 740), fill=PAPER)
draw.rectangle((72, 250, 584, 740), outline="#D3CCBF")
tx(draw, (x, 782), "情绪最强 · 产品落在偏心弧线切点", "meta", "#52544F")
draw.line((x, 808, x + 512, 808), fill=RULE)
for yy, text in zip((845, 878, 911, 944), ("H01  切边慢弧", "H02  55–65% 安静空场", "H03  弧线跨模块接力", "H04  稀疏陶土颗粒")):
    tx(draw, (x, yy), text, "hyp")
tx(draw, (x, 1002), "风险：弧线过整会趋近常见 wellness 视觉", "risk", MUTED)
swatches(draw, x, (WARM, CLAY, SAGE, INK))
tx(draw, (x, 1100), "低成本：原图 + 1 条主路径 + 静态颗粒", "micro")

# B — Clay Strata Editorial
x = 644
panel_header(draw, x, "B / 02", "陶层编辑", "CLAY STRATA EDITORIAL")
draw.rectangle((x, 250, x + 512, 740), fill=PAPER, outline="#D3CCBF")
draw.rectangle((610, 312, 1022, 416), fill=CLAY)
draw.rounded_rectangle((718, 436, 1188, 522), radius=43, fill=SAND)
draw.rectangle((616, 552, 1040, 664), fill=SAGE)
for gy in range(565, 655, 24):
    for gx in range(630 + ((gy // 24) % 2) * 11, 1032, 28):
        draw.ellipse((gx, gy, gx + 3, gy + 3), fill=(46, 47, 44, 55))
tx(draw, (668, 289), "MATERIAL / 02", "micro")
tx(draw, (668, 380), "陶土触感", "hero_small", PAPER)
tx(draw, (670, 483), "01  低噪运行", "micro")
tx(draw, (1016, 602), "02  定时关闭", "micro", PAPER, "ra")
paste_product(img, cutout, (790, 352, 310, 300))
draw.line((666, 692, 1131, 692), fill=INK, width=2)
tx(draw, (666, 716), "原图局部可直接承担材质证据", "micro")
draw.rectangle((585, 250, 643, 740), fill=PAPER)
draw.rectangle((1157, 250, 1215, 740), fill=PAPER)
draw.rectangle((644, 250, 1156, 740), outline="#D3CCBF")
tx(draw, (x, 782), "材料最强 · 错位横带组织商品信息", "meta", "#52544F")
draw.line((x, 808, x + 512, 808), fill=RULE)
for yy, text in zip((845, 878, 911), ("H05  三条错位陶层", "H06  原图微距裁片", "H07  大字、编号、细线替代图标")):
    tx(draw, (x, yy), text, "hyp")
tx(draw, (x, 1002), "风险：层数过多会变成目录式信息页", "risk", MUTED)
swatches(draw, x, (WARM, CLAY, SAND, SAGE))
tx(draw, (x, 1100), "低成本：色块 + 排版 + 原图等比裁切", "micro")

# C — Quiet Time Track
x = 1216
panel_header(draw, x, "C / 03", "静时轨", "QUIET TIME TRACK")
draw.rectangle((x, 250, x + 512, 740), fill=WARM, outline="#D3CCBF")
draw.rectangle((x, 250, x + 512, 332), fill=BLUE)
tx(draw, (1246, 294), "QUIET / TIMER / 03", "micro")
wave = [(1244, 377), (1272, 354), (1300, 400), (1328, 377), (1356, 354), (1384, 400), (1412, 377), (1433, 360), (1452, 385), (1470, 381), (1511, 377), (1584, 377)]
draw.line(wave, fill=CLAY, width=4, joint="curve")
track = [(1204, 548), (1270, 510), (1346, 498), (1412, 541), (1456, 541), (1510, 536), (1587, 455), (1660, 450), (1738, 445)]
draw.line(track, fill=INK, width=3, joint="curve")
draw.arc((1507, 337, 1721, 551), start=47, end=318, fill=SAGE, width=22)
draw.ellipse((1596, 426, 1632, 462), fill=CLAY)
draw.ellipse((1606, 436, 1622, 452), fill=WARM)
paste_product(img, cutout, (1230, 394, 300, 285))
tx(draw, (1538, 586), "低噪运行", "hero_small")
tx(draw, (1538, 625), "定时关闭", "hero_small")
tx(draw, (1538, 662), "波动 → 归零 → 停止点", "micro")
draw.line((1538, 684, 1700, 684), fill=INK, width=2)
draw.rectangle((1157, 250, 1215, 740), fill=PAPER)
draw.rectangle((1729, 250, 1776, 740), fill=PAPER)
draw.rectangle((1216, 250, 1728, 740), outline="#D3CCBF")
tx(draw, (x, 782), "功能最强 · 从波动走向停止的轨迹", "meta", "#52544F")
draw.line((x, 808, x + 512, 808), fill=RULE)
for yy, text in zip((845, 878, 911), ("H08  静音波形归零", "H09  未闭合计时轨迹 + 停止点", "H10  暖场为主，冷色只落边缘")):
    tx(draw, (x, yy), text, "hyp")
tx(draw, (x, 1002), "风险：轨迹过强会让“定时”压过材质卖点", "risk", MUTED)
swatches(draw, x, (WARM, CLAY, SAGE, BLUE))
tx(draw, (x, 1100), "低成本：2 条线 + 1 个端点 + 固定色票", "micro")

draw.line((616, 174, 616, 1122), fill=RULE)
draw.line((1188, 174, 1188, 1122), fill=RULE)
tx(draw, (1736, 1140), "SELECT A / B / C", "index", MUTED, "ra")

img.convert("RGB").save(OUT, quality=95)
print(OUT)
