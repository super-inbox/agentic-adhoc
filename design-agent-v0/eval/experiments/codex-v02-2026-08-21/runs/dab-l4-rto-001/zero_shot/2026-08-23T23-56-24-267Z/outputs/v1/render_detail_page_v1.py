import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v1"
PRODUCT_SOURCE = ROOT / "outputs" / "v0" / "product-cutout-preserve-identity.png"

WIDTH = 1440
HEIGHT = 1080
SUPERSAMPLE = 2

# Locked once for all three panels. This proportion maps the approved v0
# Direction-C preview to the final frame and is never varied by panel.
PRODUCT_SLOT = (340, 190, 1070, 850)

FONT_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_MEDIUM = "/System/Library/Fonts/STHeiti Medium.ttc"

PALETTE = {
    "dusty_clay": "#D7A08F",
    "terracotta": "#B85E49",
    "deep_ink": "#2A2321",
    "warm_bone": "#F7F1EA",
    "deep_clay": "#8F4638",
}


def font(size: int, medium: bool = False):
    return ImageFont.truetype(FONT_MEDIUM if medium else FONT_LIGHT, size=size)


def rgba(hex_color: str, alpha: int = 255):
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def scaled_box(box):
    return tuple(round(value * SUPERSAMPLE) for value in box)


def arc_endpoint(box, angle):
    left, top, right, bottom = box
    cx = (left + right) / 2
    cy = (top + bottom) / 2
    rx = (right - left) / 2
    ry = (bottom - top) / 2
    rad = math.radians(angle)
    return cx + rx * math.cos(rad), cy + ry * math.sin(rad)


def draw_open_arc(layer, box, start, end, color, width):
    """Draw a rounded, deliberately open arc; no closed rings are permitted."""
    draw = ImageDraw.Draw(layer)
    hi_box = scaled_box(box)
    hi_width = round(width * SUPERSAMPLE)
    draw.arc(hi_box, start=start, end=end, fill=color, width=hi_width)
    radius = hi_width / 2
    for angle in (start, end):
        px, py = arc_endpoint(hi_box, angle)
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)


def quadratic_point(p0, p1, p2, t):
    u = 1 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def draw_clay_particles(layer, *, seed, count, curve, spread, colors, radius_range):
    """Create an irregular, non-grid particle field following an open curve."""
    rng = random.Random(seed)
    draw = ImageDraw.Draw(layer)
    p0, p1, p2 = curve
    for _ in range(count):
        # Bias toward the beginning of the curve to avoid even spacing.
        t = rng.random() ** rng.uniform(0.72, 1.45)
        x, y = quadratic_point(p0, p1, p2, t)
        x += rng.gauss(0, spread * (0.35 + 0.9 * t))
        y += rng.gauss(0, spread * (0.75 - 0.25 * t))
        radius = rng.uniform(*radius_range) * (0.55 + 0.7 * rng.random())
        stretch = rng.uniform(0.68, 1.42)
        fill = colors[rng.randrange(len(colors))]
        box = (
            round((x - radius * stretch) * SUPERSAMPLE),
            round((y - radius / stretch) * SUPERSAMPLE),
            round((x + radius * stretch) * SUPERSAMPLE),
            round((y + radius / stretch) * SUPERSAMPLE),
        )
        draw.ellipse(box, fill=fill)


def make_background(name):
    if name == "hero":
        base = PALETTE["dusty_clay"]
        arcs = [
            ((-470, 285, 815, 1570), 207, 339, rgba(PALETTE["warm_bone"], 205), 42),
            ((-315, 250, 980, 1490), 216, 332, rgba(PALETTE["terracotta"], 185), 12),
            ((925, -515, 1830, 455), 78, 202, rgba(PALETTE["warm_bone"], 105), 24),
        ]
        particles = dict(
            seed=311,
            count=230,
            curve=((20, 940), (215, 575), (585, 420)),
            spread=74,
            colors=[rgba(PALETTE["terracotta"], 125), rgba(PALETTE["deep_clay"], 82), rgba(PALETTE["warm_bone"], 105)],
            radius_range=(2.2, 8.5),
        )
    elif name == "function":
        base = PALETTE["deep_ink"]
        arcs = [
            ((-560, 260, 845, 1650), 204, 342, rgba(PALETTE["dusty_clay"], 190), 46),
            ((-300, 315, 1050, 1550), 214, 325, rgba(PALETTE["terracotta"], 220), 13),
            ((850, -470, 1880, 525), 72, 198, rgba(PALETTE["warm_bone"], 75), 20),
        ]
        particles = dict(
            seed=517,
            count=205,
            curve=((5, 915), (220, 565), (620, 440)),
            spread=68,
            colors=[rgba(PALETTE["terracotta"], 165), rgba(PALETTE["dusty_clay"], 118), rgba(PALETTE["warm_bone"], 72)],
            radius_range=(2.0, 7.4),
        )
    else:
        base = PALETTE["warm_bone"]
        arcs = [
            ((-520, 235, 860, 1585), 205, 343, rgba(PALETTE["terracotta"], 205), 52),
            ((-285, 270, 1025, 1495), 218, 329, rgba(PALETTE["dusty_clay"], 205), 11),
            ((875, -520, 1840, 475), 76, 204, rgba(PALETTE["terracotta"], 86), 25),
        ]
        particles = dict(
            seed=829,
            count=285,
            curve=((0, 955), (220, 535), (640, 415)),
            spread=82,
            colors=[rgba(PALETTE["terracotta"], 145), rgba(PALETTE["deep_clay"], 105), rgba(PALETTE["dusty_clay"], 180)],
            radius_range=(2.0, 10.5),
        )

    background = Image.new("RGBA", (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE), rgba(base))
    arc_layer = Image.new("RGBA", background.size, (0, 0, 0, 0))
    for spec in arcs:
        draw_open_arc(arc_layer, *spec)
    particle_layer = Image.new("RGBA", background.size, (0, 0, 0, 0))
    draw_clay_particles(particle_layer, **particles)
    background = Image.alpha_composite(background, arc_layer)
    background = Image.alpha_composite(background, particle_layer)
    return background.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS), arcs, particles


