from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs" / "v0"
ASSETS = OUT / "assets"

W, H = 2200, 1400

FONT_MED = "/opt/X11/share/system_fonts/STHeiti Medium.ttc"
FONT_LIGHT = "/opt/X11/share/system_fonts/STHeiti Light.ttc"
FONT_LATIN = "/opt/X11/share/system_fonts/Supplemental/Arial Unicode.ttf"


def font(size, medium=False, latin=False):
    path = FONT_LATIN if latin else (FONT_MED if medium else FONT_LIGHT)
    return ImageFont.truetype(path, size=size)


F_KICKER = font(22, medium=True, latin=True)
F_TITLE = font(76, medium=True)
F_EN = font(25, medium=True, latin=True)
F_STANCE = font(35, medium=False)
F_LABEL = font(22, medium=True)
F_BODY = font(27, medium=False)
F_BODY_SMALL = font(24, medium=False)
F_NUM = font(20, medium=True, latin=True)
F_SWATCH = font(18, medium=True, latin=True)
F_OV_TITLE = font(58, medium=True)
F_OV_HEAD = font(38, medium=True)
F_OV_BODY = font(25)
F_OV_SMALL = font(22)


def wrap_chars(draw, text, fnt, max_width):
    lines = []
    current = ""
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
    if current or not lines:
        lines.append(current.rstrip())
    return "\n".join(lines)


def draw_wrapped(draw, xy, text, fnt, fill, max_width, spacing=10):
    wrapped = wrap_chars(draw, text, fnt, max_width)
    draw.multiline_text(xy, wrapped, font=fnt, fill=fill, spacing=spacing)
    box = draw.multiline_textbbox(xy, wrapped, font=fnt, spacing=spacing)
    return box[3]


def cover(image, size):
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def rounded_paste(base, image, box, radius=24):
    x, y, w, h = box
    fitted = cover(image, (w, h))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    base.paste(fitted, (x, y), mask)


def save_locked_logo_crop():
    source = Image.open(ROOT / "inputs" / "01-current_logo_and_identity.png").convert("RGB")
    # Exact rectangular crop from the visible AFTER lockup; no repainting or generative editing.
    crop = source.crop((760, 198, 1265, 565))
    path = ASSETS / "locked-current-logo-reference.png"
    crop.save(path, quality=100)
    return crop, path


def draw_logo_card(canvas, logo_crop, theme):
    draw = ImageDraw.Draw(canvas)
    x, y, w, h = 1740, 64, 370, 230
    shadow = (0, 0, 0, 25)
    # Pillow RGB does not support alpha fills; use a restrained solid offset shadow.
    draw.rounded_rectangle((x + 8, y + 8, x + w + 8, y + h + 8), radius=22, fill=theme["shadow"])
    draw.rounded_rectangle((x, y, x + w, y + h), radius=22, fill="#FFFFFF")
    fitted = ImageOps.contain(logo_crop, (330, 150), method=Image.Resampling.LANCZOS)
    px = x + (w - fitted.width) // 2
    py = y + 18
    canvas.paste(fitted, (px, py))
    draw.text((x + 20, y + 181), "现有 Logo 原样锁定", font=F_LABEL, fill="#35251B")
    draw.text((x + 20, y + 208), "中文标准字待准确源文件", font=font(16), fill="#725D4E")


def draw_palette(draw, colors, labels, x, y, text_fill):
    for idx, (color, label) in enumerate(zip(colors, labels)):
        sx = x + idx * 147
        draw.rounded_rectangle(
            (sx, y, sx + 126, y + 44),
            radius=10,
            fill=color,
            outline="#8B8177",
            width=1,
        )
        draw.text((sx, y + 52), label, font=F_SWATCH, fill=text_fill)


