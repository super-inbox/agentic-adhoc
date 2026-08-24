from pathlib import Path
import hashlib
import math
import random

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PRODUCT_PATH = ROOT / "product-reference-exact.png"

SCALE = 2
HERO_SIZE = (1440, 1800)
MODULE_SIZE = (1440, 1200)

# Locked from the selected v0 Territory C preview:
# product cutout center (1380, 536.5) within preview (1216, 250, 512, 490).
HERO_PRODUCT_ANCHOR_NORMALIZED = (0.3203125, 0.5846938776)

PAPER = "#F7F3E9"
WARM = "#F3EEDF"
CANVAS = "#E8E1D4"
INK = "#2E2F2C"
MUTED = "#74766F"
RULE = "#C8C2B6"
CLAY = "#B85B49"
CLAY_DARK = "#914537"
CLAY_LIGHT = "#C97B68"
SAGE = "#8B9872"
BLUE = "#B8D1D6"
SAND = "#DED2BC"

CN_MED = "/System/Library/Fonts/STHeiti Medium.ttc"
CN_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"
LATIN = "/System/Library/Fonts/Supplemental/Arial.ttf"


def sc(value):
    return int(round(value * SCALE))


def scaled_points(points):
    return [(sc(x), sc(y)) for x, y in points]


def cubic(p0, p1, p2, p3, steps=120):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


class Canvas:
    def __init__(self, width, height, fill):
        self.width = width
        self.height = height
        self.image = Image.new("RGBA", (sc(width), sc(height)), fill)
        self.draw = ImageDraw.Draw(self.image, "RGBA")

    def rect(self, box, fill=None, outline=None, width=1):
        self.draw.rectangle(tuple(sc(v) for v in box), fill=fill, outline=outline, width=sc(width))

    def line(self, points, fill, width, joint="curve"):
        self.draw.line(scaled_points(points), fill=fill, width=sc(width), joint=joint)

    def polygon(self, points, fill):
        self.draw.polygon(scaled_points(points), fill=fill)

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.draw.ellipse(tuple(sc(v) for v in box), fill=fill, outline=outline, width=sc(width))

    def text(self, xy, text, size, fill=INK, medium=False, latin=False, anchor=None):
        path = LATIN if latin else (CN_MED if medium else CN_LIGHT)
        fnt = ImageFont.truetype(path, size=sc(size))
        self.draw.text((sc(xy[0]), sc(xy[1])), text, font=fnt, fill=fill, anchor=anchor)

    def finish(self):
        return self.image.convert("RGB").resize((self.width, self.height), Image.Resampling.LANCZOS)


def product_cutout():
    source = Image.open(PRODUCT_PATH).convert("RGBA")
    crop = source.crop((155, 248, 869, 823))
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            r, g, b, a = pixels[x, y]
            whiteness = min(r, g, b)
            if whiteness >= 250:
                pixels[x, y] = (r, g, b, 0)
            elif whiteness > 238:
                pixels[x, y] = (r, g, b, int((250 - whiteness) / 12 * a))
    return crop


def paste_cutout_center(canvas, cutout, center, max_size):
    scaled = cutout.copy()
    scaled.thumbnail((sc(max_size[0]), sc(max_size[1])), Image.Resampling.LANCZOS)
    x = sc(center[0]) - scaled.width // 2
    y = sc(center[1]) - scaled.height // 2
    canvas.image.alpha_composite(scaled, (x, y))


def fill_breath_ribbon(canvas, outer, inner, fill):
    outer_pts = cubic(*outer, steps=150)
    inner_pts = cubic(*inner, steps=150)
    canvas.polygon(outer_pts + list(reversed(inner_pts)), fill)


def draw_curve(canvas, control, fill, width):
    canvas.line(cubic(*control, steps=160), fill=fill, width=width)


def irregular_particle(canvas, cx, cy, radius, color, rng):
    vertices = rng.randint(5, 8)
    rotation = rng.random() * math.tau
    points = []
    for i in range(vertices):
        angle = rotation + i / vertices * math.tau
        rr = radius * rng.uniform(0.58, 1.18)
        points.append((cx + math.cos(angle) * rr, cy + math.sin(angle) * rr))
    canvas.polygon(points, color)


