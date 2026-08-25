import base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v0"
SOURCE = ROOT / "inputs" / "01-product_reference.png"
FONT_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_MEDIUM = "/System/Library/Fonts/STHeiti Medium.ttc"


def font(size: int, medium: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_MEDIUM if medium else FONT_LIGHT, size=size)


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap_chars(draw: ImageDraw.ImageDraw, text: str, face, max_width: int):
    lines = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + ch
        if current and draw.textbbox((0, 0), candidate, font=face)[2] > max_width:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw, xy, text, face, fill, max_width, gap=9):
    x, y = xy
    lines = wrap_chars(draw, text, face, max_width)
    bbox = draw.textbbox((0, 0), "国Ag", font=face)
    line_h = bbox[3] - bbox[1]
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += line_h + gap
    return y


def alpha_cutout() -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    # Background-only extraction. Product pixels are never recolored, retouched,
    # mirrored, distorted, or regenerated. The crop is an allowed scale/placement move.
    crop = source.crop((155, 255, 869, 790))
    keyed = []
    for r, g, b, _ in crop.getdata():
        low = min(r, g, b)
        spread = max(r, g, b) - low
        # Remove neutral studio background and its grey floor haze so a dark
        # context cannot misread that haze as product illumination.
        if low >= 105 and spread <= 18:
            alpha = 0
        elif low >= 232 and spread <= 24:
            alpha = max(0, min(230, int((249 - low) / 17 * 230)))
        else:
            alpha = 255
        keyed.append((r, g, b, alpha))
    crop.putdata(keyed)
    crop.save(OUT / "product-cutout-preserve-identity.png")
    return crop


def paste_scaled(canvas: Image.Image, product: Image.Image, box):
    x, y, w, h = box
    ratio = min(w / product.width, h / product.height)
    size = (round(product.width * ratio), round(product.height * ratio))
    scaled = product.resize(size, Image.Resampling.LANCZOS)
    px = x + (w - size[0]) // 2
    py = y + (h - size[1]) // 2
    canvas.alpha_composite(scaled, (px, py))


