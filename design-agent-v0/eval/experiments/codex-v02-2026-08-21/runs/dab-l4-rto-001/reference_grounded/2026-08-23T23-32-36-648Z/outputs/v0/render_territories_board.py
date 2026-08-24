from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "creative-territories-board.png"
PRODUCT = ROOT / "product-reference-exact.png"

W, H = 2400, 1800
CREAM = "#F4EFE4"
PAPER = "#FBF8F1"
CLAY = "#B65343"
DEEP_CLAY = "#73382F"
CHARCOAL = "#292825"
OAT = "#D8C7AA"
OLIVE = "#7F8B60"
MUTED = "#6E675F"
RULE = "#CFC2AD"
WHITE = "#FFFDF8"

SANS_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
SERIF_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"


def sans(size, bold=False):
    return ImageFont.truetype(SANS_PATH, size=size, index=2 if bold else 0)


def serif(size, bold=False):
    return ImageFont.truetype(SERIF_PATH, size=size, index=1 if bold else 6)


im = Image.new("RGB", (W, H), CREAM)
d = ImageDraw.Draw(im)


def text(x, y, value, font, fill=CHARCOAL, anchor="la"):
    d.text((x, y), value, font=font, fill=fill, anchor=anchor)


def rule(x1, y1, x2, y2, fill=RULE, width=2):
    d.line((x1, y1, x2, y2), fill=fill, width=width)


def product_panel(box):
    x1, y1, x2, y2 = box
    d.rectangle(box, fill=WHITE)
    source = Image.open(PRODUCT).convert("RGB")
    # Crop only the original white surround; no product pixels are redrawn or recolored.
    source = source.crop((105, 220, 920, 825))
    fitted = ImageOps.contain(
        source, (x2 - x1, y2 - y1), method=Image.Resampling.LANCZOS
    )
    px = x1 + ((x2 - x1) - fitted.width) // 2
    py = y1 + ((y2 - y1) - fitted.height) // 2
    im.paste(fitted, (px, py))


# Header
d.rectangle((0, 0, 34, H), fill=CLAY)
text(90, 58, "DIRECTION CHECKPOINT · V0", sans(20), DEEP_CLAY)
text(90, 112, "陶土红香薰机", sans(57, True))
text(585, 113, "参考拆解与三个原创方向", serif(51))
text(2310, 63, "只取原则 / 不复制品牌、文字或具体图形", sans(20), MUTED, "ra")
rule(90, 184, 2310, 184)


def reference_card(x, label, title, lines, kind, discard):
    y, w, h = 220, 720, 365
    d.rectangle((x, y, x + w, y + h), fill=PAPER, outline="#D5C9B7", width=2)
    text(x + 35, y + 27, label, sans(20), CLAY)
    gx, gy, gw, gh = x + 35, y + 68, 235, 240
    d.rectangle((gx, gy, gx + gw, gy + gh), fill=CREAM, outline="#B8AA96", width=1)

    if kind == "layout":
        d.rectangle((gx + 28, gy + 22, gx + 207, gy + 114), fill=OAT)
        rule(gx + 28, gy + 136, gx + 207, gy + 136, CHARCOAL, 2)
        d.rectangle((gx + 28, gy + 156, gx + 80, gy + 208), fill=CLAY)
        d.rectangle((gx + 90, gy + 156, gx + 142, gy + 208), fill=OLIVE)
        d.rectangle((gx + 152, gy + 156, gx + 207, gy + 208), fill=CHARCOAL)
    elif kind == "palette":
        d.rectangle((gx, gy, gx + gw, gy + gh), fill=CHARCOAL)
        d.rectangle((gx + 20, gy + 20, gx + 215, gy + 150), fill=CREAM)
        d.rectangle((gx + 20, gy + 164, gx + 100, gy + 220), fill=CLAY)
        d.rectangle((gx + 110, gy + 164, gx + 160, gy + 220), fill=OAT)
        d.rectangle((gx + 170, gy + 164, gx + 215, gy + 220), fill=OLIVE)
    else:
        d.polygon(
            [(gx, gy + 152), (gx + 157, gy), (gx + 235, gy), (gx + 59, gy + 182)],
            fill=CLAY,
        )
        d.rectangle((gx + 75, gy + 126, gx + 235, gy + 198), fill=CHARCOAL)
        d.rectangle((gx, gy + 200, gx + 108, gy + 240), fill=OLIVE)

    tx = x + 308
    text(tx, y + 78, title, sans(31, True))
    for idx, line_value in enumerate(lines):
        text(tx, y + 131 + idx * 43, line_value, sans(24), MUTED)
    text(tx, y + 286, discard, sans(19), DEEP_CLAY)


