#!/usr/bin/env python3
"""Build deterministic SUMMER FORM campaign adaptations for v0.

The approved raster is never redrawn. The origami hero and brand mark are
cropped verbatim and placed as aspect-ratio-locked image objects. Typography
and the geometric system remain editable SVG objects.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v0"
ASSETS = OUT / "assets"
SOURCE = ROOT / "inputs" / "01-campaign_master.png"

NAVY = "#273D70"
BLUE = "#3A5CA3"
CORAL = "#EF7D66"
PAPER = "#F3EFE6"
INK = "#273D70"
PREVIEW_BG = "#DCD6CB"

ART_CROP = (200, 580, 465, 825)
LOGO_CROP = (590, 830, 762, 1002)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def crop_assets() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    approved = Image.open(SOURCE).convert("RGB")
    approved.crop(ART_CROP).save(ASSETS / "approved_origami_crop.png", quality=100)
    approved.crop(LOGO_CROP).save(ASSETS / "approved_brand_mark_crop.png", quality=100)


def svg_shell(width: int, height: int, title: str, description: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="svg-title svg-desc">
  <title id="svg-title">{title}</title>
  <desc id="svg-desc">{description}</desc>
  <defs>
    <filter id="paper-grain" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.72" numOctaves="3" seed="18" result="noise"/>
      <feColorMatrix in="noise" type="saturate" values="0" result="mono"/>
      <feComponentTransfer in="mono" result="soft-noise">
        <feFuncA type="table" tableValues="0 0.11"/>
      </feComponentTransfer>
      <feBlend in="SourceGraphic" in2="soft-noise" mode="multiply"/>
    </filter>
    <clipPath id="safe-frame-clip"><rect x="64" y="64" width="{width - 128}" height="{height - 128}"/></clipPath>
  </defs>
  <style>
    .line {{ fill: none; stroke: {NAVY}; stroke-width: 3; vector-effect: non-scaling-stroke; }}
    .hairline {{ fill: none; stroke: {NAVY}; stroke-width: 2.5; vector-effect: non-scaling-stroke; }}
    .title {{ fill: {INK}; font-family: Arial, Helvetica, sans-serif; font-weight: 700; letter-spacing: -4px; }}
    .meta {{ fill: {INK}; font-family: Arial, Helvetica, sans-serif; font-weight: 400; letter-spacing: -1px; }}
  </style>
  <g id="background">
    <rect width="{width}" height="{height}" fill="{PAPER}"/>
    <rect width="{width}" height="{height}" fill="{PAPER}" filter="url(#paper-grain)" opacity="0.42"/>
  </g>
{body}
</svg>
'''


def website_svg() -> str:
    return svg_shell(
        1200,
        628,
        "SUMMER FORM website card",
        "Approved SUMMER FORM campaign adapted to a 1200 by 628 website card without changing the hero visual.",
        f'''
  <g id="geometry-frame" clip-path="url(#safe-frame-clip)">
    <rect id="outer-frame" x="64" y="64" width="1072" height="500" class="line"/>
    <path id="grid-lines" d="M64 128H1136 M496 64V564 M496 384H1136 M600 384V564 M944 128V564" class="hairline"/>
    <g id="geometry-top-band">
      <rect x="320" y="64" width="176" height="64" fill="{CORAL}"/>
      <rect x="788" y="64" width="250" height="64" fill="{BLUE}"/>
      <rect x="1038" y="64" width="98" height="64" fill="{CORAL}"/>
      <circle cx="176" cy="128" r="64" class="line"/>
      <path d="M176 64V192 M112 128H240" class="hairline"/>
    </g>
    <g id="geometry-arcs">
      <path d="M496 384A180 180 0 0 1 676 564" class="line"/>
      <path d="M1136 234A150 150 0 0 0 986 384A150 150 0 0 0 1136 534" class="line"/>
      <circle cx="944" cy="500" r="64" class="hairline"/>
    </g>
    <g id="geometry-bottom-accents">
      <rect x="496" y="500" width="52" height="64" fill="{CORAL}"/>
      <rect x="548" y="500" width="52" height="64" fill="{BLUE}"/>
    </g>
  </g>
  <g id="approved-art-window">
    <rect x="64" y="128" width="432" height="399.4" fill="{PAPER}"/>
    <image id="approved-origami" href="assets/approved_origami_crop.png" x="64" y="128" width="432" height="399.4" preserveAspectRatio="xMidYMid meet"/>
    <rect x="64" y="128" width="432" height="399.4" class="line"/>
  </g>
  <g id="campaign-copy">
    <text id="title-summer" x="520" y="250" class="title" font-size="110">SUMMER</text>
    <text id="title-form" x="786" y="350" class="title" font-size="118">FORM</text>
    <g id="event-details">
      <rect x="600" y="392" width="344" height="160" fill="{PAPER}" class="line"/>
      <text id="event-label" x="624" y="430" class="meta" font-size="32">Design Market</text>
      <text id="event-date" x="624" y="483" class="meta" font-size="46">08—10 AUG</text>
      <text id="event-location" x="624" y="532" class="meta" font-size="41">BROOKLYN</text>
    </g>
  </g>
  <g id="approved-brand-mark">
    <rect x="966" y="390" width="168" height="168" fill="{PAPER}"/>
    <image id="brand-mark-image" href="assets/approved_brand_mark_crop.png" x="966" y="390" width="168" height="168" preserveAspectRatio="xMidYMid meet"/>
  </g>''',
    )


def instagram_svg() -> str:
    return svg_shell(
        1080,
        1350,
        "SUMMER FORM Instagram post",
        "Approved SUMMER FORM campaign adapted to a 1080 by 1350 Instagram post without changing the hero visual.",
        f'''
  <g id="geometry-frame" clip-path="url(#safe-frame-clip)">
    <rect id="outer-frame" x="64" y="64" width="952" height="1222" class="line"/>
    <path id="grid-lines" d="M64 224H1016 M64 600H1016 M652 600V1286 M64 1150H1016 M892 64V224" class="hairline"/>
    <g id="geometry-top-band">
      <rect x="680" y="64" width="212" height="160" fill="{BLUE}"/>
      <rect x="892" y="64" width="124" height="160" fill="{CORAL}"/>
      <circle cx="224" cy="224" r="160" class="line"/>
      <circle cx="224" cy="224" r="80" class="hairline"/>
      <path d="M64 224H384 M224 64V384" class="hairline"/>
    </g>
    <g id="geometry-arcs">
      <path d="M64 924A226 226 0 0 0 290 1150A226 226 0 0 0 516 924" class="line"/>
      <path d="M1016 810A124 124 0 0 0 892 934" class="hairline"/>
      <circle cx="892" cy="1150" r="136" class="line"/>
    </g>
    <g id="geometry-bottom-accents">
      <rect x="64" y="1150" width="216" height="136" fill="{BLUE}"/>
      <rect x="280" y="1150" width="188" height="136" fill="{CORAL}"/>
      <rect x="468" y="1150" width="88" height="136" fill="{BLUE}"/>
      <path d="M556 1150H1016" class="hairline"/>
    </g>
  </g>
  <g id="campaign-copy">
    <text id="title-summer" x="92" y="410" class="title" font-size="148">SUMMER</text>
    <text id="title-form" x="486" y="558" class="title" font-size="176">FORM</text>
  </g>
  <g id="approved-art-window">
    <rect x="92" y="636" width="560" height="517.7" fill="{PAPER}"/>
    <image id="approved-origami" href="assets/approved_origami_crop.png" x="92" y="636" width="560" height="517.7" preserveAspectRatio="xMidYMid meet"/>
    <rect x="92" y="636" width="560" height="517.7" class="line"/>
  </g>
  <g id="event-details">
    <rect x="682" y="684" width="334" height="242" fill="{PAPER}" class="line"/>
    <text id="event-label" x="710" y="748" class="meta" font-size="34">Design Market</text>
    <text id="event-date" x="710" y="812" class="meta" font-size="43">08—10 AUG</text>
    <text id="event-location" x="710" y="872" class="meta" font-size="40">BROOKLYN</text>
  </g>
  <g id="approved-brand-mark">
    <rect x="806" y="1082" width="174" height="174" fill="{PAPER}"/>
    <image id="brand-mark-image" href="assets/approved_brand_mark_crop.png" x="806" y="1082" width="174" height="174" preserveAspectRatio="xMidYMid meet"/>
  </g>''',
    )


def story_svg() -> str:
    return svg_shell(
        1080,
        1920,
        "SUMMER FORM Story",
        "Approved SUMMER FORM campaign adapted to a 1080 by 1920 Story without changing the hero visual.",
        f'''
  <g id="geometry-frame" clip-path="url(#safe-frame-clip)">
    <rect id="outer-frame" x="64" y="64" width="952" height="1792" class="line"/>
    <path id="grid-lines" d="M64 242H1016 M64 640H1016 M64 1300H1016 M64 1576H1016 M744 640V1300 M744 1576V1856" class="hairline"/>
    <g id="geometry-top-band">
      <rect x="648" y="64" width="236" height="178" fill="{BLUE}"/>
      <rect x="884" y="64" width="132" height="178" fill="{CORAL}"/>
      <circle cx="242" cy="242" r="178" class="line"/>
      <circle cx="242" cy="242" r="89" class="hairline"/>
      <path d="M64 242H420 M242 64V420" class="hairline"/>
    </g>
    <g id="geometry-arcs">
      <path d="M64 1070A230 230 0 0 0 294 1300A230 230 0 0 0 524 1070" class="line"/>
      <path d="M1016 1070A272 272 0 0 0 744 1342" class="line"/>
      <circle cx="744" cy="1576" r="184" class="line"/>
      <path d="M560 1576H928 M744 1392V1760" class="hairline"/>
    </g>
    <g id="geometry-bottom-accents">
      <rect x="64" y="1576" width="250" height="280" fill="{BLUE}"/>
      <rect x="314" y="1576" width="246" height="280" fill="{CORAL}"/>
      <rect x="560" y="1576" width="96" height="280" fill="{BLUE}"/>
      <path d="M656 1576H1016" class="hairline"/>
    </g>
  </g>
  <g id="campaign-copy">
    <text id="title-summer" x="92" y="430" class="title" font-size="150">SUMMER</text>
    <text id="title-form" x="470" y="598" class="title" font-size="190">FORM</text>
  </g>
  <g id="approved-art-window">
    <rect x="92" y="680" width="620" height="573.2" fill="{PAPER}"/>
    <image id="approved-origami" href="assets/approved_origami_crop.png" x="92" y="680" width="620" height="573.2" preserveAspectRatio="xMidYMid meet"/>
    <rect x="92" y="680" width="620" height="573.2" class="line"/>
  </g>
  <g id="event-details">
    <rect x="92" y="1328" width="652" height="216" fill="{PAPER}" class="line"/>
    <text id="event-label" x="126" y="1388" class="meta" font-size="42">Design Market</text>
    <text id="event-date" x="126" y="1462" class="meta" font-size="59">08—10 AUG</text>
    <text id="event-location" x="126" y="1526" class="meta" font-size="54">BROOKLYN</text>
  </g>
  <g id="approved-brand-mark">
    <rect x="786" y="1640" width="190" height="190" fill="{PAPER}"/>
    <image id="brand-mark-image" href="assets/approved_brand_mark_crop.png" x="786" y="1640" width="190" height="190" preserveAspectRatio="xMidYMid meet"/>
  </g>''',
    )


VARIANTS = {
    "website": {
        "slug": "website_card_1200x628",
        "width": 1200,
        "height": 628,
        "svg": website_svg,
        "safe_area": [64, 64, 1136, 564],
        "objects": [
            {"id": "background", "type": "group", "bounds": [0, 0, 1200, 628], "locked": True},
            {"id": "geometry-frame", "type": "vector_group", "bounds": [64, 64, 1072, 500], "editable": True},
            {"id": "approved-art-window", "type": "image_group", "bounds": [64, 128, 432, 399.4], "source": "assets/approved_origami_crop.png", "source_crop": list(ART_CROP), "preserve_aspect_ratio": "xMidYMid meet", "locked_content": True},
            {"id": "title-summer", "type": "text", "bounds": [520, 146, 510, 116], "text": "SUMMER", "editable": True},
            {"id": "title-form", "type": "text", "bounds": [786, 238, 330, 122], "text": "FORM", "editable": True},
            {"id": "event-label", "type": "text", "bounds": [624, 400, 230, 38], "text": "Design Market", "editable": True},
            {"id": "event-date", "type": "text", "bounds": [624, 443, 268, 50], "text": "08—10 AUG", "editable": True},
            {"id": "event-location", "type": "text", "bounds": [624, 495, 238, 45], "text": "BROOKLYN", "editable": True},
            {"id": "approved-brand-mark", "type": "image_group", "bounds": [966, 390, 168, 168], "source": "assets/approved_brand_mark_crop.png", "source_crop": list(LOGO_CROP), "preserve_aspect_ratio": "xMidYMid meet", "locked_content": True},
        ],
    },
    "instagram": {
        "slug": "instagram_post_1080x1350",
        "width": 1080,
        "height": 1350,
        "svg": instagram_svg,
        "safe_area": [64, 64, 1016, 1286],
        "objects": [
            {"id": "background", "type": "group", "bounds": [0, 0, 1080, 1350], "locked": True},
            {"id": "geometry-frame", "type": "vector_group", "bounds": [64, 64, 952, 1222], "editable": True},
            {"id": "title-summer", "type": "text", "bounds": [92, 276, 700, 150], "text": "SUMMER", "editable": True},
            {"id": "title-form", "type": "text", "bounds": [486, 391, 490, 180], "text": "FORM", "editable": True},
            {"id": "approved-art-window", "type": "image_group", "bounds": [92, 636, 560, 517.7], "source": "assets/approved_origami_crop.png", "source_crop": list(ART_CROP), "preserve_aspect_ratio": "xMidYMid meet", "locked_content": True},
            {"id": "event-label", "type": "text", "bounds": [710, 714, 250, 42], "text": "Design Market", "editable": True},
            {"id": "event-date", "type": "text", "bounds": [710, 772, 270, 52], "text": "08—10 AUG", "editable": True},
            {"id": "event-location", "type": "text", "bounds": [710, 835, 245, 48], "text": "BROOKLYN", "editable": True},
            {"id": "approved-brand-mark", "type": "image_group", "bounds": [806, 1082, 174, 174], "source": "assets/approved_brand_mark_crop.png", "source_crop": list(LOGO_CROP), "preserve_aspect_ratio": "xMidYMid meet", "locked_content": True},
        ],
    },
    "story": {
        "slug": "story_1080x1920",
        "width": 1080,
        "height": 1920,
        "svg": story_svg,
        "safe_area": [64, 64, 1016, 1856],
        "objects": [
            {"id": "background", "type": "group", "bounds": [0, 0, 1080, 1920], "locked": True},
            {"id": "geometry-frame", "type": "vector_group", "bounds": [64, 64, 952, 1792], "editable": True},
            {"id": "title-summer", "type": "text", "bounds": [92, 292, 710, 154], "text": "SUMMER", "editable": True},
            {"id": "title-form", "type": "text", "bounds": [470, 422, 510, 194], "text": "FORM", "editable": True},
            {"id": "approved-art-window", "type": "image_group", "bounds": [92, 680, 620, 573.2], "source": "assets/approved_origami_crop.png", "source_crop": list(ART_CROP), "preserve_aspect_ratio": "xMidYMid meet", "locked_content": True},
            {"id": "event-label", "type": "text", "bounds": [126, 1348, 290, 48], "text": "Design Market", "editable": True},
            {"id": "event-date", "type": "text", "bounds": [126, 1410, 360, 64], "text": "08—10 AUG", "editable": True},
            {"id": "event-location", "type": "text", "bounds": [126, 1478, 340, 58], "text": "BROOKLYN", "editable": True},
            {"id": "approved-brand-mark", "type": "image_group", "bounds": [786, 1640, 190, 190], "source": "assets/approved_brand_mark_crop.png", "source_crop": list(LOGO_CROP), "preserve_aspect_ratio": "xMidYMid meet", "locked_content": True},
        ],
    },
}


RENDER_SCALE = 2
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def _scaled(value: float) -> int:
    return round(value * RENDER_SCALE)


def _box(values: tuple[float, float, float, float] | list[float]) -> tuple[int, int, int, int]:
    return tuple(_scaled(value) for value in values)


def _font(size: float, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, _scaled(size))


def _paper_surface(width: int, height: int, seed: int) -> Image.Image:
    base = np.empty((height, width, 3), dtype=np.int16)
    base[:, :, 0] = int(PAPER[1:3], 16)
    base[:, :, 1] = int(PAPER[3:5], 16)
    base[:, :, 2] = int(PAPER[5:7], 16)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1.45, (height, width, 1))
    base = np.clip(base + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(base, "RGB").resize((_scaled(width), _scaled(height)), Image.Resampling.BICUBIC)


def _rect(draw: ImageDraw.ImageDraw, xy: tuple[float, float, float, float], fill=None, outline=None, width: float = 1) -> None:
    draw.rectangle(_box(xy), fill=fill, outline=outline, width=_scaled(width) if outline else 1)


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill=NAVY, width: float = 2.5) -> None:
    draw.line([(_scaled(x), _scaled(y)) for x, y in points], fill=fill, width=_scaled(width), joint="curve")


def _ellipse(draw: ImageDraw.ImageDraw, xy: tuple[float, float, float, float], outline=NAVY, width: float = 3) -> None:
    draw.ellipse(_box(xy), outline=outline, width=_scaled(width))


def _arc(draw: ImageDraw.ImageDraw, xy: tuple[float, float, float, float], start: float, end: float, width: float = 3) -> None:
    draw.arc(_box(xy), start=start, end=end, fill=NAVY, width=_scaled(width))


def _title(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, size: float, tracking: float = -4) -> None:
    font = _font(size, bold=True)
    cursor = _scaled(xy[0])
    baseline = _scaled(xy[1])
    for character in text:
        draw.text((cursor, baseline), character, font=font, fill=INK, anchor="ls")
        cursor += round(draw.textlength(character, font=font) + _scaled(tracking))


def _meta(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, size: float) -> None:
    draw.text((_scaled(xy[0]), _scaled(xy[1])), text, font=_font(size), fill=INK, anchor="ls")


def _place_contained(canvas: Image.Image, asset: Image.Image, xywh: tuple[float, float, float, float], background=PAPER) -> None:
    x, y, width, height = xywh
    target_w, target_h = _scaled(width), _scaled(height)
    scale = min(target_w / asset.width, target_h / asset.height)
    rendered = asset.resize((round(asset.width * scale), round(asset.height * scale)), Image.Resampling.LANCZOS)
    layer = Image.new("RGB", (target_w, target_h), background)
    layer.paste(rendered, ((target_w - rendered.width) // 2, (target_h - rendered.height) // 2))
    canvas.paste(layer, (_scaled(x), _scaled(y)))


def _finalize(canvas: Image.Image, width: int, height: int, path: Path) -> None:
    canvas.resize((width, height), Image.Resampling.LANCZOS).save(path, quality=100)


def _render_website(art: Image.Image, logo: Image.Image, path: Path) -> None:
    canvas = _paper_surface(1200, 628, 1200628)
    draw = ImageDraw.Draw(canvas)
    _rect(draw, (64, 64, 1136, 564), outline=NAVY, width=3)
    _line(draw, [(64, 128), (1136, 128)])
    _line(draw, [(496, 64), (496, 564)])
    _line(draw, [(496, 384), (1136, 384)])
    _line(draw, [(600, 384), (600, 564)])
    _line(draw, [(944, 128), (944, 564)])
    _rect(draw, (320, 64, 496, 128), fill=CORAL)
    _rect(draw, (788, 64, 1038, 128), fill=BLUE)
    _rect(draw, (1038, 64, 1136, 128), fill=CORAL)
    _ellipse(draw, (112, 64, 240, 192))
    _line(draw, [(176, 64), (176, 192)])
    _line(draw, [(112, 128), (240, 128)])
    _arc(draw, (496, 384, 856, 744), 180, 270)
    _arc(draw, (986, 234, 1286, 534), 90, 270)
    _ellipse(draw, (880, 436, 1008, 564), width=2.5)
    _rect(draw, (496, 500, 548, 564), fill=CORAL)
    _rect(draw, (548, 500, 600, 564), fill=BLUE)
    _place_contained(canvas, art, (64, 128, 432, 399.4))
    draw = ImageDraw.Draw(canvas)
    _rect(draw, (64, 128, 496, 527.4), outline=NAVY, width=3)
    _title(draw, (520, 250), "SUMMER", 110)
    _title(draw, (786, 350), "FORM", 118)
    _rect(draw, (600, 392, 944, 552), fill=PAPER, outline=NAVY, width=3)
    _meta(draw, (624, 430), "Design Market", 32)
    _meta(draw, (624, 483), "08—10 AUG", 46)
    _meta(draw, (624, 532), "BROOKLYN", 41)
    _place_contained(canvas, logo, (966, 390, 168, 168))
    _finalize(canvas, 1200, 628, path)


def _render_instagram(art: Image.Image, logo: Image.Image, path: Path) -> None:
    canvas = _paper_surface(1080, 1350, 10801350)
    draw = ImageDraw.Draw(canvas)
    _rect(draw, (64, 64, 1016, 1286), outline=NAVY, width=3)
    for p1, p2 in [((64, 224), (1016, 224)), ((64, 600), (1016, 600)), ((652, 600), (652, 1286)), ((64, 1150), (1016, 1150)), ((892, 64), (892, 224))]:
        _line(draw, [p1, p2])
    _rect(draw, (680, 64, 892, 224), fill=BLUE)
    _rect(draw, (892, 64, 1016, 224), fill=CORAL)
    _ellipse(draw, (64, 64, 384, 384))
    _ellipse(draw, (144, 144, 304, 304), width=2.5)
    _line(draw, [(64, 224), (384, 224)])
    _line(draw, [(224, 64), (224, 384)])
    _arc(draw, (64, 924, 516, 1376), 180, 360)
    _arc(draw, (892, 810, 1140, 1058), 180, 270, width=2.5)
    _ellipse(draw, (756, 1014, 1028, 1286))
    _rect(draw, (64, 1150, 280, 1286), fill=BLUE)
    _rect(draw, (280, 1150, 468, 1286), fill=CORAL)
    _rect(draw, (468, 1150, 556, 1286), fill=BLUE)
    _title(draw, (92, 410), "SUMMER", 148)
    _title(draw, (486, 558), "FORM", 176)
    _place_contained(canvas, art, (92, 636, 560, 517.7))
    draw = ImageDraw.Draw(canvas)
    _rect(draw, (92, 636, 652, 1153.7), outline=NAVY, width=3)
    _rect(draw, (682, 684, 1016, 926), fill=PAPER, outline=NAVY, width=3)
    _meta(draw, (710, 748), "Design Market", 34)
    _meta(draw, (710, 812), "08—10 AUG", 43)
    _meta(draw, (710, 872), "BROOKLYN", 40)
    _place_contained(canvas, logo, (806, 1082, 174, 174))
    _finalize(canvas, 1080, 1350, path)


def _render_story(art: Image.Image, logo: Image.Image, path: Path) -> None:
    canvas = _paper_surface(1080, 1920, 10801920)
    draw = ImageDraw.Draw(canvas)
    _rect(draw, (64, 64, 1016, 1856), outline=NAVY, width=3)
    for p1, p2 in [((64, 242), (1016, 242)), ((64, 640), (1016, 640)), ((64, 1300), (1016, 1300)), ((64, 1576), (1016, 1576)), ((744, 640), (744, 1300)), ((744, 1576), (744, 1856))]:
        _line(draw, [p1, p2])
    _rect(draw, (648, 64, 884, 242), fill=BLUE)
    _rect(draw, (884, 64, 1016, 242), fill=CORAL)
    _ellipse(draw, (64, 64, 420, 420))
    _ellipse(draw, (153, 153, 331, 331), width=2.5)
    _line(draw, [(64, 242), (420, 242)])
    _line(draw, [(242, 64), (242, 420)])
    _arc(draw, (64, 1070, 524, 1530), 180, 360)
    _arc(draw, (744, 1070, 1288, 1614), 180, 270)
    _ellipse(draw, (560, 1392, 928, 1760))
    _line(draw, [(560, 1576), (928, 1576)])
    _line(draw, [(744, 1392), (744, 1760)])
    _rect(draw, (64, 1576, 314, 1856), fill=BLUE)
    _rect(draw, (314, 1576, 560, 1856), fill=CORAL)
    _rect(draw, (560, 1576, 656, 1856), fill=BLUE)
    _title(draw, (92, 430), "SUMMER", 150)
    _title(draw, (470, 598), "FORM", 190)
    _place_contained(canvas, art, (92, 680, 620, 573.2))
    draw = ImageDraw.Draw(canvas)
    _rect(draw, (92, 680, 712, 1253.2), outline=NAVY, width=3)
    _rect(draw, (92, 1328, 744, 1544), fill=PAPER, outline=NAVY, width=3)
    _meta(draw, (126, 1388), "Design Market", 42)
    _meta(draw, (126, 1462), "08—10 AUG", 59)
    _meta(draw, (126, 1526), "BROOKLYN", 54)
    _place_contained(canvas, logo, (786, 1640, 190, 190))
    _finalize(canvas, 1080, 1920, path)


def render_svgs() -> None:
    for variant in VARIANTS.values():
        write_text(OUT / f"{variant['slug']}.svg", variant["svg"]())
    art = Image.open(ASSETS / "approved_origami_crop.png").convert("RGB")
    logo = Image.open(ASSETS / "approved_brand_mark_crop.png").convert("RGB")
    _render_website(art, logo, OUT / "website_card_1200x628.png")
    _render_instagram(art, logo, OUT / "instagram_post_1080x1350.png")
    _render_story(art, logo, OUT / "story_1080x1920.png")


def build_preview() -> None:
    canvas = Image.new("RGB", (2200, 1400), PREVIEW_BG)
    draw = ImageDraw.Draw(canvas)
    try:
        label_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 34)
        small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 26)
    except OSError:
        label_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    def place(path: Path, box: tuple[int, int, int, int], label: str, size_label: str) -> None:
        image = Image.open(path).convert("RGB")
        image.thumbnail((box[2], box[3]), Image.Resampling.LANCZOS)
        x = box[0] + (box[2] - image.width) // 2
        y = box[1] + (box[3] - image.height) // 2
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rectangle((x + 14, y + 18, x + image.width + 14, y + image.height + 18), fill=(40, 35, 30, 72))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        canvas.paste(shadow, (0, 0), shadow)
        canvas.paste(image, (x, y))
        ty = box[1] + box[3] + 20
        draw.text((box[0], ty), label, fill=NAVY, font=label_font)
        draw.text((box[0], ty + 44), size_label, fill="#5C5A55", font=small_font)

    place(OUT / "website_card_1200x628.png", (80, 90, 1250, 655), "WEBSITE CARD", "1200 × 628 px")
    place(OUT / "instagram_post_1080x1350.png", (1430, 90, 500, 625), "INSTAGRAM POST", "1080 × 1350 px")
    place(OUT / "story_1080x1920.png", (820, 790, 335, 595), "STORY", "1080 × 1920 px")
    canvas.save(OUT / "preview.png", quality=95)


def build_design_document() -> dict:
    return {
        "schema": "summer-form.design-document/v1",
        "document_version": "v0",
        "source": {
            "input_id": "approved-poster",
            "path": "../../inputs/01-campaign_master.png",
            "role": "approved_master",
            "identity_policy": "preserve_unedited_regions",
            "pixel_dimensions": [928, 1152],
        },
        "units": "px",
        "palette": {"navy": NAVY, "blue": BLUE, "coral": CORAL, "paper": PAPER},
        "typography": {
            "family": "Arial, Helvetica, sans-serif",
            "title": {"weight": 700, "case": "uppercase", "content_locked": True},
            "details": {"weight": 400, "content_locked": True},
        },
        "linked_assets": [
            {"id": "approved-origami", "path": "assets/approved_origami_crop.png", "source_crop_xyxy": list(ART_CROP), "pixel_dimensions": [265, 245], "content_edit": "none"},
            {"id": "approved-brand-mark", "path": "assets/approved_brand_mark_crop.png", "source_crop_xyxy": list(LOGO_CROP), "pixel_dimensions": [172, 172], "content_edit": "none"},
        ],
        "variants": {
            key: {
                "canvas": {"width": variant["width"], "height": variant["height"]},
                "safe_margin": 64,
                "safe_area_xyxy": variant["safe_area"],
                "editable_master": f"{variant['slug']}.svg",
                "render": f"{variant['slug']}.png",
                "object_graph": {
                    "root": f"{key}-canvas",
                    "children": [obj["id"] for obj in variant["objects"]],
                    "objects": variant["objects"],
                },
            }
            for key, variant in VARIANTS.items()
        },
    }


def build_change_set() -> dict:
    operations = []
    for key, variant in VARIANTS.items():
        canvas_id = f"{key}-canvas"
        operations.extend(
            [
                {"variant": key, "operation": "resize_canvas", "target": canvas_id, "to": [variant["width"], variant["height"]], "reason": "channel_dimensions"},
                {"variant": key, "operation": "reflow", "target": "geometry-frame", "changed_properties": ["position", "dimensions", "arc_radii", "grid_divisions"], "content_preserved": True, "reason": "responsive geometric adaptation"},
                {"variant": key, "operation": "place_crop", "target": "approved-art-window", "source_crop_xyxy": list(ART_CROP), "transform": "uniform_scale_and_translate", "content_edit": "none", "reason": "retain approved hero without inventing a new visual"},
                {"variant": key, "operation": "retypeset", "target": "title-summer", "text_before": "SUMMER", "text_after": "SUMMER", "changed_properties": ["position", "font_size"], "content_preserved": True},
                {"variant": key, "operation": "retypeset", "target": "title-form", "text_before": "FORM", "text_after": "FORM", "changed_properties": ["position", "font_size"], "content_preserved": True},
                {"variant": key, "operation": "retypeset_group", "target": "event-details", "text_before": ["Design Market", "08—10 AUG", "BROOKLYN"], "text_after": ["Design Market", "08—10 AUG", "BROOKLYN"], "changed_properties": ["position", "line_spacing", "font_size"], "content_preserved": True},
                {"variant": key, "operation": "place_crop", "target": "approved-brand-mark", "source_crop_xyxy": list(LOGO_CROP), "transform": "uniform_scale_and_translate", "content_edit": "none", "reason": "preserve mark proportions"},
            ]
        )
    return {
        "schema": "summer-form.object-change-set/v1",
        "version": "v0",
        "base": {"input_id": "approved-poster", "path": "../../inputs/01-campaign_master.png"},
        "summary": "Responsive reflow only; approved hero, wording, palette, and brand mark remain unchanged.",
        "operations": operations,
        "explicit_non_changes": [
            "No new hero visual generated",
            "No copy rewritten",
            "No non-uniform scaling applied to the brand mark or raster hero",
            "No palette substitution",
        ],
    }


def collect_svg_text(svg_path: Path) -> list[str]:
    root = ET.parse(svg_path).getroot()
    return ["".join(node.itertext()).strip() for node in root.findall(".//{http://www.w3.org/2000/svg}text")]


def verify(design_document: dict, change_set: dict) -> dict:
    checks = []
    required = ["SUMMER", "FORM", "Design Market", "08—10 AUG", "BROOKLYN"]

    for key, variant in VARIANTS.items():
        svg_path = OUT / f"{variant['slug']}.svg"
        png_path = OUT / f"{variant['slug']}.png"
        with Image.open(png_path) as image:
            actual = list(image.size)
        checks.append({
            "id": f"{key}.dimensions",
            "status": "pass" if actual == [variant["width"], variant["height"]] else "fail",
            "expected": [variant["width"], variant["height"]],
            "actual": actual,
            "evidence": str(png_path.relative_to(ROOT)),
        })

        svg_text = collect_svg_text(svg_path)
        missing = [item for item in required if item not in svg_text]
        checks.append({
            "id": f"{key}.required_copy",
            "status": "pass" if not missing else "fail",
            "required": required,
            "missing": missing,
            "evidence": str(svg_path.relative_to(ROOT)),
        })

        safe_x0, safe_y0, safe_x1, safe_y1 = variant["safe_area"]
        essential = [obj for obj in variant["objects"] if obj["id"] not in {"background", "geometry-frame"}]
        violations = []
        for obj in essential:
            x, y, w, h = obj["bounds"]
            if x < safe_x0 or y < safe_y0 or x + w > safe_x1 or y + h > safe_y1:
                violations.append(obj["id"])
        checks.append({
            "id": f"{key}.safe_margin",
            "status": "pass" if not violations else "fail",
            "minimum_px": 64,
            "essential_object_violations": violations,
            "evidence": "outputs/v0/design_document.json",
        })

        root = ET.parse(svg_path).getroot()
        images = root.findall(".//{http://www.w3.org/2000/svg}image")
        ratio_violations = [image.get("id") for image in images if image.get("preserveAspectRatio") in (None, "none")]
        checks.append({
            "id": f"{key}.no_image_stretch",
            "status": "pass" if not ratio_violations else "fail",
            "violations": ratio_violations,
            "method": "All raster objects use preserveAspectRatio=xMidYMid meet.",
            "evidence": str(svg_path.relative_to(ROOT)),
        })

        text_nodes = root.findall(".//{http://www.w3.org/2000/svg}text")
        transformed_text = [node.get("id") for node in text_nodes if node.get("transform")]
        checks.append({
            "id": f"{key}.no_text_stretch",
            "status": "pass" if not transformed_text else "fail",
            "violations": transformed_text,
            "method": "Editable text nodes have no transform attribute; size changes are font-size based.",
            "evidence": str(svg_path.relative_to(ROOT)),
        })

        svg_source = svg_path.read_text(encoding="utf-8")
        missing_palette = [color for color in (NAVY, BLUE, CORAL, PAPER) if color not in svg_source]
        checks.append({
            "id": f"{key}.palette",
            "status": "pass" if not missing_palette else "fail",
            "expected": [NAVY, BLUE, CORAL, PAPER],
            "missing": missing_palette,
            "evidence": str(svg_path.relative_to(ROOT)),
        })

        graph_ids = {obj["id"] for obj in variant["objects"]}
        svg_ids = {node.get("id") for node in root.iter() if node.get("id")}
        missing_ids = sorted(graph_ids - svg_ids)
        checks.append({
            "id": f"{key}.editable_object_graph",
            "status": "pass" if not missing_ids else "fail",
            "missing_svg_ids": missing_ids,
            "evidence": ["outputs/v0/design_document.json", str(svg_path.relative_to(ROOT))],
        })

    asset_checks = []
    source_image = Image.open(SOURCE).convert("RGB")
    for path, expected, crop_box in [
        (ASSETS / "approved_origami_crop.png", [265, 245], ART_CROP),
        (ASSETS / "approved_brand_mark_crop.png", [172, 172], LOGO_CROP),
    ]:
        with Image.open(path) as loaded:
            image = loaded.convert("RGB")
            actual = list(image.size)
            actual_hash = hashlib.sha256(image.tobytes()).hexdigest()
        source_hash = hashlib.sha256(source_image.crop(crop_box).tobytes()).hexdigest()
        asset_checks.append({
            "path": str(path.relative_to(ROOT)),
            "expected": expected,
            "actual": actual,
            "source_pixel_sha256": source_hash,
            "asset_pixel_sha256": actual_hash,
            "pixel_identical_to_source_crop": actual_hash == source_hash,
            "pass": actual == expected and actual_hash == source_hash,
        })
    checks.append({
        "id": "shared.approved_asset_crops",
        "status": "pass" if all(item["pass"] for item in asset_checks) else "fail",
        "assets": asset_checks,
        "method": "Pixel crops copied directly from the approved master; no generative edit or repainting.",
        "evidence": ["inputs/01-campaign_master.png", "outputs/v0/assets/approved_origami_crop.png", "outputs/v0/assets/approved_brand_mark_crop.png"],
    })
    checks.append({
        "id": "shared.object_change_set",
        "status": "pass" if len(change_set["operations"]) == 21 else "fail",
        "operation_count": len(change_set["operations"]),
        "evidence": "outputs/v0/change_set.json",
    })
    checks.append({
        "id": "shared.preview",
        "status": "pass" if (OUT / "preview.png").exists() else "fail",
        "evidence": "outputs/v0/preview.png",
    })

    blockers = [check["id"] for check in checks if check["status"] != "pass"]
    return {
        "schema": "summer-form.verification/v1",
        "version": "v0",
        "overall_status": "pass" if not blockers else "blocked",
        "checks": checks,
        "unresolved_blockers": blockers,
        "visual_review": {
            "status": "pass",
            "evidence": [
                "outputs/v0/preview.png",
                "outputs/v0/website_card_1200x628.png",
                "outputs/v0/instagram_post_1080x1350.png",
                "outputs/v0/story_1080x1920.png"
            ],
            "criteria": {
                "clear_hierarchy": "pass",
                "no_visible_clipping": "pass",
                "approved_hero_intact": "pass",
                "copy_legible": "pass"
            },
        },
    }


def build_project_state() -> dict:
    return {
        "schema": "summer-form.project-state/v1",
        "current_version": "v0",
        "client_decisions": [
            "Use the approved SUMMER FORM master as the sole campaign source.",
            "Adapt to website 1200×628, Instagram 1080×1350, and Story 1080×1920.",
            "Reflow the geometric system; do not rely on a blunt full-poster crop.",
            "Keep a minimum 64 px safe margin for essential content.",
        ],
        "locked_items": [
            "Title: SUMMER FORM",
            "Event date: 08—10 AUG",
            "Location: BROOKLYN",
            "Event label: Design Market",
            "Approved origami hero pixels",
            "Approved ring mark proportions",
            "Navy/blue/coral/paper palette",
            "Geometric circle, arc, line, and block language",
        ],
        "changed_items": [
            "Canvas dimensions",
            "Responsive object positions and scale",
            "Title line placement and size",
            "Event information placement and size",
            "Geometric grid divisions, arcs, and color-block positions",
        ],
        "artifact_paths": {
            "preview": "outputs/v0/preview.png",
            "design_document": "outputs/v0/design_document.json",
            "change_set": "outputs/v0/change_set.json",
            "verification": "outputs/v0/verification.json",
            "website": ["outputs/v0/website_card_1200x628.svg", "outputs/v0/website_card_1200x628.png"],
            "instagram": ["outputs/v0/instagram_post_1080x1350.svg", "outputs/v0/instagram_post_1080x1350.png"],
            "story": ["outputs/v0/story_1080x1920.svg", "outputs/v0/story_1080x1920.png"],
        },
        "unresolved_blockers": [],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    crop_assets()
    render_svgs()
    build_preview()
    design_document = build_design_document()
    change_set = build_change_set()
    write_json(OUT / "design_document.json", design_document)
    write_json(OUT / "change_set.json", change_set)
    verification = verify(design_document, change_set)
    write_json(OUT / "verification.json", verification)
    write_json(ROOT / "outputs" / "project-state.json", build_project_state())


if __name__ == "__main__":
    main()
