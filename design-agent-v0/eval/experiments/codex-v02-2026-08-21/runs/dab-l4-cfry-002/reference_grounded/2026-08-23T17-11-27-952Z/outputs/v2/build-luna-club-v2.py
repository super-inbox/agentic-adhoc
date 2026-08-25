from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs" / "v1"
OUT = ROOT / "outputs" / "v2"

WHITE_EXPANSION_MM = 0.2
WHITE_STROKE_MM = WHITE_EXPANSION_MM * 2
ARTBOARD_WIDTH_MM = 160.0
ARTBOARD_HEIGHT_MM = 100.0
RASTER_DPI = 600
SUPERSAMPLE_DPI = 1200


def svg_root(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def first_path(root: ET.Element, group_id: str) -> ET.Element:
    ns = {"s": "http://www.w3.org/2000/svg"}
    group = root.find(f".//s:g[@id='{group_id}']", ns)
    if group is None:
        raise RuntimeError(f"Missing SVG group: {group_id}")
    path = group.find("s:path", ns)
    if path is None:
        raise RuntimeError(f"Missing path in SVG group: {group_id}")
    return path


def parse_points(path_d: str) -> list[tuple[float, float]]:
    values = [float(value) for value in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)", path_d)]
    if len(values) % 2:
        raise RuntimeError("Odd path coordinate count")
    return list(zip(values[0::2], values[1::2]))


def parse_translate(transform: str) -> tuple[float, float]:
    match = re.fullmatch(r"translate\(([-+\d.]+)(?:[ ,]+)([-+\d.]+)\)", transform.strip())
    if not match:
        raise RuntimeError(f"Unexpected transform: {transform}")
    return float(match.group(1)), float(match.group(2))


def to_svg() -> tuple[str, str, list[tuple[float, float]], list[tuple[float, float]]]:
    white_root = svg_root(V1 / "luna-club-white-ink-layer-v1.svg")
    cut_root = svg_root(V1 / "luna-club-cutline-master-v1.svg")
    white_path = first_path(white_root, "WHITE_INK")
    body_path = first_path(cut_root, "CUTLINE_BODY")

    white_d = white_path.attrib["d"]
    body_d = body_path.attrib["d"]
    white_points = parse_points(white_d)
    body_points = parse_points(body_d)
    if body_points[: len(white_points)] != white_points:
        raise RuntimeError("v1 white-ink path no longer registers to the body-cutline artwork arc")

    body_transform = body_path.attrib["transform"]
    tx, ty = parse_translate(body_transform)
    white_master_points = [(x + tx, y + ty) for x, y in white_points]
    body_master_points = [(x + tx, y + ty) for x, y in body_points]

    production_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="160mm" height="100mm" viewBox="0 0 160 100">
  <metadata>
    LUNA CLUB v2 WHITE_INK only; registered to outputs/v1/luna-club-cutline-master-v1.svg;
    center path unchanged from v1; white ink expands 0.2 mm outward by 0.4 mm centered stroke;
    insertion tab is not flood-filled; only the required 0.2 mm artwork-edge bleed enters its top edge;
    cutline, slot, and base geometry are not contained or modified here.
  </metadata>
  <g id="WHITE_INK_EXPANDED_0P2" fill="#ffffff" stroke="#ffffff" stroke-width="0.4" stroke-linejoin="round" stroke-linecap="round" paint-order="stroke fill">
    <path d="{white_d}" transform="{body_transform}"/>
  </g>
</svg>
'''
    (OUT / "luna-club-white-ink-layer-expanded-0p2-v2.svg").write_text(production_svg, encoding="utf-8")

    proof_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="160mm" height="100mm" viewBox="0 0 160 100">
  <metadata>Registration proof only; cyan band = v2 white ink +0.2 mm; magenta = unchanged v1 body cutline.</metadata>
  <rect width="160" height="100" fill="#222633"/>
  <g id="WHITE_INK_EXPANSION_PROOF" fill="#70e7ff" stroke="#70e7ff" stroke-width="0.4" stroke-linejoin="round" stroke-linecap="round" paint-order="stroke fill" opacity="0.95">
    <path d="{white_d}" transform="{body_transform}"/>
  </g>
  <g id="PRINT_ART_REFERENCE">
    <image x="5" y="5" width="84.271" height="87" preserveAspectRatio="none" xlink:href="../v1/luna-club-print-art-crop-v1.png"/>
  </g>
  <g id="UNCHANGED_V1_CUTLINE_REFERENCE" fill="none" stroke="#ff00ff" stroke-width="0.12">
    <path d="{body_d}" transform="{body_transform}"/>
  </g>
  <g font-family="Arial, sans-serif">
    <rect x="101" y="8" width="52" height="29" rx="2" fill="#ffffff" fill-opacity="0.94"/>
    <text x="106" y="16" font-size="4.2" font-weight="700" fill="#15203e">REGISTRATION PROOF</text>
    <text x="106" y="23" font-size="3.4" fill="#15203e">CYAN: WHITE INK +0.2 mm</text>
    <text x="106" y="29" font-size="3.4" fill="#15203e">MAGENTA: V1 CUTLINE</text>
    <text x="106" y="35" font-size="3.4" fill="#15203e">CENTERLINE SHIFT: 0.0 mm</text>
  </g>
</svg>
'''
    (OUT / "luna-club-white-ink-registration-proof-v2.svg").write_text(proof_svg, encoding="utf-8")
    return white_d, body_d, white_master_points, body_master_points


def render_raster(white_points: list[tuple[float, float]], body_points: list[tuple[float, float]]) -> None:
    hi_px_per_mm = SUPERSAMPLE_DPI / 25.4
    hi_size = (round(ARTBOARD_WIDTH_MM * hi_px_per_mm), round(ARTBOARD_HEIGHT_MM * hi_px_per_mm))
    hi_mask = Image.new("L", hi_size, 0)
    mask_draw = ImageDraw.Draw(hi_mask)
    white_polygon = [(round(x * hi_px_per_mm), round(y * hi_px_per_mm)) for x, y in white_points]
    stroke_px = round(WHITE_STROKE_MM * hi_px_per_mm)
    mask_draw.polygon(white_polygon, fill=255)
    mask_draw.line(white_polygon + [white_polygon[0]], fill=255, width=stroke_px, joint="curve")

    out_size = (round(ARTBOARD_WIDTH_MM * RASTER_DPI / 25.4), round(ARTBOARD_HEIGHT_MM * RASTER_DPI / 25.4))
    mask = hi_mask.resize(out_size, Image.Resampling.LANCZOS)
    rgba = Image.new("RGBA", out_size, (255, 255, 255, 0))
    rgba.putalpha(mask)
    rgba.save(OUT / "luna-club-white-ink-mask-expanded-0p2-v2.png", dpi=(RASTER_DPI, RASTER_DPI), optimize=True)

    proof_scale = 10
    proof = Image.new("RGB", (round(ARTBOARD_WIDTH_MM * proof_scale), round(ARTBOARD_HEIGHT_MM * proof_scale)), "#222633")
    proof_draw = ImageDraw.Draw(proof, "RGBA")
    expanded_poly = [(round(x * proof_scale), round(y * proof_scale)) for x, y in white_points]
    expanded_stroke = max(1, round(WHITE_STROKE_MM * proof_scale))
    proof_draw.polygon(expanded_poly, fill=(112, 231, 255, 235))
    proof_draw.line(expanded_poly + [expanded_poly[0]], fill=(112, 231, 255, 235), width=expanded_stroke, joint="curve")

    art = Image.open(V1 / "luna-club-print-art-crop-v1.png").convert("RGBA")
    art = art.resize((round(84.271 * proof_scale), round(87 * proof_scale)), Image.Resampling.LANCZOS)
    proof.paste(art, (round(5 * proof_scale), round(5 * proof_scale)), art)

    body_poly = [(round(x * proof_scale), round(y * proof_scale)) for x, y in body_points]
    proof_draw.line(body_poly + [body_poly[0]], fill=(255, 0, 255, 255), width=2, joint="curve")
    proof_draw.rounded_rectangle((1010, 80, 1530, 370), radius=20, fill=(255, 255, 255, 242))
    title_font = ImageFont.load_default(size=26)
    note_font = ImageFont.load_default(size=19)
    proof_draw.text((1060, 125), "REGISTRATION PROOF", fill="#15203e", font=title_font)
    proof_draw.text((1060, 205), "CYAN: WHITE INK +0.2 mm", fill="#15203e", font=note_font)
    proof_draw.text((1060, 255), "MAGENTA: V1 CUTLINE", fill="#15203e", font=note_font)
    proof_draw.text((1060, 305), "CENTERLINE SHIFT: 0.0 mm", fill="#15203e", font=note_font)
    proof.save(OUT / "luna-club-white-ink-registration-proof-v2.png", optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _, _, white_points, body_points = to_svg()
    render_raster(white_points, body_points)
    print(f"white_expansion_mm={WHITE_EXPANSION_MM:.3f}")
    print(f"stroke_width_mm={WHITE_STROKE_MM:.3f}")
    print("registration_centerline_shift_mm=0.000")
    print(f"raster_dpi={RASTER_DPI}")


if __name__ == "__main__":
    main()
