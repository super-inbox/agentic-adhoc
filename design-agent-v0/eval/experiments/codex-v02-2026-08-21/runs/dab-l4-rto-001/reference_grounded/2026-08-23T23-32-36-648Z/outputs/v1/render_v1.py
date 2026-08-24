from pathlib import Path
import math
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent
PRODUCT_PATH = ROOT / "product-reference-exact.png"
CANVAS = (1500, 2000)

# This anchor is intentionally identical in all three modules.
PRODUCT_ANCHOR = (675, 1045, 1460, 1625)

CREAM = "#F4EFE4"
PAPER = "#FFF9EF"
CLAY = "#B65343"
DEEP_CLAY = "#71362E"
CHARCOAL = "#292825"
OAT = "#D8C7AA"
OLIVE = "#7F8B60"
MUTED = "#7A6E61"

SANS_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
SERIF_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"


def sans(size, bold=False):
    return ImageFont.truetype(SANS_PATH, size=size, index=2 if bold else 0)


def serif(size, bold=False):
    return ImageFont.truetype(SERIF_PATH, size=size, index=1 if bold else 6)


def label(draw, xy, value, font, fill=CHARCOAL, anchor="la"):
    draw.text(xy, value, font=font, fill=fill, anchor=anchor)


def cubic_points(p0, p1, p2, p3, count=180):
    points = []
    for i in range(count):
        t = i / (count - 1)
        u = 1 - t
        x = (
            u**3 * p0[0]
            + 3 * u**2 * t * p1[0]
            + 3 * u * t**2 * p2[0]
            + t**3 * p3[0]
        )
        y = (
            u**3 * p0[1]
            + 3 * u**2 * t * p1[1]
            + 3 * u * t**2 * p2[1]
            + t**3 * p3[1]
        )
        points.append((x, y))
    return points


def tapered_arc(base, control_points, color, width_start, width_end):
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    points = cubic_points(*control_points)
    for i in range(len(points) - 1):
        t = i / (len(points) - 2)
        # A gentle ease prevents the ribbon from looking like a mechanical circle.
        eased = t * t * (3 - 2 * t)
        width = max(2, int(width_start + (width_end - width_start) * eased))
        p0, p1 = points[i], points[i + 1]
        draw.line((p0, p1), fill=color, width=width)
        r = width / 2
        draw.ellipse((p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r), fill=color)
    base.alpha_composite(overlay)


def fine_arc(base, control_points, color, width=8):
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.line(cubic_points(*control_points), fill=color, width=width, joint="curve")
    base.alpha_composite(overlay)


def granule_cluster(base, center, spread, count, palette, seed, size_range=(4, 22)):
    rng = random.Random(seed)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = center
    sx, sy = spread
    for _ in range(count):
        x = rng.gauss(cx, sx)
        y = rng.gauss(cy, sy)
        radius = rng.uniform(*size_range)
        sides = rng.randint(5, 8)
        angle_offset = rng.uniform(0, math.tau)
        pts = []
        for j in range(sides):
            angle = angle_offset + j * math.tau / sides
            jitter = rng.uniform(0.68, 1.25)
            pts.append(
                (
                    x + math.cos(angle) * radius * jitter,
                    y + math.sin(angle) * radius * jitter,
                )
            )
        raw = rng.choice(palette)
        if len(raw) == 3:
            fill = (*raw, rng.randint(105, 220))
        else:
            fill = raw
        draw.polygon(pts, fill=fill)
        if radius > 13 and rng.random() > 0.55:
            hi = max(2, radius * 0.18)
            draw.ellipse((x - hi, y - hi, x + hi, y + hi), fill=(255, 249, 239, 70))
    base.alpha_composite(overlay)


