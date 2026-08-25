from pathlib import Path

from PIL import Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path.cwd()
INPUTS = ROOT / "inputs"
OUT = ROOT / "outputs" / "v0"
ASSETS = OUT / "assets"
PDF_PATH = OUT / "mori-night-fragrance-kv-hypotheses-v0.pdf"

OFF_WHITE = "#F4F0DF"
PAPER_WHITE = "#FBF8EA"
CHARCOAL = "#2D2E2B"
TERRACOTTA = "#B6533D"
OLIVE = "#88945F"
PALE_BLUE = "#B7D4DB"
HAIRLINE = "#D6D0C0"

PRODUCT_PATH = INPUTS / "02-launch_product.png"
BRAND_PATH = INPUTS / "01-brand_guideline.png"
BG_A = ASSETS / "territory-a-quiet-geometry-bg.png"
BG_B = ASSETS / "territory-b-tactile-ritual-bg.png"
BG_C = ASSETS / "territory-c-afterglow-bg.png"
LOGO_PATH = ASSETS / "mori-wordmark-exact-crop.png"


def register_fonts():
    pdfmetrics.registerFont(TTFont("ArialUnicode", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"))


def crop_exact_logo():
    # Exact source-pixel crop from the supplied brand board; no redrawing or recoloring.
    with Image.open(BRAND_PATH) as im:
        im.crop((260, 55, 620, 167)).save(LOGO_PATH)


register_fonts()
crop_exact_logo()

PRODUCT = ImageReader(str(PRODUCT_PATH))
LOGO = ImageReader(str(LOGO_PATH))
BACKGROUNDS = {
    "A": ImageReader(str(BG_A)),
    "B": ImageReader(str(BG_B)),
    "C": ImageReader(str(BG_C)),
}


CANDIDATES = [
    {"id": "A1", "title": "Horizon Field / 地平线", "production": "2 张色卡 + 侧光", "territory": "A", "filename": "a1-horizon-field.png"},
    {"id": "A2", "title": "Breathing Frame / 呼吸框", "production": "纸框 + 现成 packshot", "territory": "A", "filename": "a2-breathing-frame.png"},
    {"id": "A3", "title": "Cadence Blocks / 节拍色块", "production": "3 色卡 + 平铺", "territory": "A", "filename": "a3-cadence-blocks.png"},
    {"id": "B1", "title": "Linen Fold / 亚麻褶", "production": "亚麻 + 手工纸", "territory": "B", "filename": "b1-linen-fold.png"},
    {"id": "B2", "title": "Paper Window / 纸窗", "production": "撕边纸 + 单灯", "territory": "B", "filename": "b2-paper-window.png"},
    {"id": "B3", "title": "Ceramic Marker / 陶片", "production": "陶片 + 压纹纸", "territory": "B", "filename": "b3-ceramic-marker.png"},
    {"id": "C1", "title": "Dusk Split / 暮色切面", "production": "黑卡 + 柔光", "territory": "C", "filename": "c1-dusk-split.png"},
    {"id": "C2", "title": "Ember Halo / 余温光晕", "production": "暖灯 + 圆形遮片", "territory": "C", "filename": "c2-ember-halo.png"},
    {"id": "C3", "title": "Quiet Threshold / 静夜门槛", "production": "双背景板 + 单灯", "territory": "C", "filename": "c3-quiet-threshold.png"},
]


TERRITORIES = {
    "A": {
        "title": "TERRITORY A - QUIET GEOMETRY",
        "cn": "静默几何",
        "note": "平面色块与大留白；最易复刻、最利于后续响应式裁切",
    },
    "B": {
        "title": "TERRITORY B - TACTILE RITUAL",
        "cn": "触感仪式",
        "note": "亚麻、手工纸与陶片；触觉最强、仪式感最直接",
    },
    "C": {
        "title": "TERRITORY C - AFTERGLOW",
        "cn": "夜色余温",
        "note": "黑卡与暖光投影；夜间辨识最高、情绪更浓",
    },
}


def color(c, hex_value):
    c.setFillColor(hex_value)
    c.setStrokeColor(hex_value)


def top_y(canvas_h, y, h):
    return canvas_h - y - h


def rect_top(c, x, y, w, h, canvas_h, fill_color, stroke_color=None, line_width=1):
    c.saveState()
    c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(line_width)
    c.rect(x, top_y(canvas_h, y, h), w, h, stroke=1 if stroke_color else 0, fill=1)
    c.restoreState()


def image_dimensions(reader):
    return reader.getSize()


def draw_image_fit(c, reader, x, y, w, h, canvas_h, preserve=True):
    iw, ih = image_dimensions(reader)
    if preserve:
        scale = min(w / iw, h / ih)
        dw, dh = iw * scale, ih * scale
        dx = x + (w - dw) / 2
        dy = top_y(canvas_h, y, h) + (h - dh) / 2
    else:
        dx, dy, dw, dh = x, top_y(canvas_h, y, h), w, h
    c.drawImage(reader, dx, dy, width=dw, height=dh, preserveAspectRatio=False, mask="auto")


def draw_image_fill(c, reader, x, y, w, h, canvas_h, focal_x=0.5, focal_y=0.5):
    iw, ih = image_dimensions(reader)
    scale = max(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    dx = x + (w - dw) * focal_x
    base_y = top_y(canvas_h, y, h)
    dy = base_y + (h - dh) * focal_y
    c.saveState()
    path = c.beginPath()
    path.rect(x, base_y, w, h)
    c.clipPath(path, stroke=0, fill=0)
    c.drawImage(reader, dx, dy, width=dw, height=dh, preserveAspectRatio=False, mask="auto")
    c.restoreState()


def draw_logo(c, x, y, w, canvas_h, mat=False):
    iw, ih = image_dimensions(LOGO)
    h = w * ih / iw
    if mat:
        rect_top(c, x - 14, y - 10, w + 28, h + 20, canvas_h, OFF_WHITE)
    draw_image_fit(c, LOGO, x, y, w, h, canvas_h)


def draw_packshot(c, x, y, size, canvas_h, border_color=OFF_WHITE, border=12):
    rect_top(c, x, y, size, size, canvas_h, border_color)
    draw_image_fit(c, PRODUCT, x + border, y + border, size - 2 * border, size - 2 * border, canvas_h)


def draw_multiline(c, text, x, y, width, font_name, font_size, fill, canvas_h, leading=None, align="left"):
    leading = leading or font_size * 1.2
    text_obj = c.beginText()
    text_obj.setFont(font_name, font_size)
    text_obj.setFillColor(fill)
    text_obj.setLeading(leading)
    lines = text.split("\n")
    baseline = canvas_h - y - font_size
    for index, line in enumerate(lines):
        if align == "center":
            line_width = pdfmetrics.stringWidth(line, font_name, font_size)
            line_x = x + (width - line_width) / 2
        elif align == "right":
            line_width = pdfmetrics.stringWidth(line, font_name, font_size)
            line_x = x + width - line_width
        else:
            line_x = x
        text_obj.setTextOrigin(line_x, baseline - index * leading)
        text_obj.textOut(line)
    c.drawText(text_obj)


def draw_approved_copy(c, x, y, width, fill, canvas_h, align="left", compact=False):
    english_size = 34 if compact else 48
    chinese_size = 27 if compact else 34
    draw_multiline(c, "Quiet hours,\nmade tangible.", x, y, width, "Times-Roman", english_size, fill, canvas_h, english_size * 1.12, align)
    draw_multiline(c, "让夜晚慢下来。", x, y + (112 if compact else 154), width, "ArialUnicode", chinese_size, fill, canvas_h, chinese_size * 1.2, align)


def draw_candidate(c, candidate_id, x, y, w, h):
    sx, sy = w / 1200.0, h / 1500.0
    c.saveState()
    c.translate(x, y)
    c.scale(sx, sy)
    H = 1500

    if candidate_id == "A1":
        draw_image_fill(c, BACKGROUNDS["A"], 0, 0, 1200, 1500, H, 0.44, 0.52)
        rect_top(c, 64, 62, 410, 440, H, OFF_WHITE)
        draw_logo(c, 94, 92, 230, H)
        draw_approved_copy(c, 94, 235, 340, CHARCOAL, H)
        draw_packshot(c, 555, 755, 570, H, OFF_WHITE, 14)
    elif candidate_id == "A2":
        rect_top(c, 0, 0, 1200, 1500, H, OFF_WHITE)
        rect_top(c, 1040, 0, 160, 1500, H, TERRACOTTA)
        draw_image_fill(c, BACKGROUNDS["A"], 0, 1010, 1040, 490, H, 0.48, 0.22)
        draw_logo(c, 80, 74, 235, H)
        draw_approved_copy(c, 80, 242, 460, CHARCOAL, H)
        draw_packshot(c, 420, 575, 555, H, PAPER_WHITE, 16)
        c.setStrokeColor(TERRACOTTA)
        c.setLineWidth(5)
        c.rect(382, top_y(H, 537, 631), 631, 631, stroke=1, fill=0)
    elif candidate_id == "A3":
        rect_top(c, 0, 0, 1200, 1500, H, OFF_WHITE)
        rect_top(c, 0, 0, 300, 260, H, CHARCOAL)
        rect_top(c, 300, 0, 300, 260, H, OLIVE)
        rect_top(c, 600, 0, 600, 260, H, TERRACOTTA)
        draw_logo(c, 70, 300, 230, H)
        draw_image_fill(c, BACKGROUNDS["A"], 610, 520, 590, 980, H, 0.55, 0.45)
        draw_packshot(c, 70, 770, 520, H, PAPER_WHITE, 14)
        draw_approved_copy(c, 70, 465, 450, CHARCOAL, H)
    elif candidate_id == "B1":
        draw_image_fill(c, BACKGROUNDS["B"], 0, 0, 1200, 1500, H, 0.42, 0.54)
        rect_top(c, 62, 62, 475, 475, H, OFF_WHITE)
        draw_logo(c, 92, 96, 225, H)
        draw_approved_copy(c, 92, 250, 390, CHARCOAL, H)
        draw_packshot(c, 585, 790, 545, H, OFF_WHITE, 14)
    elif candidate_id == "B2":
        rect_top(c, 0, 0, 1200, 1500, H, OFF_WHITE)
        draw_image_fill(c, BACKGROUNDS["B"], 0, 0, 1200, 610, H, 0.54, 0.56)
        rect_top(c, 608, 712, 18, 545, H, TERRACOTTA)
        draw_logo(c, 70, 660, 230, H)
        draw_packshot(c, 70, 805, 500, H, PAPER_WHITE, 14)
        draw_approved_copy(c, 690, 835, 420, CHARCOAL, H)
    elif candidate_id == "B3":
        draw_image_fill(c, BACKGROUNDS["B"], 0, 0, 1200, 1500, H, 0.58, 0.48)
        rect_top(c, 0, 1020, 1200, 480, H, OFF_WHITE)
        rect_top(c, 76, 880, 230, 230, H, TERRACOTTA)
        draw_packshot(c, 335, 570, 530, H, PAPER_WHITE, 18)
        draw_logo(c, 72, 1085, 225, H)
        draw_approved_copy(c, 430, 1090, 650, CHARCOAL, H, compact=True)
    elif candidate_id == "C1":
        draw_image_fill(c, BACKGROUNDS["C"], 0, 0, 1200, 1500, H, 0.55, 0.48)
        draw_logo(c, 72, 72, 225, H, mat=True)
        draw_approved_copy(c, 705, 240, 410, CHARCOAL, H)
        draw_packshot(c, 570, 810, 560, H, OFF_WHITE, 14)
    elif candidate_id == "C2":
        rect_top(c, 0, 0, 1200, 1500, H, OFF_WHITE)
        rect_top(c, 38, 38, 1124, 1424, H, CHARCOAL)
        c.saveState()
        clip = c.beginPath()
        clip.circle(600, top_y(H, 270, 840) + 420, 420)
        c.clipPath(clip, stroke=0, fill=0)
        draw_image_fill(c, BACKGROUNDS["C"], 180, 270, 840, 840, H, 0.62, 0.48)
        c.restoreState()
        draw_logo(c, 72, 72, 225, H, mat=True)
        draw_approved_copy(c, 74, 1180, 1050, OFF_WHITE, H, align="center", compact=True)
        draw_packshot(c, 355, 505, 490, H, OFF_WHITE, 12)
    elif candidate_id == "C3":
        rect_top(c, 0, 0, 1200, 1500, H, OFF_WHITE)
        rect_top(c, 0, 0, 410, 1500, H, CHARCOAL)
        draw_image_fill(c, BACKGROUNDS["C"], 410, 440, 790, 1060, H, 0.54, 0.48)
        draw_logo(c, 510, 70, 230, H)
        draw_approved_copy(c, 510, 225, 580, CHARCOAL, H)
        draw_packshot(c, 535, 775, 535, H, OFF_WHITE, 14)
    c.restoreState()


def draw_overview_page(c):
    W, H = 2400, 1600
    c.setPageSize((W, H))
    rect_top(c, 0, 0, W, H, H, PAPER_WHITE)
    rect_top(c, 0, 0, 22, H, H, TERRACOTTA)
    draw_logo(c, 76, 52, 205, H)
    draw_multiline(c, "NIGHT FRAGRANCE - KV HYPOTHESES", 350, 54, 1000, "Helvetica-Bold", 31, CHARCOAL, H)
    draw_multiline(c, "9 个低成本假设 / 3 个 Creative Territories / 等待内部选择", 350, 108, 1250, "ArialUnicode", 23, "#67675F", H)
    draw_multiline(c, "选择格式：Territory + KV 编号（例如 B + B2）", 1600, 88, 700, "ArialUnicode", 21, TERRACOTTA, H, align="right")

    row_ys = [220, 690, 1160]
    for row, code in enumerate(["A", "B", "C"]):
        meta = TERRITORIES[code]
        draw_multiline(c, meta["title"], 78, row_ys[row], 430, "Helvetica-Bold", 22, CHARCOAL, H)
        draw_multiline(c, meta["cn"], 78, row_ys[row] + 48, 300, "ArialUnicode", 23, TERRACOTTA, H)
        draw_multiline(c, meta["note"], 78, row_ys[row] + 100, 390, "ArialUnicode", 17, "#6A6A62", H, leading=25)
        group = [item for item in CANDIDATES if item["territory"] == code]
        xs = [530, 1145, 1760]
        for idx, item in enumerate(group):
            draw_candidate(c, item["id"], xs[idx], top_y(H, row_ys[row], 375), 300, 375)
            c.setStrokeColor(HAIRLINE)
            c.rect(xs[idx], top_y(H, row_ys[row], 375), 300, 375, stroke=1, fill=0)
            draw_multiline(c, f'{item["id"]}  {item["title"]}', xs[idx] + 325, row_ys[row] + 92, 240, "ArialUnicode", 17, CHARCOAL, H, leading=24)
            draw_multiline(c, item["production"], xs[idx] + 325, row_ys[row] + 220, 225, "ArialUnicode", 16, "#77766E", H)
    c.showPage()


def draw_territory_page(c, code):
    W, H = 1920, 1080
    c.setPageSize((W, H))
    rect_top(c, 0, 0, W, H, H, PAPER_WHITE)
    rect_top(c, 0, 0, 18, H, H, TERRACOTTA)
    draw_logo(c, 72, 58, 190, H)
    meta = TERRITORIES[code]
    draw_multiline(c, meta["title"], 330, 59, 980, "Helvetica-Bold", 31, CHARCOAL, H)
    draw_multiline(c, meta["cn"], 330, 108, 350, "ArialUnicode", 29, TERRACOTTA, H)
    draw_multiline(c, meta["note"], 690, 112, 1000, "ArialUnicode", 21, "#6A6A62", H)
    group = [item for item in CANDIDATES if item["territory"] == code]
    xs = [100, 690, 1280]
    for idx, item in enumerate(group):
        draw_candidate(c, item["id"], xs[idx], top_y(H, 212, 638), 510, 638)
        c.setStrokeColor(HAIRLINE)
        c.rect(xs[idx], top_y(H, 212, 638), 510, 638, stroke=1, fill=0)
        draw_multiline(c, item["id"], xs[idx], 880, 55, "Helvetica-Bold", 24, TERRACOTTA, H)
        draw_multiline(c, item["title"], xs[idx] + 58, 881, 440, "ArialUnicode", 21, CHARCOAL, H)
        draw_multiline(c, item["production"], xs[idx] + 58, 926, 440, "ArialUnicode", 18, "#77766E", H)
    draw_multiline(c, "Internal selection board - consumer-facing text inside each KV is approved copy only", 100, 1007, 1500, "Helvetica", 16, "#8A897F", H)
    c.showPage()


def draw_full_candidate_page(c, item):
    W, H = 1200, 1500
    c.setPageSize((W, H))
    draw_candidate(c, item["id"], 0, 0, W, H)
    c.showPage()


pdf = canvas.Canvas(str(PDF_PATH), pagesize=(2400, 1600), pageCompression=1)
pdf.setTitle("MORI Night Fragrance - KV Hypotheses v0")
pdf.setAuthor("Candidate Design Agent")
pdf.setSubject("9 low-cost KV hypotheses grouped into 3 Creative Territories")

draw_overview_page(pdf)
for territory_code in ["A", "B", "C"]:
    draw_territory_page(pdf, territory_code)
for candidate in CANDIDATES:
    draw_full_candidate_page(pdf, candidate)

pdf.save()
print(PDF_PATH)