reference_card(
    90,
    "REFERENCE 01 / 布局原则",
    "大留白 × 分段节奏",
    ["首屏最疏，卖点适中，参数最密", "产品 → 主张 → 卖点 → 材质", "细线建秩序，每段只回答一个问题"],
    "layout",
    "舍弃：品牌、原图、图标、具体比例",
)
reference_card(
    840,
    "REFERENCE 02 / 暖色系统",
    "70 / 20 / 8 / 2",
    ["奶油 / 陶土红 / 炭黑 / 橄榄", "暖而不闷，产品与背景保持分离", "强标题层级 + 安静说明层级"],
    "palette",
    "舍弃：品牌字标、叶形标志与原纹样",
)
reference_card(
    1590,
    "REFERENCE 03 / 构图原则",
    "错位 × 跨栏 × 尺度反差",
    ["每屏只留一个几何冲突点", "几何引导视线，不抢产品身份", "用裁切与跨栏制造“从静到动”"],
    "geometry",
    "舍弃：圆弧网格、原配色与具体图案",
)


def route_shell(x, bg, code, title_cn, title_en):
    y, w, h = 625, 720, 1030
    d.rectangle((x, y, x + w, y + h), fill=bg, outline="#CCBEA9", width=2)
    text(x + 40, y + 31, f"TERRITORY {code}", sans(20), CLAY)
    text(x + 40, y + 76, title_cn, sans(41, True))
    text(x + 680, y + 81, title_en, serif(27), MUTED, "ra")


route_shell(90, PAPER, "A", "余温留白", "Residual Warmth")
route_shell(840, "#F6ECE3", "B", "陶土切面", "Clay Facets")
route_shell(1590, "#EEE7D9", "C", "静音时序", "Quiet Sequence")

# A preview
ax1, ay1, ax2, ay2 = 130, 745, 770, 1165
d.rectangle((ax1, ay1, ax2, ay2), fill=CREAM)
d.rectangle((ax1, ay1, ax1 + 12, ay2), fill=CLAY)
rule(180, 815, 720, 815, DEEP_CLAY, 2)
text(180, 778, "让香气", sans(25))
text(180, 835, "慢下来", serif(78))
text(183, 918, "陶土红香薰机", sans(20), MUTED)
product_panel((310, 930, 745, 1155))

text(130, 1201, "安静、生活方式、留白最充分", sans(30, True))
text(130, 1246, "低成本机制：排版、原图裁切、单一细线。", sans(24), MUTED)
items_a = [
    ("H01", "首屏至少 45% 负空间"),
    ("H02", "产品居中偏下，宽约 32%"),
    ("H03", "暖色面积比 70 / 20 / 8 / 2"),
    ("H04", "大标题 + 短句 + 细线足够"),
]
for i, (num, value) in enumerate(items_a):
    yy = 1318 + i * 58
    d.ellipse((132, yy - 13, 158, yy + 13), fill=CREAM, outline=CLAY, width=3)
    text(175, yy - 20, num, sans(26, True))
    text(245, yy - 20, value, sans(26))
rule(130, 1552, 770, 1552)
text(130, 1578, "首选目标：情绪 / 高级感 / 安静", sans(20), DEEP_CLAY)