def product_cutout():
    source = Image.open(PRODUCT_PATH).convert("RGBA").crop((105, 230, 920, 820))
    alpha_values = []
    for red, green, blue, _ in source.getdata():
        darkest = min(red, green, blue)
        saturation = max(red, green, blue) - darkest
        distance_from_white = 255 - darkest
        alpha = 0 if distance_from_white <= 3 else min(255, int((distance_from_white - 3) * 5.8))
        # Remove the neutral white/gray studio surround while preserving red product pixels
        # and the dark lid gap/button. RGB values are never repainted.
        if saturation < 18 and darkest > 125:
            alpha = 0
        alpha_values.append(alpha)
    alpha = Image.new("L", source.size)
    alpha.putdata(alpha_values)
    source.putalpha(alpha)
    return source


PRODUCT = product_cutout()


def place_product(base):
    x1, y1, x2, y2 = PRODUCT_ANCHOR
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((x1 + 95, y2 - 118, x2 - 15, y2 - 34), fill=(22, 18, 16, 62))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    base.alpha_composite(shadow)
    fitted = ImageOps.contain(
        PRODUCT, (x2 - x1, y2 - y1), method=Image.Resampling.LANCZOS
    )
    x = x1 + (x2 - x1 - fitted.width) // 2
    y = y1 + (y2 - y1 - fitted.height) // 2
    base.alpha_composite(fitted, (x, y))


def paste_material_macro(base, box):
    source = Image.open(PRODUCT_PATH).convert("RGB")
    # Exact crop from the front ceramic body; enlargement only, no recoloring or invented texture.
    detail = source.crop((255, 430, 470, 660))
    w, h = box[2] - box[0], box[3] - box[1]
    detail = ImageOps.fit(detail, (w, h), method=Image.Resampling.LANCZOS)

    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    # A low asymmetric arch echoes the lid without becoming a circular grid.
    md.rounded_rectangle((0, 72, w, h), radius=74, fill=255)
    md.ellipse((-25, 0, w + 75, 205), fill=255)
    rgba = detail.convert("RGBA")
    rgba.putalpha(mask)
    base.alpha_composite(rgba, (box[0], box[1]))


def new_canvas(color):
    return Image.new("RGBA", CANVAS, color)


def render_hero():
    base = new_canvas(CREAM)
    draw = ImageDraw.Draw(base)

    # Proprietary "slow-breath" ribbons: open, asymmetric, and tapered.
    tapered_arc(
        base,
        ((-260, 1505), (205, 815), (795, 500), (1630, 735)),
        (182, 83, 67, 255),
        225,
        46,
    )
    fine_arc(
        base,
        ((-90, 1670), (320, 1050), (900, 610), (1580, 895)),
        (113, 54, 46, 190),
        13,
    )
    fine_arc(
        base,
        ((210, 1900), (300, 1240), (785, 780), (1510, 855)),
        (127, 139, 96, 190),
        9,
    )
    granule_cluster(
        base,
        (1150, 650),
        (245, 150),
        105,
        [(182, 83, 67), (113, 54, 46), (216, 199, 170), (127, 139, 96)],
        101,
        (3, 18),
    )
    granule_cluster(
        base,
        (330, 1280),
        (150, 210),
        38,
        [(182, 83, 67), (216, 199, 170)],
        102,
        (4, 12),
    )

    label(draw, (94, 92), "陶土红香薰机", sans(31, True), CHARCOAL)
    label(draw, (94, 245), "让香气", sans(76), DEEP_CLAY)
    label(draw, (86, 358), "慢下来", serif(174, True), CHARCOAL)

    # Direction C's sequence is preserved; only its geometry has changed.
    sequence_y = 1650
    for index, copy, color in [
        ("01", "低噪运行", CHARCOAL),
        ("02", "定时关闭", OLIVE),
        ("03", "陶土触感", CLAY),
    ]:
        draw.ellipse((95, sequence_y + 5, 117, sequence_y + 27), fill=color)
        label(draw, (138, sequence_y), index, sans(25, True), color)
        label(draw, (198, sequence_y), copy, sans(25), CHARCOAL)
        sequence_y += 74

    place_product(base)
    return base