def draw_hypothesis(draw, number, text, x, y, width, theme):
    draw.rounded_rectangle((x, y + 2, x + 42, y + 44), radius=10, fill=theme["accent"])
    draw.text((x + 9, y + 10), f"{number:02d}", font=F_NUM, fill=theme["num_text"])
    end_y = draw_wrapped(draw, (x + 62, y), text, F_BODY, theme["text"], width - 62, spacing=8)
    return max(y + 56, end_y + 16)


THEMES = {
    "t1": {
        "bg": "#F2EEE5",
        "text": "#2C211C",
        "muted": "#6B5A50",
        "accent": "#8B1720",
        "num_text": "#FFFFFF",
        "rule": "#BCA46F",
        "panel": "#E9E2D6",
        "shadow": "#D8CFC2",
    },
    "t2": {
        "bg": "#1D110C",
        "text": "#F6E9D4",
        "muted": "#C9A77A",
        "accent": "#D78328",
        "num_text": "#24140D",
        "rule": "#7E4E29",
        "panel": "#2A1912",
        "shadow": "#0E0805",
    },
    "t3": {
        "bg": "#132139",
        "text": "#F3F0E8",
        "muted": "#B6BDB2",
        "accent": "#A86A48",
        "num_text": "#FFFFFF",
        "rule": "#859189",
        "panel": "#1C2D48",
        "shadow": "#0A1322",
    },
}


TERRITORIES = [
    {
        "id": "01",
        "slug": "new-chinese-ritual",
        "title": "新中礼序",
        "en": "NEW CHINESE RITUAL",
        "theme": "t1",
        "image": ASSETS / "territory-01-new-chinese-ritual-key-visual.png",
        "stance": "把“礼赠感”从复古纹样转成秩序、留白与开启动作。",
        "hypotheses": [
            "大留白＋轴线秩序，比贴纸拼贴更像“成熟的年轻”。",
            "朱砂只做结构色，保留礼赠信号而不落入满版喜庆。",
            "折叠、套框、开合可用纸材低成本形成可复制系统。",
            "中文品牌名承担信息主层级；现有 Logo 与标准字保持原样。",
        ],
        "palette": ["#F2EEE5", "#8B1720", "#2C211C", "#C2A05F"],
        "palette_labels": ["象牙", "朱砂", "炭棕", "香槟金"],
        "ecom": "若入选：产品居中，朱砂框定义卖点；SKU 只换结构色块，Logo 固定在白色身份区。",
        "store": "若入选：橱窗用层叠框景，礼盒墙用模块栅格，价签沿同一轴线。",
        "tradeoff": "最强礼赠秩序；食欲感较弱，红金比例失控会偏老气。",
        "cost": "低成本验证：现有白底产品图＋纸样即可，不新增完整拍摄。",
    },
    {
        "id": "02",
        "slug": "layers-in-light",
        "title": "酥层见光",
        "en": "LAYERS IN LIGHT",
        "theme": "t2",
        "image": ASSETS / "territory-02-layers-in-light-key-visual.png",
        "stance": "不靠年轻化装饰，直接让招牌酥点的“层、脆、光”成为品牌资产。",
        "hypotheses": [
            "22–30 岁对可见的工艺证据，比“年轻标签”更有信任。",
            "微距层理能在不改 Logo 的前提下建立强记忆点。",
            "一束暖光可呼应现有日轮感，但不拆解或重绘 Logo。",
            "深棕压住甜腻，金黄负责食欲，仍保有礼赠质感。",
        ],
        "palette": ["#1D110C", "#A9531F", "#E5A03C", "#F1D5A2"],
        "palette_labels": ["深棕", "烘烤橙", "酥金", "暖石"],
        "ecom": "若入选：微距层理做内容背景，完整产品／礼盒保持清晰；卖点只写可核实的工艺事实。",
        "store": "若入选：背光酥层大图作远距识别，货架用窄幅暖光与深棕底统一陈列。",
        "tradeoff": "最强食欲与跨年龄；拍摄质量决定成败，控制不好会像普通烘焙广告。",
        "cost": "低成本验证：先拍 1 款招牌酥点的单灯微距，验证点击与停留。",
    },
    {
        "id": "03",
        "slug": "1998-pastry-archive",
        "title": "1998 酥点档案",
        "en": "THE 1998 PASTRY ARCHIVE",
        "theme": "t3",
        "image": ASSETS / "territory-03-1998-archive-key-visual.png",
        "stance": "把 1998 变成可信的时间坐标，用档案秩序连接“老品牌”与“新收藏”。",
        "hypotheses": [
            "“1998”作为事实锚点，比复古口号更年轻也更可信。",
            "索引、编号与留档可让礼赠系列产生收藏感。",
            "墨蓝／豆青／氧化铜能主动离开红金与小红书浅米色。",
            "盲压、纸纤维、装订边让历史可触摸，而不是做旧。",
        ],
        "palette": ["#132139", "#AAB3A2", "#F3F0E8", "#A86A48"],
        "palette_labels": ["墨蓝", "豆青", "纸白", "氧化铜"],
        "ecom": "若入选：以档案卡组织产品事实，“1998”作时间锚；Logo 固定在白色身份区。",
        "store": "若入选：索引式货架标签＋“1998”起点墙；其余年代内容只在事实核实后上墙。",
        "tradeoff": "最强差异与体系感；即时食欲最弱，品牌史资料不足时容易显得“伪档案”。",
        "cost": "低成本验证：空白档案卡＋现有产品图即可；只使用已核实事实。",
    },
]