def particles_along_curve(canvas, control, count, spread, seed, palette, radius_range=(2, 11), fade_to_end=False):
    rng = random.Random(seed)
    path = cubic(*control, steps=500)
    for i in range(count):
        progress = rng.random()
        if fade_to_end:
            progress = 1 - (1 - progress) ** 1.8
        px, py = path[int(progress * (len(path) - 1))]
        local_spread = spread * (1.05 - progress * 0.45 if fade_to_end else 1)
        cx = px + rng.gauss(0, local_spread)
        cy = py + rng.gauss(0, local_spread * 0.62)
        radius = rng.uniform(*radius_range) * (1.0 - progress * 0.42 if fade_to_end else 1)
        irregular_particle(canvas, cx, cy, max(radius, 1.4), rng.choice(palette), rng)


def masked_material_crop(source, size):
    # Exact source pixels, tightly cropped to the terracotta body and resized only.
    crop = source.crop((275, 430, 750, 620)).convert("RGB")
    return crop.resize((sc(size[0]), sc(size[1])), Image.Resampling.LANCZOS).convert("RGBA")


def render_hero(cutout):
    w, h = HERO_SIZE
    c = Canvas(w, h, PAPER)
    c.rect((0, 0, w, 170), fill=BLUE)
    c.text((72, 78), "QUIET / AROMA / 01", 20, medium=True)
    c.text((1368, 78), "DIRECTION 03", 18, fill=MUTED, latin=True, anchor="ra")

    # Bespoke non-circular breath ribbon: unequal Bezier boundaries, no grid or rings.
    fill_breath_ribbon(
        c,
        ((-210, 650), (220, 135), (1030, 535), (1525, 150)),
        ((-145, 790), (360, 335), (1005, 710), (1510, 355)),
        CLAY,
    )
    draw_curve(c, ((-100, 835), (390, 430), (1010, 790), (1495, 440)), SAGE, 12)
    particles_along_curve(
        c,
        ((60, 720), (380, 470), (700, 870), (1010, 710)),
        count=118,
        spread=62,
        seed=303,
        palette=(CLAY_DARK, CLAY_LIGHT, SAND, SAGE),
        radius_range=(2.0, 10.5),
        fade_to_end=True,
    )

    product_center = (w * HERO_PRODUCT_ANCHOR_NORMALIZED[0], h * HERO_PRODUCT_ANCHOR_NORMALIZED[1])
    paste_cutout_center(c, cutout, product_center, (720, 590))

    c.text((850, 874), "让香气", 108, medium=True)
    c.text((850, 1008), "慢下来", 108, medium=True)
    c.line(((850, 1194), (1338, 1194)), INK, 3)
    c.text((850, 1248), "低噪运行   /   定时关闭   /   陶土触感", 28, medium=True)
    c.text((850, 1320), "03", 18, fill=MUTED, latin=True)

    # A small continuation at the lower edge preserves the scroll rhythm without a borrowed grid.
    draw_curve(c, ((1020, 1555), (1170, 1450), (1300, 1620), (1500, 1480)), CLAY, 26)
    particles_along_curve(
        c,
        ((1040, 1590), (1180, 1510), (1320, 1690), (1470, 1570)),
        count=34,
        spread=24,
        seed=313,
        palette=(CLAY_DARK, CLAY_LIGHT, SAGE),
        radius_range=(2, 7),
        fade_to_end=True,
    )
    c.rect((1398, 1625, 1440, 1800), fill=BLUE)
    c.line(((72, 1718), (1332, 1718)), RULE, 2)
    return c.finish()