def render_low_noise():
    base = new_canvas(CHARCOAL)
    draw = ImageDraw.Draw(base)

    tapered_arc(
        base,
        ((-290, 1440), (250, 970), (920, 1235), (1690, 630)),
        (182, 83, 67, 255),
        250,
        42,
    )
    fine_arc(
        base,
        ((-160, 1590), (310, 1110), (870, 1330), (1590, 840)),
        (216, 199, 170, 210),
        12,
    )
    fine_arc(
        base,
        ((20, 1760), (420, 1390), (1060, 1470), (1520, 1090)),
        (127, 139, 96, 205),
        7,
    )
    granule_cluster(
        base,
        (405, 1125),
        (250, 170),
        120,
        [(182, 83, 67), (216, 199, 170), (127, 139, 96)],
        201,
        (3, 17),
    )
    granule_cluster(
        base,
        (1260, 720),
        (195, 135),
        54,
        [(182, 83, 67), (216, 199, 170)],
        202,
        (3, 12),
    )

    label(draw, (92, 100), "01", sans(190, True), CLAY)
    label(draw, (94, 355), "低噪运行", serif(112, True), PAPER)
    draw.line((98, 520, 540, 520), fill=OAT, width=4)
    label(draw, (97, 1735), "让香气慢下来", sans(31), OAT)

    place_product(base)
    return base


def render_timer_touch():
    base = new_canvas("#E8DCC9")
    draw = ImageDraw.Draw(base)

    tapered_arc(
        base,
        ((-270, 830), (320, 45), (1120, 520), (1650, 175)),
        (127, 139, 96, 238),
        190,
        34,
    )
    tapered_arc(
        base,
        ((-240, 1830), (250, 1380), (810, 1670), (1600, 1090)),
        (113, 54, 46, 255),
        92,
        210,
    )
    fine_arc(
        base,
        ((-50, 960), (380, 430), (1030, 715), (1540, 440)),
        (182, 83, 67, 220),
        12,
    )
    granule_cluster(
        base,
        (460, 710),
        (260, 170),
        102,
        [(182, 83, 67), (113, 54, 46), (127, 139, 96), (255, 249, 239)],
        301,
        (3, 17),
    )
    granule_cluster(
        base,
        (380, 1355),
        (190, 190),
        70,
        [(182, 83, 67), (113, 54, 46), (216, 199, 170)],
        302,
        (4, 19),
    )

    label(draw, (92, 84), "02", sans(150, True), DEEP_CLAY)
    label(draw, (94, 285), "定时关闭", serif(92, True), CHARCOAL)
    label(draw, (92, 640), "03", sans(118, True), OLIVE)
    label(draw, (94, 800), "陶土触感", serif(90, True), CHARCOAL)

    paste_material_macro(base, (88, 1040, 565, 1395))
    label(draw, (95, 1735), "让香气慢下来", sans(31), DEEP_CLAY)

    place_product(base)
    return base


hero = render_hero()
low_noise = render_low_noise()
timer_touch = render_timer_touch()

outputs = {
    "hero-quiet-sequence-clay-drift.png": hero,
    "selling-point-01-low-noise.png": low_noise,
    "selling-point-02-timer-tactility.png": timer_touch,
}
for name, image in outputs.items():
    image.convert("RGB").save(ROOT / name, optimize=True)

preview = Image.new("RGB", (CANVAS[0], CANVAS[1] * 3), CREAM)
preview.paste(hero.convert("RGB"), (0, 0))
preview.paste(low_noise.convert("RGB"), (0, CANVAS[1]))
preview.paste(timer_touch.convert("RGB"), (0, CANVAS[1] * 2))
preview.save(ROOT / "detail-page-scroll-preview.png", optimize=True)

print("Rendered:")
for name in [*outputs.keys(), "detail-page-scroll-preview.png"]:
    print(ROOT / name)
