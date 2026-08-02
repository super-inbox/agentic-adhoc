from __future__ import annotations

import io
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont

from app.agent_runtime.schemas import VoteAnalysis


_APP_ROOT = Path(__file__).resolve().parent.parent
_FONT_PATH = _APP_ROOT / "assets" / "fonts" / "NotoSansSC-Regular.ttf"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(_FONT_PATH), size)
    except Exception:
        return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy, value: str, *, size: int, fill, anchor=None):
    draw.text(xy, value, font=_font(size), fill=fill, anchor=anchor)


def _fit_text(draw: ImageDraw.ImageDraw, value: str, *, size: int, max_width: int) -> str:
    normalized = " ".join(value.split())
    font = _font(size)
    if draw.textlength(normalized, font=font) <= max_width:
        return normalized
    suffix = "…"
    while normalized and draw.textlength(normalized + suffix, font=font) > max_width:
        normalized = normalized[:-1]
    return normalized + suffix


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS,
    )
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _image_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    out = io.BytesIO()
    image.save(out, format=format, optimize=True)
    return out.getvalue()


def split_vote_candidates(source_images: List[bytes]) -> List[bytes]:
    """Normalize four files or split one comparison board into A-D.

    The deterministic splitter supports the common 4-column, 4-row, and 2x2
    boards. Visual verification is responsible for rejecting a single image
    that does not actually contain four coherent candidates.
    """
    if len(source_images) == 4:
        return source_images
    if len(source_images) != 1:
        raise ValueError("Design vote requires one comparison board or four images.")
    image = Image.open(io.BytesIO(source_images[0])).convert("RGB")
    w, h = image.size
    boxes: List[tuple[int, int, int, int]] = []
    if w / max(h, 1) >= 2.2:
        boxes = [(round(i * w / 4), 0, round((i + 1) * w / 4), h) for i in range(4)]
    elif h / max(w, 1) >= 2.2:
        boxes = [(0, round(i * h / 4), w, round((i + 1) * h / 4)) for i in range(4)]
    else:
        boxes = [
            (0, 0, w // 2, h // 2),
            (w // 2, 0, w, h // 2),
            (0, h // 2, w // 2, h),
            (w // 2, h // 2, w, h),
        ]
    return [_image_bytes(image.crop(box), "JPEG") for box in boxes]


def render_vote_report(analysis: VoteAnalysis, candidate_images: List[bytes]) -> bytes:
    width, height = 1600, 1220
    canvas = Image.new("RGB", (width, height), (247, 245, 240))
    draw = ImageDraw.Draw(canvas)
    ink = (24, 27, 34)
    muted = (99, 103, 112)
    accent = (121, 72, 54)
    gold = (188, 137, 65)

    _text(
        draw,
        (70, 54),
        _fit_text(draw, analysis.product, size=52, max_width=1160),
        size=52,
        fill=ink,
    )
    _text(
        draw,
        (70, 120),
        _fit_text(draw, f"AI 模拟投票 · {analysis.axis}", size=29, max_width=1360),
        size=29,
        fill=accent,
    )
    _text(draw, (1530, 76), f"置信度 {round(analysis.confidence * 100)}%", size=23, fill=muted, anchor="ra")

    card_w, gap, start_x = 340, 26, 70
    top = 180
    variant_by_id = {variant.id: variant for variant in analysis.variants}
    for index, label in enumerate(("A", "B", "C", "D")):
        x = start_x + index * (card_w + gap)
        winner = label == analysis.winner
        border = gold if winner else (218, 215, 207)
        draw.rounded_rectangle(
            (x, top, x + card_w, top + 560),
            radius=24,
            fill=(255, 255, 255),
            outline=border,
            width=7 if winner else 2,
        )
        thumb = _cover(Image.open(io.BytesIO(candidate_images[index])), (300, 310))
        canvas.paste(thumb, (x + 20, top + 20))
        draw.rounded_rectangle((x + 20, top + 20, x + 84, top + 84), radius=18, fill=(20, 22, 27))
        _text(draw, (x + 52, top + 52), label, size=32, fill="white", anchor="mm")
        if winner:
            draw.rounded_rectangle((x + 202, top + 31, x + 309, top + 74), radius=18, fill=gold)
            _text(draw, (x + 255, top + 52), "推荐", size=21, fill="white", anchor="mm")
        percent = analysis.overall[label]
        _text(draw, (x + 20, top + 356), f"{percent}%", size=60, fill=accent if winner else ink)
        draw.rounded_rectangle((x + 20, top + 430, x + card_w - 20, top + 448), radius=9, fill=(234, 230, 221))
        draw.rounded_rectangle(
            (x + 20, top + 430, x + 20 + round((card_w - 40) * percent / 100), top + 448),
            radius=9,
            fill=gold if winner else accent,
        )
        variant = variant_by_id[label]
        _text(
            draw,
            (x + 20, top + 472),
            _fit_text(draw, variant.design_language, size=22, max_width=300),
            size=22,
            fill=muted,
        )
        if variant.strengths:
            _text(
                draw,
                (x + 20, top + 512),
                _fit_text(draw, "＋ " + variant.strengths[0], size=20, max_width=300),
                size=20,
                fill=(55, 112, 78),
            )

    section_top = 790
    _text(draw, (70, section_top), "分人群偏好", size=32, fill=ink)
    segment_x = 70
    for segment in analysis.segments[:5]:
        leader = max(("A", "B", "C", "D"), key=lambda key: segment.votes[key])
        box_w = 276
        draw.rounded_rectangle(
            (segment_x, section_top + 54, segment_x + box_w, section_top + 172),
            radius=18,
            fill=(239, 235, 226),
        )
        _text(
            draw,
            (segment_x + 18, section_top + 72),
            _fit_text(draw, segment.name, size=21, max_width=240),
            size=21,
            fill=ink,
        )
        _text(
            draw,
            (segment_x + 18, section_top + 116),
            f"偏好 {leader} · {segment.votes[leader]}%",
            size=24,
            fill=accent,
        )
        segment_x += box_w + 24

    draw.rounded_rectangle((70, 1010, 1530, 1122), radius=22, fill=(31, 34, 40))
    _text(
        draw,
        (100, 1036),
        _fit_text(draw, f"建议：{analysis.recommendation}", size=27, max_width=1380),
        size=27,
        fill="white",
    )
    _text(draw, (70, 1163), analysis.simulated_disclaimer, size=21, fill=muted)
    _text(draw, (1530, 1163), "Curify Design Agent", size=21, fill=muted, anchor="ra")
    return _image_bytes(canvas, "PNG")


def render_tryon_poster(image_bytes: bytes, direction: str, prompt: str) -> bytes:
    image = _cover(Image.open(io.BytesIO(image_bytes)), (1080, 1350))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(230):
        alpha = round(150 * (1 - y / 230))
        draw.rectangle((0, y, 1080, y + 1), fill=(10, 12, 17, alpha))
    for y in range(1110, 1350):
        alpha = round(175 * ((y - 1110) / 240))
        draw.rectangle((0, y, 1080, y + 1), fill=(10, 12, 17, alpha))
    composed = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composed)
    _text(draw, (58, 54), "CURIFY EDIT", size=28, fill=(255, 255, 255, 220))
    _text(
        draw,
        (58, 101),
        _fit_text(draw, direction, size=47, max_width=964),
        size=47,
        fill="white",
    )
    _text(
        draw,
        (58, 1212),
        _fit_text(draw, prompt, size=30, max_width=820),
        size=30,
        fill="white",
    )
    _text(draw, (1022, 1294), "AI CONCEPT", size=21, fill=(255, 255, 255, 210), anchor="ra")
    return _image_bytes(composed.convert("RGB"), "JPEG")


def validate_image_bytes(image_bytes: bytes, *, min_side: int = 512) -> List[str]:
    failures: List[str] = []
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        image = Image.open(io.BytesIO(image_bytes))
        if min(image.size) < min_side:
            failures.append(f"image is too small: {image.width}x{image.height}")
    except Exception:
        failures.append("artifact is not a readable image")
    return failures