def build_board(data, logo_crop):
    theme = THEMES[data["theme"]]
    canvas = Image.new("RGB", (W, H), theme["bg"])
    draw = ImageDraw.Draw(canvas)

    draw.text((90, 70), f"CREATIVE TERRITORY {data['id']}  /  v0", font=F_KICKER, fill=theme["muted"])
    draw.rectangle((90, 116, 470, 122), fill=theme["accent"])
    draw.text((90, 152), data["title"], font=F_TITLE, fill=theme["text"])
    draw.text((94, 248), data["en"], font=F_EN, fill=theme["muted"])
    draw_logo_card(canvas, logo_crop, theme)

    image = Image.open(data["image"])
    rounded_paste(canvas, image, (90, 330, 1110, 880), radius=32)
    draw.rounded_rectangle((90, 1236, 1110, 1305), radius=16, fill=theme["panel"])
    draw.text((116, 1255), "辅助视觉：仅提炼系统语汇；未生成／重绘 Logo", font=F_BODY_SMALL, fill=theme["muted"])

    x, width = 1270, 840
    draw.text((x, 330), "核心主张", font=F_LABEL, fill=theme["accent"])
    y = draw_wrapped(draw, (x, 371), data["stance"], F_STANCE, theme["text"], width, spacing=12) + 35

    draw.text((x, y), "低成本假设", font=F_LABEL, fill=theme["accent"])
    y += 45
    base_number = (int(data["id"]) - 1) * 4 + 1
    for offset, hypothesis in enumerate(data["hypotheses"]):
        y = draw_hypothesis(draw, base_number + offset, hypothesis, x, y, width, theme)

    y += 6
    draw_palette(draw, data["palette"], data["palette_labels"], x, y, theme["muted"])
    y += 105

    draw.text((x, y), "若入选，如何延展", font=F_LABEL, fill=theme["accent"])
    y += 42
    draw.text((x, y), "电商", font=F_LABEL, fill=theme["muted"])
    y = draw_wrapped(draw, (x + 76, y - 2), data["ecom"], F_BODY_SMALL, theme["text"], width - 76, spacing=7) + 15
    draw.text((x, y), "门店", font=F_LABEL, fill=theme["muted"])
    y = draw_wrapped(draw, (x + 76, y - 2), data["store"], F_BODY_SMALL, theme["text"], width - 76, spacing=7) + 24

    draw.line((x, y, x + width, y), fill=theme["rule"], width=2)
    y += 22
    draw.text((x, y), "取舍", font=F_LABEL, fill=theme["accent"])
    draw_wrapped(draw, (x + 76, y - 3), data["tradeoff"], F_BODY_SMALL, theme["text"], width - 76, spacing=7)

    draw.text((90, 1343), data["cost"], font=F_BODY_SMALL, fill=theme["muted"])
    draw.text((1968, 1345), f"{data['id']} / 03", font=F_KICKER, fill=theme["muted"])

    out_path = OUT / f"territory-{data['id']}-{data['slug']}-board.png"
    canvas.save(out_path, quality=95)
    return out_path