def render_low_noise():
    w, h = MODULE_SIZE
    c = Canvas(w, h, WARM)
    c.rect((0, 0, w, 94), fill=BLUE)
    c.text((72, 58), "SELLING POINT / 01", 18, medium=True)
    c.text((1368, 58), "QUIET FIELD", 17, fill=MUTED, latin=True, anchor="ra")

    c.text((730, 252), "低噪运行", 104, medium=True)
    c.line(((734, 410), (1325, 410)), INK, 3)
    c.text((734, 466), "01", 18, fill=MUTED, latin=True)

    # Dense-to-sparse earthen sweep replaces the earlier waveform and clock-like track.
    fill_breath_ribbon(
        c,
        ((-220, 940), (190, 590), (680, 1115), (1500, 355)),
        ((-185, 1110), (330, 790), (720, 1240), (1515, 635)),
        CLAY,
    )
    draw_curve(c, ((-80, 875), (260, 610), (690, 1035), (1380, 500)), SAGE, 10)
    particles_along_curve(
        c,
        ((60, 885), (340, 680), (700, 990), (1260, 565)),
        count=146,
        spread=72,
        seed=403,
        palette=(CLAY_DARK, CLAY_LIGHT, SAND, SAGE),
        radius_range=(2.2, 11.5),
        fade_to_end=True,
    )
    c.text((72, 1082), "让香气慢下来", 24, medium=True, fill=INK)
    return c.finish()


def render_timer_clay(source):
    w, h = MODULE_SIZE
    c = Canvas(w, h, PAPER)
    c.rect((0, 0, 50, h), fill=BLUE)
    c.text((92, 82), "SELLING POINT / 02", 18, medium=True)
    c.text((1368, 82), "EARTHEN PAUSE", 17, fill=MUTED, latin=True, anchor="ra")

    # Three unequal open arcs share a direction but not a center, radius or circular outline.
    draw_curve(c, ((300, 1145), (420, 585), (1100, 855), (1495, 290)), CLAY, 68)
    draw_curve(c, ((500, 1160), (620, 720), (1110, 1015), (1465, 595)), SAGE, 20)
    draw_curve(c, ((690, 1170), (790, 860), (1190, 1100), (1430, 850)), INK, 4)

    particles_along_curve(
        c,
        ((1015, 585), (1190, 470), (1360, 430), (1490, 320)),
        count=58,
        spread=42,
        seed=503,
        palette=(CLAY_DARK, CLAY_LIGHT, SAND, SAGE),
        radius_range=(2.0, 10.0),
        fade_to_end=False,
    )

    c.text((760, 214), "定时关闭", 104, medium=True)
    c.line(((764, 372), (1328, 372)), INK, 3)
    c.text((764, 434), "陶土触感", 38, medium=True)
    c.text((764, 506), "02", 18, fill=MUTED, latin=True)

    crop_size = (690, 276)
    crop = masked_material_crop(source, crop_size)
    c.image.alpha_composite(crop, (sc(90), sc(770)))
    c.rect((90, 770, 780, 1046), outline=PAPER, width=5)
    c.line(((90, 1082), (780, 1082)), INK, 3)
    particles_along_curve(
        c,
        ((675, 840), (800, 790), (880, 940), (1005, 865)),
        count=36,
        spread=28,
        seed=513,
        palette=(CLAY_DARK, CLAY_LIGHT, SAND),
        radius_range=(2, 8),
        fade_to_end=True,
    )
    return c.finish()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = Image.open(PRODUCT_PATH).convert("RGB")
    cutout = product_cutout()

    hero = render_hero(cutout)
    module_1 = render_low_noise()
    module_2 = render_timer_clay(source)

    hero_path = ROOT / "hero-direction-03-clay-arc.png"
    module_1_path = ROOT / "module-01-low-noise.png"
    module_2_path = ROOT / "module-02-timer-clay-touch.png"
    hero.save(hero_path, optimize=True)
    module_1.save(module_1_path, optimize=True)
    module_2.save(module_2_path, optimize=True)

    gap = 12
    combined = Image.new("RGB", (HERO_SIZE[0], HERO_SIZE[1] + MODULE_SIZE[1] * 2 + gap * 2), CANVAS)
    combined.paste(hero, (0, 0))
    combined.paste(module_1, (0, HERO_SIZE[1] + gap))
    combined.paste(module_2, (0, HERO_SIZE[1] + MODULE_SIZE[1] + gap * 2))
    combined_path = ROOT / "detail-page-composite.png"
    combined.save(combined_path, optimize=True)

    print(f"product_sha256={sha256(PRODUCT_PATH)}")
    print(f"hero_product_anchor_normalized={HERO_PRODUCT_ANCHOR_NORMALIZED}")
    for path in (hero_path, module_1_path, module_2_path, combined_path):
        print(path)


if __name__ == "__main__":
    main()
