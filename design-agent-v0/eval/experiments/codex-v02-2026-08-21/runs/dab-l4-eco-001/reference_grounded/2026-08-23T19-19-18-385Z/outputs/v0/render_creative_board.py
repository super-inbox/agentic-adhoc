from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v0" / "creative-territories-board.png"
PRODUCT = ROOT / "inputs" / "01-product_master.png"

W, H = 1600, 2200
BG = "#f7f6f0"
CHARCOAL = "#30312f"
MUTED = "#6d716c"
WHITE = "#ffffff"

FONT_MEDIUM = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"


def font(size, medium=False):
    return ImageFont.truetype(FONT_MEDIUM if medium else FONT_LIGHT, size)


F_LABEL = font(20, True)
F_SMALL = font(21)
F_BODY = font(24)
F_CARD = font(25, True)
F_TITLE = font(51, True)
F_TERRITORY = font(37, True)


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def fit_lines(draw, text, fnt, max_width):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        if current and draw.textlength(test, font=fnt) > max_width:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def text_block(draw, xy, text, fnt, fill, max_width, line_gap=8, max_lines=None):
    x, y = xy
    lines = fit_lines(draw, text, fnt, max_width)
    if max_lines:
        lines = lines[:max_lines]
    bbox = fnt.getbbox("国A")
    line_h = bbox[3] - bbox[1]
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h + line_gap
    return y


def shadow_card(base, box, radius=28):
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x0, y0 + 10, x1, y1 + 10), radius=radius, fill=(29, 36, 31, 28))
    layer = layer.filter(ImageFilter.GaussianBlur(16))
    base.alpha_composite(layer)


territories = [
    {
        "x": 80,
        "bg": "#eef3f2",
        "stroke": "#c9d9d6",
        "accent": "#93bec2",
        "code": "TERRITORY A",
        "name": "城市轻行",
        "en": "CITY LOOP",
        "claim": "一体式挂环",
        "concept": "从玄关到街角，用包带与路径线表达轻便出发。",
        "grammar": "视觉：高明度自然光 / 斜向动势 / 产品大轮廓",
        "scenes": [
            ("1", "玄关帆布包", "长凳＋墙钩＋帆布包，形成“即将出门”线索。", "挂包连接须等官方挂环视角，绝不虚构结构。"),
            ("2", "街角咖啡外摆", "桌角＋包带斜线＋浅景深城市背景。", "产品前景完整，缩略图识别最直接。"),
            ("3", "单车短暂停靠", "车篮与包提示移动，不表现骑行中操作。", "不添加固定支架或未提供配件。"),
            ("4", "城市公园长椅", "包＋书＋浅绿背景，无模特也能成立。", "产品占画面约一半，保持主体清楚。"),
        ],
        "best": "天猫主图 · 挂环卖点图 · 社媒海报",
        "adv": "优势：电商信息最直给",
        "risk": "风险：需要补充准确挂环视角",
        "best_bg": "#dfeae8",
    },
    {
        "x": 570,
        "bg": "#edf5f7",
        "stroke": "#c5dce3",
        "accent": "#b5d4df",
        "code": "TERRITORY B",
        "name": "轻水留白",
        "en": "FRESH SPLASH",
        "claim": "IPX4 防泼水",
        "concept": "用水珠与雨后反光，克制表现日常泼溅中的从容。",
        "grammar": "视觉：浅蓝冷光 / 水珠微距 / 橄榄绿植物",
        "scenes": [
            ("5", "雨后公园桌", "桌面薄反光，背景叶片带水珠。", "产品处于稳定区域；不制造积水包围。"),
            ("6", "露台浇花", "浇水壶虚化，少量飞溅停留在叶片/空气。", "产品不置于直流水柱或暴雨下。"),
            ("7", "野餐冷饮凝露", "杯壁凝露＋水果＋桌布边缘少量水点。", "只作场景道具，不暗示随箱附赠。"),
        ],
        "best": "防泼水卖点图 · 详情首屏 · 社媒海报",
        "adv": "优势：视觉记忆最强",
        "risk": "风险：必须避免“可浸泡”误读",
        "best_bg": "#dcecf1",
    },
    {
        "x": 1060,
        "bg": "#f3f0e7",
        "stroke": "#ddd5c3",
        "accent": "#8f9b6c",
        "code": "TERRITORY C",
        "name": "晨昏慢陪",
        "en": "DAYLONG CALM",
        "claim": "12 小时续航",
        "concept": "同一桌面从晨光到夜色，用时间层次讲清 12 小时续航。",
        "grammar": "视觉：奶油白 / 橄榄绿 / 陶土红 / 三段光色",
        "scenes": [
            ("8", "晨间早餐台", "杯碟＋一枝绿叶，柔和晨光。", "产品占画面 45% 以上，缩略图清楚。"),
            ("9", "午后阅读角", "同一机位换书与织物，光线转中性。", "不出现音质、连接距离等未批准参数。"),
            ("10", "黄昏阳台桌", "陶土红夕照＋小型暖灯，收束晨至暮。", "不写“全天/整日”，只写 12 小时。"),
        ],
        "best": "续航卖点图 · 详情首屏 · 品牌社媒",
        "adv": "优势：MORI 品牌气质最完整",
        "risk": "风险：便携动作弱，需放大产品",
        "best_bg": "#e9e4d5",
    },
]


canvas = Image.new("RGBA", (W, H), BG)
draw = ImageDraw.Draw(canvas)
draw.rectangle((0, 0, W, 18), fill=CHARCOAL)

