from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from shutil import copy2
from math import hypot

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v1"
SOURCE = ROOT / "inputs" / "01-ip_artwork.png"

ART_VISIBLE_HEIGHT_MM = 87.0
TAB_HEIGHT_MM = 3.0
ASSEMBLED_HEIGHT_MM = 90.0
TAB_WIDTH_MM = 7.0
SLOT_LENGTH_MM = 7.2
SLOT_WIDTH_MM = 3.2
SLOT_WIDTH_TOL_MM = 0.1
BASE_WIDTH_MM = 55.0
BASE_DEPTH_MM = 25.0
BASE_RADIUS_MM = 3.0
ACRYLIC_THICKNESS_MM = 3.0


def fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    x1, y1 = points[0]
    x2, y2 = points[-1]
    dx, dy = x2 - x1, y2 - y1
    denom = hypot(dx, dy)
    max_distance = -1.0
    max_index = 0
    for index, (x, y) in enumerate(points[1:-1], start=1):
        if denom == 0:
            distance = hypot(x - x1, y - y1)
        else:
            distance = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / denom
        if distance > max_distance:
            max_distance = distance
            max_index = index
    if max_distance > epsilon:
        left = rdp(points[: max_index + 1], epsilon)
        right = rdp(points[max_index:], epsilon)
        return left[:-1] + right
    return [points[0], points[-1]]


def trace_pixel_outline(mask: np.ndarray) -> list[tuple[int, int]]:
    height, width = mask.shape
    adjacency: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for y in range(height):
        for x in range(width):
            if not mask[y, x]:
                continue
            if y == 0 or not mask[y - 1, x]:
                adjacency[(x + 1, y)].append((x, y))
            if x == 0 or not mask[y, x - 1]:
                adjacency[(x, y)].append((x, y + 1))
            if y == height - 1 or not mask[y + 1, x]:
                adjacency[(x, y + 1)].append((x + 1, y + 1))
            if x == width - 1 or not mask[y, x + 1]:
                adjacency[(x + 1, y + 1)].append((x + 1, y))

    starts = list(adjacency)
    if not starts or any(len(adjacency[start]) != 1 for start in starts):
        raise RuntimeError("Unexpected outline topology")
    start = min(starts, key=lambda point: (point[1], point[0]))
    loop = [start]
    current = start
    for _ in range(sum(len(values) for values in adjacency.values()) + 1):
        current = adjacency[current][0]
        loop.append(current)
        if current == start:
            break
    if loop[-1] != start:
        raise RuntimeError("Outline did not close")

    points = loop[:-1]
    simplified: list[tuple[int, int]] = []
    for point in points:
        simplified.append(point)
        while len(simplified) >= 3:
            a, b, c = simplified[-3:]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            forward = (b[0] - a[0]) * (c[0] - b[0]) >= 0 and (b[1] - a[1]) * (c[1] - b[1]) >= 0
            if cross == 0 and forward:
                simplified.pop(-2)
            else:
                break
    return simplified


def path_d(points: list[tuple[float, float]]) -> str:
    commands = [f"M {fmt(points[0][0])},{fmt(points[0][1])}"]
    commands.extend(f"L {fmt(x)},{fmt(y)}" for x, y in points[1:])
    commands.append("Z")
    return " ".join(commands)