def prepare_product():
    product = Image.open(PRODUCT_SOURCE).convert("RGBA")
    # Suppress only high-luminance, low-chroma edge pixels left by the original
    # white studio background. RGB values are retained; only their background-
    # contaminated alpha is reduced before scaling.
    cleaned = []
    for r, g, b, alpha in product.getdata():
        low = min(r, g, b)
        spread = max(r, g, b) - low
        if alpha and low >= 238 and spread <= 35:
            alpha = 0
        elif alpha and low >= 205 and spread <= 35:
            alpha = round(alpha * max(0.0, min(1.0, (238 - low) / 33)))
        cleaned.append((r, g, b, alpha))
    product.putdata(cleaned)
    x, y, target_w, target_h = PRODUCT_SLOT
    ratio = min(target_w / product.width, target_h / product.height)
    size = (round(product.width * ratio), round(product.height * ratio))
    # Resize in premultiplied-alpha space so transparent studio-white RGB does
    # not bleed into the edge. This changes only compositing fringe, not the
    # product color, geometry, position, or scale.
    scaled = product.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    edge_alpha = scaled.getchannel("A").filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.35))
    scaled.putalpha(edge_alpha)
    px = x + (target_w - size[0]) // 2
    py = y + (target_h - size[1]) // 2
    alpha_box = scaled.getchannel("A").getbbox()
    visible_box = [px + alpha_box[0], py + alpha_box[1], px + alpha_box[2], py + alpha_box[3]]
    return scaled, (px, py), visible_box


def add_copy(canvas, name):
    draw = ImageDraw.Draw(canvas)
    if name == "hero":
        draw.multiline_text((72, 64), "让香气\n慢下来", font=font(112, True), fill=PALETTE["deep_ink"], spacing=10)
    elif name == "function":
        draw.text((68, 76), "低噪运行", font=font(78, True), fill=PALETTE["warm_bone"])
        draw.text((68, 210), "定时关闭", font=font(78, True), fill=PALETTE["dusty_clay"])
    else:
        draw.text((68, 80), "陶土触感", font=font(92, True), fill=PALETTE["deep_ink"])


def render_panel(name, filename, product, product_xy):
    canvas, arcs, particles = make_background(name)
    canvas.alpha_composite(product, product_xy)
    add_copy(canvas, name)
    canvas.convert("RGB").save(OUT / filename, quality=96)
    return {
        "name": name,
        "path": f"outputs/v1/{filename}",
        "dimensions": [WIDTH, HEIGHT],
        "product_image_xy": list(product_xy),
        "arc_spans_degrees": [spec[2] - spec[1] for spec in arcs],
        "particle_count": particles["count"],
        "particle_seed": particles["seed"],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    product, product_xy, visible_box = prepare_product()
    panels = [
        render_panel("hero", "hero-slow-arcs.png", product, product_xy),
        render_panel("function", "selling-module-low-noise-timer.png", product, product_xy),
        render_panel("material", "selling-module-clay-touch.png", product, product_xy),
    ]

    page = Image.new("RGB", (WIDTH, HEIGHT * 3))
    for index, panel in enumerate(panels):
        image = Image.open(ROOT / panel["path"]).convert("RGB")
        page.paste(image, (0, HEIGHT * index))
    page.save(OUT / "detail-page-v1.png", quality=96)

    metadata = {
        "version": "v1",
        "selected_territory": "C 慢刻序列",
        "canvas_dimensions": [WIDTH, HEIGHT],
        "product_slot_locked": list(PRODUCT_SLOT),
        "product_image_xy_locked": list(product_xy),
        "product_visible_box_locked": visible_box,
        "product_source": "outputs/v0/product-cutout-preserve-identity.png",
        "consumer_copy": {
            "hero": ["让香气慢下来"],
            "function": ["低噪运行", "定时关闭"],
            "material": ["陶土触感"],
        },
        "visual_language": {
            "removed": ["直线间隔刻度", "封闭几何", "同心环"],
            "added": ["非闭合开放弧线", "非网格不规则陶土颗粒"],
            "arc_span_rule": "每段小于 180 度",
        },
        "panels": panels,
        "combined_page": {
            "path": "outputs/v1/detail-page-v1.png",
            "dimensions": [WIDTH, HEIGHT * 3],
        },
    }
    (OUT / "render-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