def render_reference(product: Image.Image):
    W, H = 1600, 1100
    bg = "#F4EFE7"
    ink = "#2B221E"
    muted = "#756860"
    terracotta = "#B85E49"
    canvas = Image.new("RGBA", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    draw.text((76, 58), "REFERENCE DECONSTRUCTION · V0", font=font(22, True), fill=terracotta)
    draw.text((76, 100), "先锁定产品身份，再讨论视觉方向", font=font(52, True), fill=ink)
    draw.text((78, 172), "只提炼节奏、配色与构图原则；不借用外部品牌、文字或具体图形。", font=font(25), fill=muted)

    items = [
        ("01", "低矮圆柱", "宽于高的柔和机身，是第一识别轮廓。"),
        ("02", "悬浮薄盖", "扁平椭圆上盖与机身之间保留清楚停顿。"),
        ("03", "黑色环缝", "唯一强对比结构，负责建立层次与精度。"),
        ("04", "正面单圆键", "同色、克制、不可增删或改位。"),
        ("05", "陶土红哑光", "颜色和微颗粒触感保持原样，不加滤镜。"),
    ]
    y = 255
    for num, title, desc in items:
        draw.text((78, y), num, font=font(23, True), fill=terracotta)
        draw.text((145, y - 5), title, font=font(31, True), fill=ink)
        draw.text((145, y + 40), desc, font=font(22), fill=muted)
        draw.line((145, y + 82, 620, y + 82), fill="#D9CEC3", width=2)
        y += 122

    # Product shown from source pixels on a neutral contextual field.
    rounded(draw, (705, 242, 1520, 895), 36, "#EBE0D4")
    draw.ellipse((790, 352, 1435, 895), fill="#E5D5C8")
    paste_scaled(canvas, product, (730, 285, 760, 570))

    callouts = [
        ((1085, 430), (1425, 320), "悬浮薄盖"),
        ((1090, 500), (1430, 455), "黑色环缝"),
        ((1100, 670), (1435, 670), "陶土红哑光"),
        ((1080, 735), (1425, 805), "单圆键"),
    ]
    for p1, p2, label in callouts:
        draw.line((p1[0], p1[1], p2[0], p2[1]), fill=ink, width=2)
        draw.ellipse((p1[0]-5, p1[1]-5, p1[0]+5, p1[1]+5), fill=terracotta)
        tw = draw.textbbox((0, 0), label, font=font(20, True))[2]
        draw.text((min(p2[0] - tw, 1500 - tw), p2[1] - 29), label, font=font(20, True), fill=ink)

    rounded(draw, (76, 943, 1524, 1035), 22, "#2B221E")
    draw.text((108, 972), "批准文案", font=font(21, True), fill="#D9A28F")
    approved = ["让香气慢下来", "低噪运行", "定时关闭", "陶土触感"]
    x = 285
    for idx, phrase in enumerate(approved):
        draw.text((x, 967), phrase, font=font(26, True), fill="#F8F0E8")
        x += [270, 205, 205, 0][idx]
        if idx < 3:
            draw.ellipse((x - 33, 984, x - 25, 992), fill="#B85E49")

    canvas.convert("RGB").save(OUT / "reference-deconstruction.png", quality=95)


def draw_palette(draw, x, y, colors):
    for i, c in enumerate(colors):
        draw.ellipse((x + i * 50, y, x + i * 50 + 34, y + 34), fill=c)


def render_territories(product: Image.Image):
    W, H = 1800, 1450
    canvas = Image.new("RGBA", (W, H), "#F7F3ED")
    draw = ImageDraw.Draw(canvas)
    ink = "#29211E"
    muted = "#746861"
    terracotta = "#B85E49"

    draw.text((76, 48), "CREATIVE TERRITORIES · V0", font=font(22, True), fill=terracotta)
    draw.text((76, 90), "三条原创路径，等待选择", font=font(52, True), fill=ink)
    draw.text((76, 160), "同一产品身份与批准文案；只比较节奏、配色和构图。", font=font(25), fill=muted)

    panel_y, panel_h, panel_w = 232, 1135, 512
    xs = [76, 644, 1212]
    territories = [
        {
            "key": "A",
            "name": "陶土留白",
            "tag": "材质先行 · 编辑式留白",
            "panel": "#EFE3D2",
            "ink": "#2B211C",
            "muted": "#685B52",
            "accent": "#B85E49",
            "palette": ["#F3E9DA", "#B85E49", "#8F4638", "#2B211C"],
            "hyp": "H01 · H02 · H03 · H04",
            "rhythm": "大留白 / 低位重心 / 长停顿",
            "layout": "轻微非对称，产品与窄列文字错位。",
            "test": "先测骨白 vs 纯白，再测 35% vs 60% 产品占比。",
            "risk": "避免落入泛米色家居模板；陶土红必须唯一主导。",
        },
        {
            "key": "B",
            "name": "静域圆场",
            "tag": "安静技术感 · 稳定中轴",
            "panel": "#221D1B",
            "ink": "#F4ECE2",
            "muted": "#C6B8AE",
            "accent": "#D47A62",
            "palette": ["#201B19", "#4A3430", "#B85E49", "#F1E7DB"],
            "hyp": "H05 · H06 · H07",
            "rhythm": "严格中轴 / 低对比 / 少量椭圆",
            "layout": "产品居中，形态线只回应盖体与环缝。",
            "test": "测居中 vs 偏置，并检查暗底上的环缝与按键。",
            "risk": "不用声波、水波、发光或夜间功效暗示。",
        },
        {
            "key": "C",
            "name": "慢刻序列",
            "tag": "时间节奏 · 三拍阅读",
            "panel": "#D7A08F",
            "ink": "#2A2321",
            "muted": "#5C4943",
            "accent": "#F8EFE7",
            "palette": ["#D7A08F", "#B85E49", "#2A2321", "#F7F1EA"],
            "hyp": "H08 · H09 · H10",
            "rhythm": "分段栅格 / 递增间隔 / 一句一拍",
            "layout": "产品与文字交替，时间由间隔而非钟表表达。",
            "test": "测密排 vs 三段排版，再做三屏顺序回忆。",
            "risk": "不出现钟面、具体时长、进度状态或参数。",
        },
    ]

    for x, t in zip(xs, territories):
        rounded(draw, (x, panel_y, x + panel_w, panel_y + panel_h), 30, t["panel"])
        draw.text((x + 34, panel_y + 28), t["key"], font=font(28, True), fill=t["accent"])
        draw.text((x + 86, panel_y + 18), t["name"], font=font(42, True), fill=t["ink"])
        draw.text((x + 36, panel_y + 78), t["tag"], font=font(22), fill=t["muted"])

        stage = (x + 28, panel_y + 130, x + panel_w - 28, panel_y + 492)
        if t["key"] == "A":
            rounded(draw, stage, 22, "#F6EEE3")
            draw.text((stage[0] + 28, stage[1] + 28), "让香气\n慢下来", font=font(38, True), fill="#2B211C", spacing=8)
            draw.line((stage[0] + 28, stage[1] + 142, stage[0] + 132, stage[1] + 142), fill="#B85E49", width=4)
            paste_scaled(canvas, product, (stage[0] + 115, stage[1] + 70, 330, 285))
        elif t["key"] == "B":
            rounded(draw, stage, 22, "#171312")
            cx = (stage[0] + stage[2]) // 2
            cy = stage[1] + 220
            for i, color in enumerate(["#4B302C", "#6C3E35", "#8B4C40"]):
                ew = 385 - i * 65
                eh = 230 - i * 35
                draw.ellipse((cx - ew//2, cy - eh//2, cx + ew//2, cy + eh//2), outline=color, width=2)
            tw = draw.textbbox((0, 0), "低噪运行", font=font(28, True))[2]
            draw.text((cx - tw//2, stage[1] + 24), "低噪运行", font=font(28, True), fill="#F1E7DB")
            paste_scaled(canvas, product, (stage[0] + 50, stage[1] + 88, 360, 270))
        else:
            rounded(draw, stage, 22, "#F2D1C5")
            # Three unequal intervals carry the time idea without a clock or duration.
            for i, w in enumerate([58, 102, 168]):
                draw.rounded_rectangle((stage[0] + 28, stage[1] + 278 + i*19,
                                        stage[0] + 28 + w, stage[1] + 286 + i*19),
                                       radius=4, fill="#2A2321")
            draw.text((stage[0] + 28, stage[1] + 28), "让香气", font=font(28, True), fill="#2A2321")
            draw.text((stage[0] + 28, stage[1] + 75), "慢下来", font=font(40, True), fill="#2A2321")
            paste_scaled(canvas, product, (stage[0] + 115, stage[1] + 50, 340, 280))

        info_y = panel_y + 530
        draw.text((x + 34, info_y), "色板", font=font(20, True), fill=t["muted"])
        draw_palette(draw, x + 112, info_y - 3, t["palette"])
        draw.text((x + 34, info_y + 68), "节奏", font=font(20, True), fill=t["muted"])
        draw_wrapped(draw, (x + 112, info_y + 62), t["rhythm"], font(21), t["ink"], 350, gap=4)
        draw.text((x + 34, info_y + 132), "构图", font=font(20, True), fill=t["muted"])
        end_y = draw_wrapped(draw, (x + 112, info_y + 125), t["layout"], font(21), t["ink"], 350, gap=5)

        line_y = max(info_y + 205, end_y + 22)
        draw.line((x + 34, line_y, x + panel_w - 34, line_y), fill=t["muted"], width=1)
        draw.text((x + 34, line_y + 28), "假设簇", font=font(20, True), fill=t["muted"])
        draw.text((x + 34, line_y + 65), t["hyp"], font=font(28, True), fill=t["ink"])
        draw.text((x + 34, line_y + 125), "低成本验证", font=font(20, True), fill=t["muted"])
        test_end = draw_wrapped(draw, (x + 34, line_y + 162), t["test"], font(21), t["ink"], panel_w - 68, gap=5)
        draw.text((x + 34, test_end + 25), "风险护栏", font=font(20, True), fill=t["muted"])
        draw_wrapped(draw, (x + 34, test_end + 62), t["risk"], font(21), t["ink"], panel_w - 68, gap=5)

        rounded(draw, (x + 34, panel_y + panel_h - 84, x + panel_w - 34, panel_y + panel_h - 30), 18,
                t["ink"])
        label = f"选择 {t['key']}"
        lw = draw.textbbox((0, 0), label, font=font(22, True))[2]
        draw.text((x + (panel_w - lw)//2, panel_y + panel_h - 73), label,
                  font=font(22, True), fill=t["panel"])

    canvas.convert("RGB").save(OUT / "creative-territories-board.png", quality=95)


def render_selector_fragment():
    template = (OUT / "creative-territory-selector.fragment.html.template").read_text(encoding="utf-8")
    product_bytes = (OUT / "product-cutout-preserve-identity.png").read_bytes()
    product_data = "data:image/png;base64," + base64.b64encode(product_bytes).decode("ascii")
    fragment = template.replace("__PRODUCT_DATA__", product_data)
    (OUT / "creative-territory-selector.html").write_text(fragment, encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cutout = alpha_cutout()
    render_reference(cutout)
    render_territories(cutout)
    render_selector_fragment()