def dimension_line(x1: float, y1: float, x2: float, y2: float, label: str, text_dx: float = 0, text_dy: float = -2) -> str:
    return (
        f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}" '
        'stroke="#29375f" stroke-width="0.45" marker-start="url(#arrow)" marker-end="url(#arrow)"/>'
        f'<text x="{fmt((x1 + x2) / 2 + text_dx)}" y="{fmt((y1 + y2) / 2 + text_dy)}" '
        'font-size="4" text-anchor="middle" fill="#17213f">'
        f'{label}</text>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    alpha = np.asarray(source)[:, :, 3]
    ys, xs = np.nonzero(alpha > 128)
    xmin, ymin, xmax, ymax = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    crop = source.crop((xmin, ymin, xmax, ymax))
    crop.save(OUT / "luna-club-print-art-crop-v1.png", optimize=False)
    copy2(SOURCE, OUT / "luna-club-print-art-master-v1.png")

    crop_array = np.asarray(crop)
    white_mask = Image.new("RGBA", crop.size, (255, 255, 255, 0))
    white_mask.putalpha(Image.fromarray(crop_array[:, :, 3], mode="L"))
    white_mask.save(OUT / "luna-club-white-ink-mask-v1.png", optimize=False)
    white_proof = Image.new("RGB", crop.size, "#151515")
    white_fill = Image.new("RGB", crop.size, "#ffffff")
    white_proof.paste(white_fill, (0, 0), Image.fromarray(crop_array[:, :, 3], mode="L"))
    white_proof.save(OUT / "luna-club-white-ink-proof-v1.png", optimize=True)

    binary = crop_array[:, :, 3] > 128
    height_px, width_px = binary.shape
    mm_per_px = ART_VISIBLE_HEIGHT_MM / height_px
    body_width_mm = width_px * mm_per_px
    outline = trace_pixel_outline(binary)

    bottom_y = max(y for _, y in outline)
    bottom_indices = [index for index, (_, y) in enumerate(outline) if y == bottom_y]
    if len(bottom_indices) != 2:
        raise RuntimeError(f"Expected two bottom tangent points, found {len(bottom_indices)}")
    first, second = bottom_indices
    left_index, right_index = (first, second) if outline[first][0] < outline[second][0] else (second, first)
    left_point, right_point = outline[left_index], outline[right_index]

    if (left_index + 1) % len(outline) == right_index:
        outer_arc_px = outline[right_index:] + outline[: left_index + 1]
    elif (right_index + 1) % len(outline) == left_index:
        outer_arc_px = outline[right_index : left_index + 1]
    else:
        raise RuntimeError("Bottom tangent points are not adjacent")

    outer_arc_px = rdp([(float(x), float(y)) for x, y in outer_arc_px], 0.75)

    def to_mm(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return ((x - width_px / 2) * mm_per_px, y * mm_per_px)

    outer_arc_mm = [to_mm(point) for point in outer_arc_px]
    body_outline_mm = outer_arc_mm + [
        (-TAB_WIDTH_MM / 2, ART_VISIBLE_HEIGHT_MM),
        (-TAB_WIDTH_MM / 2, ASSEMBLED_HEIGHT_MM),
        (TAB_WIDTH_MM / 2, ASSEMBLED_HEIGHT_MM),
        (TAB_WIDTH_MM / 2, ART_VISIBLE_HEIGHT_MM),
    ]
    art_outline_mm = outer_arc_mm
    body_d = path_d(body_outline_mm)
    art_d = path_d(art_outline_mm)

    cutline_master = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="160mm" height="100mm" viewBox="0 0 160 100">
  <metadata>
    LUNA CLUB v1; units mm; body material 3.0 mm clear acrylic; base 55x25 R3;
    slot 7.2x3.2 mm centered; slot width tolerance +/-0.1 mm; no hanging hole.
  </metadata>
  <g id="CUTLINE_BODY" fill="none" stroke="#ff00ff" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <path d="{body_d}" transform="translate({fmt(5 + body_width_mm / 2)},5)"/>
  </g>
  <g id="CUTLINE_BASE" fill="none" stroke="#ff00ff" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <rect x="100" y="5" width="55" height="25" rx="3" ry="3"/>
  </g>
  <g id="SLOT_CUT" fill="none" stroke="#00aeea" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <rect x="{fmt(100 + (BASE_WIDTH_MM - SLOT_LENGTH_MM) / 2)}" y="{fmt(5 + (BASE_DEPTH_MM - SLOT_WIDTH_MM) / 2)}" width="{fmt(SLOT_LENGTH_MM)}" height="{fmt(SLOT_WIDTH_MM)}"/>
  </g>
</svg>
'''
    (OUT / "luna-club-cutline-master-v1.svg").write_text(cutline_master, encoding="utf-8")

    body_cutline = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(body_width_mm + 4)}mm" height="94mm" viewBox="0 0 {fmt(body_width_mm + 4)} 94">
  <metadata>BODY CUTLINE; 3.0 mm clear acrylic; total piece height 90.0 mm; centered 7.0x3.0 mm tab; no hanging hole.</metadata>
  <g id="CUTLINE_BODY" fill="none" stroke="#ff00ff" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <path d="{body_d}" transform="translate({fmt(2 + body_width_mm / 2)},2)"/>
  </g>
</svg>
'''
    (OUT / "luna-club-body-cutline-v1.svg").write_text(body_cutline, encoding="utf-8")

    base_cutline = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="59mm" height="29mm" viewBox="0 0 59 29">
  <metadata>BASE CUTLINE; 3.0 mm clear acrylic; 55x25 mm; corners R3; centered slot 7.2x3.2 mm; slot width tolerance +/-0.1 mm; no hanging hole.</metadata>
  <g id="CUTLINE_BASE" fill="none" stroke="#ff00ff" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <rect x="2" y="2" width="55" height="25" rx="3" ry="3"/>
  </g>
  <g id="SLOT_CUT" fill="none" stroke="#00aeea" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <rect x="{fmt(2 + (BASE_WIDTH_MM - SLOT_LENGTH_MM) / 2)}" y="{fmt(2 + (BASE_DEPTH_MM - SLOT_WIDTH_MM) / 2)}" width="{fmt(SLOT_LENGTH_MM)}" height="{fmt(SLOT_WIDTH_MM)}"/>
  </g>
</svg>
'''
    (OUT / "luna-club-base-cutline-v1.svg").write_text(base_cutline, encoding="utf-8")

    print_layout = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{fmt(body_width_mm)}mm" height="90mm" viewBox="0 0 {fmt(body_width_mm)} 90">
  <metadata>PRINT ART uses the approved master without redrawing. Artwork height 87.0 mm; clear insertion tab below; cutline shown in CUTLINE_PREVIEW.</metadata>
  <g id="PRINT_ART">
    <image x="0" y="0" width="{fmt(body_width_mm)}" height="87" preserveAspectRatio="none" xlink:href="luna-club-print-art-crop-v1.png"/>
  </g>
  <g id="CUTLINE_PREVIEW" fill="none" stroke="#ff00ff" stroke-width="0.1" vector-effect="non-scaling-stroke">
    <path d="{body_d}" transform="translate({fmt(body_width_mm / 2)},0)"/>
  </g>
</svg>
'''
    (OUT / "luna-club-print-layout-v1.svg").write_text(print_layout, encoding="utf-8")

    white_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(body_width_mm)}mm" height="87mm" viewBox="0 0 {fmt(body_width_mm)} 87">
  <metadata>WHITE_INK full underprint beneath the approved color-art silhouette; no white ink on the clear insertion tab.</metadata>
  <g id="WHITE_INK" fill="#ffffff" stroke="none">
    <path d="{art_d}" transform="translate({fmt(body_width_mm / 2)},0)"/>
  </g>
