#!/usr/bin/env python3
"""Render the editable MORI object graph and validate product pixel identity."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v0"
DOC_PATH = OUT / "design_document.json"
PREVIEW_PATH = OUT / "preview.png"
SVG_PATH = OUT / "mori_aroma_poster_editable.svg"
PRODUCT_SOURCE = ROOT / "inputs" / "02-product_reference.png"
PRODUCT_CUTOUT = OUT / "assets" / "product_cutout.png"
FONT_PATHS = {
    "display": Path("/opt/X11/share/system_fonts/Supplemental/Songti.ttc"),
    "sans": Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    "latin": Path("/opt/X11/share/system_fonts/Supplemental/Arial.ttf"),
}


def rgba(color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    red, green, blue = ImageColor.getrgb(color)
    return red, green, blue, round(255 * opacity)


def load_doc() -> dict:
    return json.loads(DOC_PATH.read_text(encoding="utf-8"))


def asset_map(doc: dict) -> dict[str, Path]:
    mapped: dict[str, Path] = {}
    for asset in doc["assets"]:
        path = Path(asset["path"])
        mapped[asset["id"]] = (OUT / path).resolve()
    return mapped


def make_product_cutout() -> dict:
    source = Image.open(PRODUCT_SOURCE).convert("RGB")
    rgb = np.asarray(source).astype(np.float32)
    distance = np.sqrt(np.sum((255.0 - rgb) ** 2, axis=2))
    alpha = np.clip((distance - 2.5) / 35.0 * 255.0, 0, 255).astype(np.uint8)

    # Recover edge/shadow chroma from the original white matte. Core product
    # pixels (alpha=255) remain byte-for-byte identical to the source.
    a = alpha.astype(np.float32) / 255.0
    recovered = rgb.copy()
    partial = (a > 0) & (a < 1)
    if np.any(partial):
        aa = a[partial, None]
        recovered[partial] = np.clip((rgb[partial] - 255.0 * (1.0 - aa)) / aa, 0, 255)
    recovered = recovered.astype(np.uint8)
    recovered[alpha == 255] = rgb[alpha == 255].astype(np.uint8)

    # Use a high-confidence matte threshold only for the crop bounds so the
    # faint studio background does not force a full-canvas crop. The saved
    # cutout still retains the softer shadow pixels inside those bounds.
    ys, xs = np.where(alpha > 128)
    margin = 26
    left = max(0, int(xs.min()) - margin)
    top = max(0, int(ys.min()) - margin)
    right = min(source.width, int(xs.max()) + margin + 1)
    bottom = min(source.height, int(ys.max()) + margin + 1)

    out_rgba = np.dstack([recovered, alpha])
    cutout = Image.fromarray(out_rgba, mode="RGBA").crop((left, top, right, bottom))
    PRODUCT_CUTOUT.parent.mkdir(parents=True, exist_ok=True)
    cutout.save(PRODUCT_CUTOUT)

    opaque = alpha == 255
    exact_core = bool(np.array_equal(recovered[opaque], rgb.astype(np.uint8)[opaque]))
    sample_xy = (512, 545)
    sample_source = source.getpixel(sample_xy)
    sample_cutout = cutout.getpixel((sample_xy[0] - left, sample_xy[1] - top))[:3]
    return {
        "source_size": [source.width, source.height],
        "crop_box_source": [left, top, right, bottom],
        "cutout_size": [cutout.width, cutout.height],
        "opaque_core_pixel_count": int(opaque.sum()),
        "opaque_core_rgb_exact": exact_core,
        "sample_source_xy": list(sample_xy),
        "sample_source_rgb": list(sample_source),
        "sample_cutout_rgb": list(sample_cutout),
        "sample_exact": sample_source == sample_cutout,
    }


def font_for(obj: dict) -> ImageFont.FreeTypeFont:
    path = FONT_PATHS[obj.get("font_token", "sans")]
    return ImageFont.truetype(str(path), int(obj["font_size"]))


def draw_text_with_tracking(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    content: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    tracking: float,
) -> None:
    x, y = xy
    for character in content:
        draw.text((x, y), character, font=font, fill=fill, anchor="la")
        bounds = draw.textbbox((0, 0), character, font=font)
        x += bounds[2] - bounds[0] + tracking


def fit_image(image: Image.Image, size: tuple[int, int], fit: str) -> Image.Image:
    if fit == "contain":
        contained = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        layer.alpha_composite(contained, ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2))
        return layer
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)).convert("RGBA")


def render_png(doc: dict) -> None:
    width = int(doc["canvas"]["width"])
    height = int(doc["canvas"]["height"])
    canvas = Image.new("RGBA", (width, height), rgba(doc["tokens"]["colors"]["warm_ivory"]))
    assets = asset_map(doc)

    for obj in doc["objects"]:
        obj_type = obj["type"]
        opacity = float(obj.get("opacity", 1.0))
        if obj_type == "image":
            source = Image.open(assets[obj["asset"]]).convert("RGBA")
            layer = fit_image(source, (int(obj["width"]), int(obj["height"])), obj.get("fit", "cover"))
            if opacity < 1:
                layer.putalpha(layer.getchannel("A").point(lambda value: round(value * opacity)))
            canvas.alpha_composite(layer, (int(obj["x"]), int(obj["y"])))
            continue

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        if obj_type == "rounded_rect":
            box = [obj["x"], obj["y"], obj["x"] + obj["width"], obj["y"] + obj["height"]]
            draw.rounded_rectangle(
                box,
                radius=int(obj.get("radius", 0)),
                fill=rgba(obj["fill"], opacity),
                outline=rgba(obj["stroke"], opacity) if obj.get("stroke") else None,
                width=int(obj.get("stroke_width", 1)),
            )
        elif obj_type == "ellipse":
            box = [obj["x"], obj["y"], obj["x"] + obj["width"], obj["y"] + obj["height"]]
            draw.ellipse(
                box,
                fill=rgba(obj["fill"], opacity),
                outline=rgba(obj["stroke"], opacity * float(obj.get("stroke_opacity", 1))) if obj.get("stroke") else None,
                width=int(obj.get("stroke_width", 1)),
            )
        elif obj_type == "line":
            draw.line(
                [obj["x1"], obj["y1"], obj["x2"], obj["y2"]],
                fill=rgba(obj["stroke"], opacity),
                width=int(obj.get("stroke_width", 1)),
            )
        elif obj_type == "text":
            draw_text_with_tracking(
                draw,
                (int(obj["x"]), int(obj["y"])),
                obj["content"],
                font_for(obj),
                rgba(obj["fill"], opacity),
                float(obj.get("tracking", 0)),
            )
        else:
            raise ValueError(f"Unsupported object type: {obj_type}")
        canvas.alpha_composite(overlay)

    canvas.convert("RGB").save(PREVIEW_PATH, quality=95)


def svg_color_opacity(obj: dict) -> tuple[str, str]:
    return obj.get("fill", "none"), str(obj.get("opacity", 1))


def render_svg(doc: dict) -> None:
    assets = {asset["id"]: asset for asset in doc["assets"]}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{doc["canvas"]["width"]}" height="{doc["canvas"]["height"]}" viewBox="0 0 {doc["canvas"]["width"]} {doc["canvas"]["height"]}">',
        "  <title>MORI 陶土红香薰机产品信息页 v0</title>",
        "  <desc>对象可编辑：背景、品牌签名、原产品图、标题、三张功能卡与底部规格带均为独立命名对象。</desc>",
        "  <defs>",
        '    <clipPath id="hero-clip"><rect x="0" y="0" width="1200" height="880"/></clipPath>',
        "  </defs>",
    ]
    for group in doc["groups"]:
        lines.append(f'  <g id="{html.escape(group["id"].replace("/", "-"))}" data-label="{html.escape(group["label"])}">')
        child_ids = set(group["children"])
        for obj in (item for item in doc["objects"] if item["id"] in child_ids):
            oid = html.escape(obj["id"].replace("/", "-"))
            opacity = obj.get("opacity", 1)
            if obj["type"] == "rounded_rect":
                stroke = f' stroke="{obj["stroke"]}" stroke-width="{obj.get("stroke_width", 1)}"' if obj.get("stroke") else ""
                lines.append(f'    <rect id="{oid}" x="{obj["x"]}" y="{obj["y"]}" width="{obj["width"]}" height="{obj["height"]}" rx="{obj.get("radius", 0)}" fill="{obj["fill"]}" opacity="{opacity}"{stroke}/>')
            elif obj["type"] == "ellipse":
                cx = obj["x"] + obj["width"] / 2
                cy = obj["y"] + obj["height"] / 2
                stroke = f' stroke="{obj["stroke"]}" stroke-width="{obj.get("stroke_width", 1)}" stroke-opacity="{obj.get("stroke_opacity", 1)}"' if obj.get("stroke") else ""
                lines.append(f'    <ellipse id="{oid}" cx="{cx}" cy="{cy}" rx="{obj["width"] / 2}" ry="{obj["height"] / 2}" fill="{obj["fill"]}" opacity="{opacity}"{stroke}/>')
            elif obj["type"] == "line":
                lines.append(f'    <line id="{oid}" x1="{obj["x1"]}" y1="{obj["y1"]}" x2="{obj["x2"]}" y2="{obj["y2"]}" stroke="{obj["stroke"]}" stroke-width="{obj.get("stroke_width", 1)}" opacity="{opacity}"/>')
            elif obj["type"] == "text":
                token = doc["tokens"]["typography"][obj["font_token"]]
                lines.append(f'    <text id="{oid}" x="{obj["x"]}" y="{obj["y"] + obj["font_size"]}" fill="{obj["fill"]}" opacity="{opacity}" font-family="{html.escape(token["family"])}" font-size="{obj["font_size"]}" font-weight="{obj.get("font_weight", token["weight"])}" letter-spacing="{obj.get("tracking", 0)}">{html.escape(obj["content"])}</text>')
            elif obj["type"] == "image":
                asset = assets[obj["asset"]]
                href = html.escape(asset["path"])
                preserve = "xMidYMid meet" if obj.get("fit") == "contain" else "xMidYMid slice"
                clip = ' clip-path="url(#hero-clip)"' if obj["id"] == "hero/texture" else ""
                lock = ' data-identity-locked="true"' if obj.get("identity_locked") else ""
                lines.append(f'    <image id="{oid}" x="{obj["x"]}" y="{obj["y"]}" width="{obj["width"]}" height="{obj["height"]}" xlink:href="{href}" preserveAspectRatio="{preserve}" opacity="{opacity}"{clip}{lock}/>')
        lines.append("  </g>")
    lines.append("</svg>")
    SVG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    doc = load_doc()
    identity = make_product_cutout()
    render_png(doc)
    render_svg(doc)
    metadata_path = OUT / "assets" / "product_identity_metrics.json"
    metadata_path.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"preview": str(PREVIEW_PATH), "editable_svg": str(SVG_PATH), "product_identity": identity}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