def build_overview(logo_crop):
    bg = "#F1EEE8"
    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)
    draw.text((90, 68), "12 HYPOTHESES  /  3 TERRITORIES  /  1 LOCKED IDENTITY", font=F_KICKER, fill="#6E6258")
    draw.text((90, 118), "三个 Creative Territories", font=F_OV_TITLE, fill="#251D18")
    draw.text((94, 194), "同一现有 Logo，不同增长逻辑；本轮不制作淘宝主图或门店成品。", font=F_BODY, fill="#6E6258")
    draw_logo_card(canvas, logo_crop, {"shadow": "#D4CEC4"})

    cols = [(90, 640), (780, 640), (1470, 640)]
    for data, (x, cw) in zip(TERRITORIES, cols):
        theme = THEMES[data["theme"]]
        draw.rounded_rectangle((x, 300, x + cw, 1200), radius=26, fill=theme["bg"])
        image = Image.open(data["image"])
        rounded_paste(canvas, image, (x + 24, 324, cw - 48, 390), radius=18)
        draw.text((x + 28, 747), f"{data['id']}  {data['title']}", font=F_OV_HEAD, fill=theme["text"])
        draw.text((x + 30, 798), data["en"], font=font(18, medium=True, latin=True), fill=theme["muted"])
        y = draw_wrapped(draw, (x + 28, 846), data["stance"], F_OV_BODY, theme["text"], cw - 56, spacing=8) + 22
        draw_palette(draw, data["palette"], ["", "", "", ""], x + 28, y, theme["muted"])
        y += 58
        draw.text((x + 28, y), "优势", font=F_LABEL, fill=theme["accent"])
        strength = ["礼赠秩序最清晰", "食欲与工艺最直接", "资历与差异最鲜明"][int(data["id"]) - 1]
        draw.text((x + 100, y - 2), strength, font=F_OV_SMALL, fill=theme["text"])
        y += 43
        draw.text((x + 28, y), "代价", font=F_LABEL, fill=theme["accent"])
        cost = ["食欲需要产品图补足", "依赖高质量微距拍摄", "需要更多已核实史料"][int(data["id"]) - 1]
        draw.text((x + 100, y - 2), cost, font=F_OV_SMALL, fill=theme["text"])
        y += 52
        draw.text((x + 28, y), "延展", font=F_LABEL, fill=theme["accent"])
        extension = ["框景电商模板／模块礼盒墙", "层理主图背景／背光陈列", "档案卡信息层／索引式货架"][int(data["id"]) - 1]
        draw_wrapped(draw, (x + 100, y - 2), extension, F_OV_SMALL, theme["text"], cw - 128, spacing=6)

    draw.rounded_rectangle((90, 1240, 2110, 1340), radius=24, fill="#DED7CC")
    draw.text((120, 1265), "选择检查点", font=F_LABEL, fill="#8B1720")
    draw.text((270, 1260), "请选 01／02／03，或明确保留／淘汰的假设；本轮不自动混合。", font=F_BODY, fill="#2C211C")
    path = OUT / "creative-territories-overview.png"
    canvas.save(path, quality=95)
    return path


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    logo_crop, _ = save_locked_logo_crop()
    paths = [build_overview(logo_crop)]
    paths.extend(build_board(data, logo_crop) for data in TERRITORIES)
    for path in paths:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