draw.text((80, 58), "MORI · CREATIVE TERRITORIES / V0", font=F_LABEL, fill=CHARCOAL)
draw.text((80, 119), "便携音箱创意方向选择板", font=F_TITLE, fill=CHARCOAL)
draw.text((80, 198), "10 个低成本场景假设 · 3 个差异化方向 · 本轮仅供选择，不生成六张成品", font=F_BODY, fill=MUTED)

rr(draw, (80, 278, 1090, 400), 22, "#eeeadf")
draw.text((112, 304), "LOCKED / 不可改变", font=F_LABEL, fill=CHARCOAL)
draw.text((112, 340), "产品外观、接口、Logo、蓝绿色保持原样；只使用 12 小时续航 / IPX4 防泼水 / 一体式挂环。", font=F_SMALL, fill=CHARCOAL)
draw.text((112, 372), "不增加虚构按钮或配件；不出现浸泡、强水柱或“防水”表述。", font=F_SMALL, fill=MUTED)

shadow_card(canvas, (1180, 60, 1530, 410), 34)
draw = ImageDraw.Draw(canvas)
rr(draw, (1180, 60, 1530, 410), 34, WHITE)
product = Image.open(PRODUCT).convert("RGB").resize((330, 330), Image.Resampling.LANCZOS)
canvas.paste(product, (1190, 70))
draw.text((1180, 430), "原产品图仅缩放 / 未改色、未改结构", font=F_SMALL, fill=MUTED)

for t in territories:
    x = t["x"]
    y = 468
    rr(draw, (x, y, x + 460, y + 1250), 28, t["bg"], t["stroke"], 2)
    rr(draw, (x, y, x + 460, y + 15), 8, t["accent"])
    draw.text((x + 30, y + 42), t["code"], font=F_LABEL, fill=CHARCOAL)
    draw.text((x + 30, y + 89), t["name"], font=F_TERRITORY, fill=CHARCOAL)
    draw.text((x + 30, y + 142), t["en"], font=F_SMALL, fill=MUTED)
    claim_w = int(draw.textlength(t["claim"], font=F_SMALL) + 46)
    rr(draw, (x + 30, y + 194, x + 30 + claim_w, y + 234), 20, CHARCOAL)
    draw.text((x + 53, y + 201), t["claim"], font=F_SMALL, fill=WHITE)
    text_block(draw, (x + 30, y + 266), t["concept"], F_BODY, CHARCOAL, 400, line_gap=8, max_lines=2)
    draw.text((x + 30, y + 365), t["grammar"], font=font(19), fill=MUTED)

    scene_y = y + 410
    available = 605
    gap = 16
    card_h = int((available - gap * (len(t["scenes"]) - 1)) / len(t["scenes"]))
    for n, title, line1, line2 in t["scenes"]:
        rr(draw, (x + 30, scene_y, x + 430, scene_y + card_h), 18, WHITE)
        draw.ellipse((x + 48, scene_y + 18, x + 86, scene_y + 56), fill=t["accent"])
        num_w = draw.textlength(n, font=font(18, True))
        draw.text((x + 67 - num_w / 2, scene_y + 26), n, font=font(18, True), fill=WHITE if t["code"] != "TERRITORY B" else CHARCOAL)
        draw.text((x + 98, scene_y + 22), title, font=F_CARD, fill=CHARCOAL)
        text_block(draw, (x + 50, scene_y + 67), line1, font(19), MUTED, 360, line_gap=5, max_lines=2)
        text_block(draw, (x + 50, scene_y + card_h - 38), line2, font(18), MUTED, 360, line_gap=4, max_lines=1)
        scene_y += card_h + gap

    rr(draw, (x + 30, y + 1045, x + 430, y + 1210), 18, t["best_bg"])
    draw.text((x + 52, y + 1068), "BEST AT", font=F_LABEL, fill=CHARCOAL)
    draw.text((x + 52, y + 1106), t["best"], font=font(19), fill=CHARCOAL)
    draw.text((x + 52, y + 1147), t["adv"], font=font(19), fill=MUTED)
    draw.text((x + 52, y + 1180), t["risk"], font=font(19), fill=MUTED)

rr(draw, (80, 1780, 1520, 2080), 28, CHARCOAL)
draw.text((120, 1818), "SELECTION CHECKPOINT / 请选择一个方向", font=F_LABEL, fill="#f7f6f0")
draw.text((120, 1882), "A 城市轻行　　B 轻水留白　　C 晨昏慢陪", font=F_TERRITORY, fill=WHITE)
draw.text((120, 1944), "选择后再制作：天猫主图 ×1 / 卖点图 ×3 / 详情页首屏 ×1 / 社媒场景海报 ×1", font=F_BODY, fill="#e7e5dc")
draw.text((120, 1994), "要真实表现“挂包”，需官方侧/背面图、透明底图或 CAD，清楚展示一体式挂环与连接方式。", font=F_SMALL, fill="#bfc4bd")
draw.text((120, 2032), "当前状态：AWAITING CLIENT DECISION · 六张最终视觉资产尚未授权制作", font=F_SMALL, fill="#bfc4bd")

draw.text((80, 2140), "Palette visually approximated from supplied MORI brand-board PNG. Final production values require source brand specifications.", font=font(18), fill=MUTED)

OUT.parent.mkdir(parents=True, exist_ok=True)
canvas.convert("RGB").save(OUT, quality=95)
print(OUT)

