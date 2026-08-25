#!/usr/bin/env python3
"""Render preview.png from the editable design_document.json object graph."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE_DIR = Path(__file__).resolve().parent
DOC_PATH = BASE_DIR / "design_document.json"
OUT_PATH = BASE_DIR / "preview.png"


def rgba(hex_color: str, opacity: float = 1.0):
    value = hex_color.lstrip("#")
    rgb = tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    return (*rgb, max(0, min(255, round(opacity * 255))))


def layer(canvas_size):
    return Image.new("RGBA", canvas_size, (0, 0, 0, 0))


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255
    )
    return mask


def fit_cover(im: Image.Image, target_size):
    target_w, target_h = target_size
    scale = max(target_w / im.width, target_h / im.height)
    resized = im.resize(
        (round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def font_from_token(token, size_override=None):
    return ImageFont.truetype(
        token["font_file"],
        size_override or token["size"],
        index=token.get("font_index", 0),
    )


def centered_text(draw, box, text, font, fill):
    x, y, w, h = box
    bounds = draw.textbbox((0, 0), text, font=font)
    tw = bounds[2] - bounds[0]
    th = bounds[3] - bounds[1]
    tx = x + (w - tw) / 2 - bounds[0]
    ty = y + (h - th) / 2 - bounds[1]
    draw.text((round(tx), round(ty)), text, font=font, fill=fill)


def draw_icon(draw, kind, center, circle_fill, ink):
    cx, cy = center
    r = 43
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=circle_fill)
    width = 4
    if kind == "low_noise":
        points = []
        for i in range(-28, 29, 4):
            amp = 4 + 4 * (1 - abs(i) / 28)
            points.append((cx + i, cy + math.sin(i / 6) * amp))
        draw.line(points, fill=ink, width=width, joint="curve")
        draw.arc((cx - 24, cy - 24, cx + 24, cy + 24), 205, 335, fill=ink, width=3)
    elif kind == "timer":
        draw.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), outline=ink, width=3)
        draw.line((cx, cy, cx, cy - 15), fill=ink, width=width)
        draw.line((cx, cy, cx + 13, cy + 8), fill=ink, width=width)
        draw.line((cx - 10, cy - 31, cx + 10, cy - 31), fill=ink, width=3)
    elif kind == "clay_touch":
        draw.arc((cx - 26, cy - 24, cx + 26, cy + 15), 18, 162, fill=ink, width=3)
        draw.arc((cx - 22, cy - 8, cx + 22, cy + 27), 18, 162, fill=ink, width=3)
        for dx, dy in ((-15, 17), (0, 21), (15, 17)):
            draw.ellipse((cx + dx - 2, cy + dy - 2, cx + dx + 2, cy + dy + 2), fill=ink)


def render():
    doc = json.loads(DOC_PATH.read_text(encoding="utf-8"))
    canvas_size = (doc["canvas"]["width"], doc["canvas"]["height"])
    tokens = doc["tokens"]
    colors = tokens["colors"]
    base = Image.new("RGBA", canvas_size, rgba(colors["paper_highlight"]))

    for obj in doc["root"]["children"]:
        kind = obj["type"]
        if kind == "image":
            x, y, w, h = obj["bbox"]
            im = Image.open(BASE_DIR / obj["source"]).convert("RGBA")
            if "source_crop" in obj:
                im = im.crop(tuple(obj["source_crop"]))
            if obj.get("fit") == "cover":
                im = fit_cover(im, (w, h))
            else:
                im = im.resize((w, h), Image.Resampling.LANCZOS)
            if obj.get("clip_radius", 0):
                mask = rounded_mask((w, h), obj["clip_radius"])
                alpha = im.getchannel("A")
                im.putalpha(Image.composite(alpha, Image.new("L", (w, h), 0), mask))
            if obj.get("opacity", 1.0) < 1.0:
                alpha = im.getchannel("A").point(lambda a: round(a * obj["opacity"]))
                im.putalpha(alpha)
            base.alpha_composite(im, (x, y))
        elif kind == "rounded_rect":
            x, y, w, h = obj["bbox"]
            ov = layer(canvas_size)
            ImageDraw.Draw(ov).rounded_rectangle(
                (x, y, x + w, y + h),
                radius=obj.get("radius", 0),
                fill=rgba(obj["fill"], obj.get("opacity", 1.0)),
            )
            base = Image.alpha_composite(base, ov)
        elif kind == "frame":
            x, y, w, h = obj["bbox"]
            shadow = obj.get("shadow")
            if shadow:
                sh = layer(canvas_size)
                dx, dy = shadow["offset"]
                ImageDraw.Draw(sh).rounded_rectangle(
                    (x + dx, y + dy, x + w + dx, y + h + dy),
                    radius=obj.get("radius", 0),
                    fill=rgba(shadow["color"], shadow["opacity"]),
                )
                sh = sh.filter(ImageFilter.GaussianBlur(shadow["blur"]))
                base = Image.alpha_composite(base, sh)
            ov = layer(canvas_size)
            ImageDraw.Draw(ov).rounded_rectangle(
                (x, y, x + w, y + h),
                radius=obj.get("radius", 0),
                fill=rgba(obj["fill"], obj.get("fill_opacity", 1.0)),
                outline=rgba(obj["stroke"]),
                width=obj.get("stroke_width", 1),
            )
            base = Image.alpha_composite(base, ov)
        elif kind == "text":
            ov = layer(canvas_size)
            draw = ImageDraw.Draw(ov)
            token = tokens["typography"][obj["typography_token"]]
            centered_text(draw, obj["bbox"], obj["text"], font_from_token(token), rgba(token["color"]))
            base = Image.alpha_composite(base, ov)
        elif kind == "feature_strip":
            ov = layer(canvas_size)
            draw = ImageDraw.Draw(ov)
            x, y, w, h = obj["bbox"]
            line_color = rgba(obj["stroke"], 0.95)
            draw.line((x, y, x + w, y), fill=line_color, width=obj["stroke_width"])
            draw.line((x, y + h, x + w, y + h), fill=line_color, width=obj["stroke_width"])
            label_token = tokens["typography"]["feature_label"]
            label_font = font_from_token(label_token)
            for index, item in enumerate(obj["items"]):
                ix, iy, iw, ih = item["bbox"]
                if index:
                    draw.line((ix, y + 22, ix, y + h - 22), fill=line_color, width=1)
                draw_icon(
                    draw,
                    item["icon"],
                    (ix + iw // 2, iy + 90),
                    rgba(item["icon_fill"]),
                    rgba(colors["icon_ink"]),
                )
                centered_text(
                    draw,
                    (ix, iy + 166, iw, 62),
                    item["label"],
                    label_font,
                    rgba(label_token["color"]),
                )
            base = Image.alpha_composite(base, ov)
        elif kind == "line":
            ov = layer(canvas_size)
            ImageDraw.Draw(ov).line(
                tuple(obj["points"]),
                fill=rgba(obj["stroke"], obj.get("opacity", 1.0)),
                width=obj.get("stroke_width", 1),
            )
            base = Image.alpha_composite(base, ov)

    base.convert("RGB").save(OUT_PATH, quality=95, optimize=True)
    return OUT_PATH


if __name__ == "__main__":
    print(render())