# B preview
bx1, by1, bx2, by2 = 880, 745, 1520, 1165
d.rectangle((bx1, by1, bx2, by2), fill=CLAY)
d.polygon([(880, 745), (1260, 745), (1080, 1165), (880, 1165)], fill=CREAM)
d.polygon([(1285, 745), (1520, 745), (1520, 955), (1400, 1015)], fill=DEEP_CLAY)
text(905, 885, "慢", serif(180), CHARCOAL)
text(925, 1058, "让香气慢下来", sans(21), CHARCOAL)
product_panel((1115, 865, 1510, 1155))

text(880, 1201, "发布感最强，几何张力最明显", sans(30, True))
text(880, 1246, "低成本机制：斜切色面、文字裁切、真实近景。", sans(24), MUTED)
items_b = [
    (CLAY, "H05", "单一斜切面穿过产品背景"),
    (DEEP_CLAY, "H06", "“慢下来”大尺度裁切即构图"),
    (OAT, "H07", "产品原图局部表达陶土触感"),
]
for i, (color, num, value) in enumerate(items_b):
    yy = 1318 + i * 58
    d.rectangle((880, yy - 13, 906, yy + 13), fill=color)
    text(925, yy - 20, num, sans(26, True))
    text(995, yy - 20, value, sans(26))
text(880, 1480, "边界：一屏一个斜切焦点，产品始终保持正视。", sans(23), MUTED)
rule(880, 1552, 1520, 1552)
text(880, 1578, "首选目标：新品冲击 / 传播 / 记忆点", sans(20), DEEP_CLAY)

# C preview
cx1, cy1, cx2, cy2 = 1630, 745, 2270, 1165
d.rectangle((cx1, cy1, cx2, cy2), fill=CREAM)
for i, (color, num, label) in enumerate(
    [(CHARCOAL, "01", "低噪运行"), (OLIVE, "02", "定时关闭"), (CLAY, "03", "陶土触感")]
):
    y1 = 745 + i * 140
    d.rectangle((1630, y1, 1794, y1 + 140), fill=color)
    text(1660, y1 + 25, num, sans(44), WHITE)
    text(1660, y1 + 84, label, sans(20), WHITE)
rule(1818, 785, 2242, 785, "#B8AA96", 2)
rule(1818, 815, 2110, 815, CLAY, 4)
rule(1818, 833, 2070, 833, CLAY, 2)
text(1830, 858, "让香气慢下来", serif(50))
product_panel((1840, 905, 2255, 1155))

text(1630, 1201, "功能最清晰，适合快速扫读", sans(30, True))
text(1630, 1246, "低成本机制：序号、线段、矩形与统一网格。", sans(24), MUTED)
items_c = [
    (CHARCOAL, "H08", "01/02/03 替代通用图标"),
    (OLIVE, "H09", "低振幅线 + 时间阶梯块"),
    (CLAY, "H10", "统一 12 栏网格，改变跨栏"),
]
for i, (color, num, value) in enumerate(items_c):
    yy = 1318 + i * 58
    rule(1630, yy, 1662, yy, color, 8)
    text(1685, yy - 20, num, sans(26, True))
    text(1755, yy - 20, value, sans(26))
text(1630, 1480, "边界：保留足够留白，避免变成纯参数页。", sans(23), MUTED)
rule(1630, 1552, 2270, 1552)
text(1630, 1578, "首选目标：功能扫读 / 电商效率 / 复用", sans(20), DEEP_CLAY)

# Footer
rule(90, 1704, 2310, 1704)
text(90, 1729, "下一步：", sans(27, True))
text(205, 1729, "请选择 A / B / C 一个主方向；选定后再制作 1 张首屏 + 2 张卖点模块。", sans(27))
text(2310, 1735, "PRODUCT SOURCE PRESERVED EXACTLY · SHA-256 241716AA…", sans(19), MUTED, "ra")

im.save(OUT, optimize=True)
print(OUT)