</svg>
'''
    (OUT / "luna-club-white-ink-layer-v1.svg").write_text(white_svg, encoding="utf-8")

    front_center_x, front_top_y = 72.0, 36.0
    side_center_x = 178.0
    top_x, top_y = 235.0, 50.0
    sheet = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="420mm" height="297mm" viewBox="0 0 420 297">
  <defs>
    <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse"><path d="M 6 0 L 0 3 L 6 6 Z" fill="#29375f"/></marker>
  </defs>
  <rect width="420" height="297" fill="#f7f8fc"/>
  <rect width="420" height="23" fill="#111a42"/>
  <text x="15" y="15" font-family="Arial, sans-serif" font-size="8" font-weight="700" fill="#ffffff">LUNA CLUB ACRYLIC STANDEE · V1 TECHNICAL SHEET</text>
  <text x="405" y="15" font-family="Arial, sans-serif" font-size="4.5" text-anchor="end" fill="#ffeb7b">FACTORY REVIEW DRAFT · NOT FINAL RELEASE</text>
  <g font-family="Arial, sans-serif">
    <text x="30" y="32" font-size="5" font-weight="700" fill="#17213f">FRONT VIEW · SCALE 1:1</text>
    <image x="{fmt(front_center_x - body_width_mm / 2)}" y="{fmt(front_top_y)}" width="{fmt(body_width_mm)}" height="87" preserveAspectRatio="none" xlink:href="luna-club-print-art-crop-v1.png"/>
    <path d="{body_d}" transform="translate({fmt(front_center_x)},{fmt(front_top_y)})" fill="none" stroke="#ff00ff" stroke-width="0.25"/>
    <rect x="{fmt(front_center_x - BASE_WIDTH_MM / 2)}" y="{fmt(front_top_y + ART_VISIBLE_HEIGHT_MM)}" width="55" height="3" rx="0.8" fill="#dff8ff" fill-opacity="0.75" stroke="#319bb5" stroke-width="0.35"/>
    {dimension_line(18, front_top_y, 18, front_top_y + ASSEMBLED_HEIGHT_MM, '90.0 OVERALL', text_dx=-7, text_dy=1)}
    {dimension_line(front_center_x - body_width_mm / 2, 136, front_center_x + body_width_mm / 2, 136, f'{body_width_mm:.1f} ART WIDTH')}
    {dimension_line(front_center_x - BASE_WIDTH_MM / 2, 146, front_center_x + BASE_WIDTH_MM / 2, 146, '55.0 BASE')}

    <text x="145" y="32" font-size="5" font-weight="700" fill="#17213f">SIDE VIEW · SCALE 1:1</text>
    <rect x="{fmt(side_center_x - ACRYLIC_THICKNESS_MM / 2)}" y="{fmt(front_top_y)}" width="3" height="90" fill="#dff8ff" fill-opacity="0.8" stroke="#319bb5" stroke-width="0.35"/>
    <rect x="{fmt(side_center_x - BASE_DEPTH_MM / 2)}" y="{fmt(front_top_y + ART_VISIBLE_HEIGHT_MM)}" width="25" height="3" rx="0.8" fill="#dff8ff" fill-opacity="0.8" stroke="#319bb5" stroke-width="0.35"/>
    {dimension_line(side_center_x - BASE_DEPTH_MM / 2, 140, side_center_x + BASE_DEPTH_MM / 2, 140, '25.0 BASE DEPTH')}
    <text x="{fmt(side_center_x + 8)}" y="70" font-size="4" fill="#17213f">3.0 BODY</text>
    <text x="{fmt(side_center_x + 15)}" y="122" font-size="4" fill="#17213f">3.0 BASE</text>

    <text x="235" y="39" font-size="5" font-weight="700" fill="#17213f">TOP VIEW · SCALE 1:1</text>
    <rect x="{fmt(top_x)}" y="{fmt(top_y)}" width="55" height="25" rx="3" fill="#e9fbff" stroke="#319bb5" stroke-width="0.45"/>
    <rect x="{fmt(top_x + (BASE_WIDTH_MM - SLOT_LENGTH_MM) / 2)}" y="{fmt(top_y + (BASE_DEPTH_MM - SLOT_WIDTH_MM) / 2)}" width="7.2" height="3.2" fill="none" stroke="#00aeea" stroke-width="0.5"/>
    {dimension_line(top_x, top_y + 34, top_x + BASE_WIDTH_MM, top_y + 34, '55.0')}
    {dimension_line(top_x + BASE_WIDTH_MM + 10, top_y, top_x + BASE_WIDTH_MM + 10, top_y + BASE_DEPTH_MM, '25.0', text_dx=7, text_dy=1)}
    <text x="{fmt(top_x + BASE_WIDTH_MM / 2)}" y="{fmt(top_y + 11)}" font-size="3.8" text-anchor="middle" fill="#17213f">SLOT 7.2 × 3.2</text>
    <text x="{fmt(top_x + BASE_WIDTH_MM / 2)}" y="{fmt(top_y + 17)}" font-size="3.8" text-anchor="middle" fill="#17213f">WIDTH TOL. ±0.1</text>
    <text x="{fmt(top_x + 3)}" y="{fmt(top_y - 3)}" font-size="3.8" fill="#17213f">4 × R3</text>

    <rect x="330" y="37" width="73" height="92" rx="3" fill="#ffffff" stroke="#d7dced"/>
    <text x="339" y="49" font-size="5" font-weight="700" fill="#17213f">CMF</text>
    <text x="339" y="61" font-size="4" fill="#17213f">MATERIAL</text><text x="339" y="67" font-size="3.7" fill="#4f5b78">Clear acrylic · 3.0 mm</text>
    <text x="339" y="79" font-size="4" fill="#17213f">COLOR</text><text x="339" y="85" font-size="3.7" fill="#4f5b78">Approved master artwork</text>
    <text x="339" y="97" font-size="4" fill="#17213f">WHITE INK</text><text x="339" y="103" font-size="3.7" fill="#4f5b78">Full silhouette underprint</text>
    <text x="339" y="115" font-size="4" fill="#17213f">FINISH</text><text x="339" y="121" font-size="3.7" fill="#4f5b78">Edge finish: not specified</text>

    <rect x="25" y="166" width="378" height="105" rx="4" fill="#ffffff" stroke="#d7dced"/>
    <text x="36" y="181" font-size="5.5" font-weight="700" fill="#17213f">PRODUCTION NOTES</text>
    <text x="36" y="195" font-size="4.2" fill="#17213f">01  Exact source master is included; print crop is unscaled within the production alpha boundary.</text>
    <text x="36" y="207" font-size="4.2" fill="#17213f">02  Body and base: 3.0 mm clear acrylic. Base: 55 × 25 mm, four corners R3.</text>
    <text x="36" y="219" font-size="4.2" fill="#17213f">03  Centered slot: 7.2 × 3.2 mm; 3.2 mm width tolerance ±0.1 mm. No hanging hole.</text>
    <text x="36" y="231" font-size="4.2" fill="#17213f">04  Slot length 7.2 mm and tab width 7.0 mm are design-defined from the artwork bottom connection; factory review required.</text>
    <text x="36" y="243" font-size="4.2" fill="#17213f">05  White ink: full artwork-silhouette underprint; clear tab remains unprinted.</text>
    <text x="36" y="255" font-size="4.2" fill="#17213f">06  Effective raster resolution at 87 mm art height: approximately 149 ppi; do not upscale or redraw without approval.</text>
  </g>
</svg>
'''
    (OUT / "luna-club-three-view-dimensioned-v1.svg").write_text(sheet, encoding="utf-8")

    # PNG review preview of the same core geometry. Production geometry remains in SVG.
    px_per_mm = 4
    canvas = Image.new("RGB", (420 * px_per_mm, 297 * px_per_mm), "#f7f8fc")
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.load_default(size=30)
    label_font = ImageFont.load_default(size=20)
    small_font = ImageFont.load_default(size=15)

    def p(value: float) -> int:
        return round(value * px_per_mm)

    draw.rectangle((0, 0, canvas.width, p(23)), fill="#111a42")
    draw.text((p(15), p(7)), "LUNA CLUB ACRYLIC STANDEE - V1 TECHNICAL SHEET", fill="white", font=title_font)
    draw.text((p(300), p(9)), "FACTORY REVIEW DRAFT", fill="#ffeb7b", font=label_font)

    art_preview = crop.resize((p(body_width_mm), p(ART_VISIBLE_HEIGHT_MM)), Image.Resampling.LANCZOS)
    canvas.paste(art_preview, (p(front_center_x - body_width_mm / 2), p(front_top_y)), art_preview)
    body_poly = [(p(front_center_x + x), p(front_top_y + y)) for x, y in body_outline_mm]
    draw.line(body_poly + [body_poly[0]], fill="#ff00ff", width=2, joint="curve")
    draw.rounded_rectangle((p(front_center_x - BASE_WIDTH_MM / 2), p(front_top_y + ART_VISIBLE_HEIGHT_MM), p(front_center_x + BASE_WIDTH_MM / 2), p(front_top_y + ASSEMBLED_HEIGHT_MM)), radius=3, fill="#dff8ff", outline="#319bb5", width=2)
    draw.text((p(30), p(29)), "FRONT VIEW 1:1", fill="#17213f", font=label_font)
    draw.text((p(28), p(139)), f"OVERALL 90.0 | ART W {body_width_mm:.1f} | BASE W 55.0", fill="#17213f", font=small_font)

    draw.text((p(145), p(29)), "SIDE VIEW 1:1", fill="#17213f", font=label_font)
    draw.rectangle((p(side_center_x - 1.5), p(front_top_y), p(side_center_x + 1.5), p(front_top_y + 90)), fill="#dff8ff", outline="#319bb5", width=2)
    draw.rounded_rectangle((p(side_center_x - 12.5), p(front_top_y + 87), p(side_center_x + 12.5), p(front_top_y + 90)), radius=3, fill="#dff8ff", outline="#319bb5", width=2)
    draw.text((p(151), p(139)), "BASE D 25.0 | BODY/BASE T 3.0", fill="#17213f", font=small_font)

    draw.text((p(top_x), p(40)), "TOP VIEW 1:1", fill="#17213f", font=label_font)
    draw.rounded_rectangle((p(top_x), p(top_y), p(top_x + 55), p(top_y + 25)), radius=p(3), fill="#e9fbff", outline="#319bb5", width=2)
    slot_x = top_x + (55 - SLOT_LENGTH_MM) / 2
    slot_y = top_y + (25 - SLOT_WIDTH_MM) / 2
    draw.rectangle((p(slot_x), p(slot_y), p(slot_x + SLOT_LENGTH_MM), p(slot_y + SLOT_WIDTH_MM)), outline="#00aeea", width=3)
    draw.text((p(top_x), p(80)), "55 x 25 | 4xR3 | SLOT 7.2 x 3.2 +/-0.1 WIDTH", fill="#17213f", font=small_font)

    draw.rounded_rectangle((p(330), p(37), p(403), p(129)), radius=10, fill="white", outline="#d7dced", width=2)
    cmf_lines = ["CMF", "Clear acrylic 3.0 mm", "Approved master colors", "Full white underprint", "No hanging hole", "Edge finish: OPEN"]
    for index, line in enumerate(cmf_lines):
        draw.text((p(337), p(47 + index * 13)), line, fill="#17213f" if index == 0 else "#4f5b78", font=label_font if index == 0 else small_font)

    draw.rounded_rectangle((p(25), p(166), p(403), p(271)), radius=12, fill="white", outline="#d7dced", width=2)
    notes = [
        "PRODUCTION NOTES",
        "1. Approved artwork preserved; no redraw or hanging hole.",
        "2. 3.0 mm clear acrylic; base 55 x 25 mm, four corners R3.",
        "3. Center slot 7.2 x 3.2 mm; width tolerance +/-0.1 mm.",
        "4. 7.2 slot length / 7.0 tab are design-defined; factory review required.",
        "5. Full white-ink silhouette underprint; clear tab unprinted.",
        "6. Effective source resolution at 87 mm art height: approx. 149 ppi.",
    ]
    for index, line in enumerate(notes):
        draw.text((p(35), p(178 + index * 13)), line, fill="#17213f" if index == 0 else "#4f5b78", font=label_font if index == 0 else small_font)
    canvas.save(OUT / "luna-club-three-view-dimensioned-v1.png", optimize=True)

    print(
        f"art_bbox_px={xmin},{ymin},{xmax},{ymax}\n"
        f"crop_px={width_px}x{height_px}\n"
        f"art_physical_mm={body_width_mm:.3f}x{ART_VISIBLE_HEIGHT_MM:.3f}\n"
        f"effective_ppi={height_px / (ART_VISIBLE_HEIGHT_MM / 25.4):.2f}\n"
        f"outline_vertices={len(body_outline_mm)}"
    )


if __name__ == "__main__":
    main()
