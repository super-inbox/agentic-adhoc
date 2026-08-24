#!/usr/bin/env python3
"""Render the editable adaptation-map object graph to preview.png."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DOC = json.loads((OUT / "design_document.json").read_text(encoding="utf-8"))


def hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


P = {k: hex_color(v) for k, v in DOC["palette"].items()}


def font(key: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(DOC["fonts"][key], size=size)


F_DISPLAY_66 = font("display", 66)
F_DISPLAY_38 = font("display", 38)
F_DISPLAY_32 = font("display", 32)
F_DISPLAY_24 = font("display", 24)
F_CJK_34 = font("cjkMedium", 34)
F_CJK_28 = font("cjkMedium", 28)
F_CJK_26 = font("cjkMedium", 26)
F_CJK_24 = font("cjk", 24)
F_CJK_22 = font("cjk", 22)
F_CJK_20 = font("cjk", 20)
F_CJK_18 = font("cjk", 18)
F_LATIN_26 = font("latin", 26)
F_LATIN_22 = font("latin", 22)


def rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, family: str, start: int, minimum: int = 9):
    size = start
    while size > minimum:
        f = font(family, size)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
        size -= 1
    return font(family, minimum)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, f, max_width: int):
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textbbox((0, 0), candidate, font=f)[2] > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def paper_texture(base: Image.Image):
    # Deterministic low-contrast paper grain; never touches the approved source image.
    noise = Image.effect_noise(base.size, 9).convert("L")
    tint = Image.new("RGB", base.size, P["paperDeep"])
    mask = noise.point(lambda v: int(abs(v - 128) * 0.13))
    base.paste(tint, (0, 0), mask)


def draw_grid_motif(draw: ImageDraw.ImageDraw, box, compact=False):
    x, y, w, h = box
    stroke = max(1, int(min(w, h) * 0.009))
    for fx in (0.31, 0.68):
        xx = x + int(w * fx)
        draw.line((xx, y, xx, y + h), fill=P["blue"], width=stroke)
    for fy in (0.34, 0.70):
        yy = y + int(h * fy)
        draw.line((x, yy, x + w, yy), fill=P["blue"], width=stroke)
    if not compact:
        r = int(min(w, h) * 0.19)
        draw.arc((x - r // 2, y + int(h * 0.05), x + int(1.5 * r), y + int(h * 0.05) + 2 * r), 270, 90, fill=P["blue"], width=stroke)
        draw.arc((x + w - int(1.5 * r), y + h - 2 * r, x + w + r // 2, y + h), 90, 270, fill=P["blue"], width=stroke)
    draw.rectangle((x, y + int(h * 0.70), x + int(w * 0.18), y + int(h * 0.88)), fill=P["coral"])
    draw.rectangle((x + int(w * 0.68), y, x + int(w * 0.86), y + int(h * 0.17)), fill=P["navy"])


def draw_sculpture(draw: ImageDraw.ImageDraw, box):
    x, y, w, h = box
    # A schematic folded-paper object, deliberately distinct from the locked source pixels.
    pts = {
        "a": (x + int(w * 0.08), y + int(h * 0.40)),
        "b": (x + int(w * 0.52), y + int(h * 0.08)),
        "c": (x + int(w * 0.92), y + int(h * 0.48)),
        "d": (x + int(w * 0.55), y + int(h * 0.92)),
        "e": (x + int(w * 0.36), y + int(h * 0.52)),
    }
    draw.polygon((pts["a"], pts["b"], pts["e"]), fill=(233, 227, 214), outline=P["blue"])
    draw.polygon((pts["b"], pts["c"], pts["e"]), fill=(249, 245, 235), outline=P["blue"])
    draw.polygon((pts["c"], pts["d"], pts["e"]), fill=(215, 208, 194), outline=P["blue"])
    draw.polygon((pts["a"], pts["d"], pts["e"]), fill=(242, 237, 225), outline=P["blue"])
    draw.polygon(
        (
            (x + int(w * 0.43), y + int(h * 0.60)),
            (x + int(w * 0.69), y + int(h * 0.52)),
            (x + int(w * 0.57), y + int(h * 0.77)),
        ),
        fill=P["coral"],
    )


def norm_box(frame, norm):
    x, y, w, h = frame
    nx, ny, nw, nh = norm
    return (
        x + int(w * nx),
        y + int(h * ny),
        max(1, int(w * nw)),
        max(1, int(h * nh)),
    )


def draw_mini_title(draw, box, frame, channel_id):
    x, y, w, h = box
    landscape = frame[2] / frame[3] > 1.45
    if landscape:
        lines = ["SUMMER", "FORM"]
        target = max(9, int(min(h * 0.43, w * 0.16)))
    else:
        lines = ["SUMMER", "FORM"]
        target = max(9, int(min(h * 0.40, w * 0.19)))
    f = font("display", target)
    gap = max(0, int(target * -0.04))
    yy = y
    for line in lines:
        if draw.textbbox((0, 0), line, font=f)[2] > w:
            f = fit_text(draw, line, w, "display", target)
        draw.text((x, yy), line, font=f, fill=P["navy"])
        yy += int(target * 0.88) + gap


def draw_mini_info(draw, box, frame):
    x, y, w, h = box
    size = max(7, int(min(h * 0.31, w * 0.13)))
    f = font("display", size)
    lines = ["08—10 AUG", "BROOKLYN"]
    yy = y
    for line in lines:
        ff = fit_text(draw, line, w, "display", size, 6)
        draw.text((x, yy), line, font=ff, fill=P["navy"])
        yy += max(size, int(h * 0.43))


def draw_story_info_lines(draw, channel, frame):
    """Keep the v0 location baseline while moving only the Story date."""
    _, _, w, h = norm_box(frame, channel["layout"]["eventInfo"])
    size = max(7, int(min(h * 0.31, w * 0.13)))
    for role, label in (("date", "08—10 AUG"), ("location", "BROOKLYN")):
        x, y, line_w, _ = norm_box(frame, channel["layout"][role])
        ff = fit_text(draw, label, line_w, "display", size, 6)
        draw.text((x, y), label, font=ff, fill=P["navy"])


def draw_url_slot(draw, box):
    x, y, w, h = box
    draw.rectangle((x, y, x + w, y + h), fill=P["coral"])
    label = "URL · 待提供"
    f = fit_text(draw, label, max(10, w - 6), "cjkMedium", max(7, int(h * 0.55)), 6)
    tb = draw.textbbox((0, 0), label, font=f)
    ty = y + max(0, (h - (tb[3] - tb[1])) // 2 - tb[1])
    draw.text((x + 4, ty), label, font=f, fill=P["white"])


def draw_channel_frame(draw: ImageDraw.ImageDraw, channel):
    fx, fy, fw, fh = channel["frameBbox"]
    draw.rectangle((fx, fy, fx + fw, fy + fh), fill=P["white"], outline=P["blue"], width=2)
    draw_grid_motif(draw, (fx, fy, fw, fh), compact=(fw / fh > 2.5))
    roles = ("title", "sculpture", "registrationUrl") if channel["id"] == "story" else ("title", "sculpture", "eventInfo", "registrationUrl")
    for role in roles:
        b = norm_box((fx, fy, fw, fh), channel["layout"][role])
        if role == "title":
            draw_mini_title(draw, b, (fx, fy, fw, fh), channel["id"])
        elif role == "sculpture":
            draw_sculpture(draw, b)
        elif role == "eventInfo":
            draw_mini_info(draw, b, (fx, fy, fw, fh))
        else:
            draw_url_slot(draw, b)
    if channel["id"] == "story":
        draw_story_info_lines(draw, channel, (fx, fy, fw, fh))
    if channel["id"] == "story":
        top = fy + int(fh * 0.12)
        bottom = fy + int(fh * 0.88)
        dash = 8
        for xx in range(fx + 4, fx + fw - 4, dash * 2):
            draw.line((xx, top, min(xx + dash, fx + fw - 4), top), fill=P["coral"], width=2)
            draw.line((xx, bottom, min(xx + dash, fx + fw - 4), bottom), fill=P["coral"], width=2)


def draw_channel_card(draw: ImageDraw.ImageDraw, channel):
    x, y, w, h = channel["cardBbox"]
    rounded_rect(draw, (x, y, x + w, y + h), 12, P["white"], P["blue"], 2)
    draw.rectangle((x, y, x + 13, y + h), fill=P["coral"])
    draw.text((x + 38, y + 27), channel["name"], font=F_CJK_28, fill=P["navy"])
    ratio_text = f'{channel["ratio"]}  /  {channel["proposedExport"]}'
    draw.text((x + 38, y + 70), ratio_text, font=F_LATIN_22, fill=P["muted"])
    draw_channel_frame(draw, channel)

    fx, fy, fw, fh = channel["frameBbox"]
    if y < 900:
        tx = fx + fw + 28
        ty = fy
        tw = x + w - tx - 28
        strategy_font = F_CJK_22
        bullets_font = F_CJK_18
    else:
        tx = x + 38
        ty = fy + fh + 34
        tw = w - 76
        strategy_font = F_CJK_20
        bullets_font = F_CJK_18

    draw.text((tx, ty), "取舍", font=F_CJK_24 if y < 900 else F_CJK_22, fill=P["coral"])
    cursor = ty + 38
    for line in wrap_text(draw, channel["strategy"], strategy_font, tw):
        draw.text((tx, cursor), line, font=strategy_font, fill=P["ink"])
        cursor += 31 if y < 900 else 28
    cursor += 16
    for item in channel["tradeoffs"]:
        bullet = "— " + item
        for i, line in enumerate(wrap_text(draw, bullet, bullets_font, tw)):
            draw.text((tx, cursor), line, font=bullets_font, fill=P["muted"])
            cursor += 27 if y < 900 else 25
        cursor += 3


def render():
    canvas = Image.new("RGB", (DOC["canvas"]["width"], DOC["canvas"]["height"]), P["paper"])
    paper_texture(canvas)
    draw = ImageDraw.Draw(canvas)

    # Header grid echoes the approved campaign without altering it.
    draw.line((80, 222, 2480, 222), fill=P["blue"], width=2)
    draw.text((80, 58), "SUMMER FORM / ADAPTATION MAP", font=F_DISPLAY_66, fill=P["navy"])
    draw.text((82, 151), "v1 · Story 安全区修订（仅日期 + URL 上移）", font=F_CJK_28, fill=P["coral"])

    draw.rectangle((1450, 58, 2480, 113), fill=P["navy"])
    draw.text((1475, 70), "LOCK / 标题 · 日期 · 地点 · 报名 URL", font=F_CJK_24, fill=P["white"])
    draw.rectangle((1450, 124, 2480, 190), fill=P["coral"])
    draw.text((1475, 143), "BLOCKER / 母版未见报名 URL，全部版式已预留位置", font=F_CJK_22, fill=P["white"])

    # Source panel with the source pixels preserved exactly inside a contain fit.
    sx, sy, sw, sh = 80, 250, 500, 1430
    rounded_rect(draw, (sx, sy, sx + sw, sy + sh), 12, P["white"], P["blue"], 2)
    draw.rectangle((sx, sy, sx + sw, sy + 88), fill=P["navy"])
    draw.text((sx + 34, sy + 23), "APPROVED MASTER", font=F_DISPLAY_32, fill=P["white"])
    source = Image.open(ROOT / DOC["sourceBinding"]["path"]).convert("RGB")
    thumb = source.copy()
    thumb.thumbnail((380, 472), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", (thumb.width + 36, thumb.height + 36), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rectangle((18, 18, 18 + thumb.width, 18 + thumb.height), fill=(34, 45, 62, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    canvas.paste(shadow, (122, 348), shadow)
    canvas.paste(thumb, (140, 372))

    draw = ImageDraw.Draw(canvas)
    draw.text((130, 885), "批准母版 · 928 × 1152", font=F_CJK_28, fill=P["navy"])
    draw.text((130, 932), "IDENTITY LOCK", font=F_DISPLAY_24, fill=P["coral"])
    source_notes = [
        "不做机械居中裁切",
        "蓝 / 珊瑚 / 暖白配色",
        "细线网格与圆弧几何",
        "折纸焦点与粗体标题层级",
        "母版像素不改动",
    ]
    yy = 980
    for note in source_notes:
        draw.rectangle((132, yy + 8, 144, yy + 20), fill=P["blue"])
        draw.text((160, yy), note, font=F_CJK_22, fill=P["ink"])
        yy += 48
    draw.rectangle((130, 1264, 530, 1378), fill=P["coral"])
    draw.text((154, 1284), "缺失输入", font=F_CJK_24, fill=P["white"])
    draw.text((154, 1325), "请提供准确报名 URL", font=F_CJK_28, fill=P["white"])
    draw.text((130, 1420), "本轮仅提交构图策略；", font=F_CJK_22, fill=P["muted"])
    draw.text((130, 1456), "收到 URL 与地图批准后进入七版批量输出。", font=F_CJK_22, fill=P["muted"])
    draw.line((130, 1535, 530, 1535), fill=P["blue"], width=2)
    draw.text((130, 1560), "SOURCE STATUS", font=F_DISPLAY_24, fill=P["navy"])
    draw.text((130, 1600), "UNCHANGED / LOCKED", font=F_DISPLAY_32, fill=P["navy"])

    for channel in DOC["channels"]:
        draw_channel_card(draw, channel)

    # Footer legend.
    draw.text((650, 1712), "LEGEND", font=F_DISPLAY_24, fill=P["navy"])
    draw.rectangle((775, 1715, 798, 1738), fill=P["coral"])
    draw.text((812, 1708), "URL 保留位 / 待输入", font=F_CJK_20, fill=P["muted"])
    draw.line((1070, 1726, 1118, 1726), fill=P["blue"], width=3)
    draw.text((1134, 1708), "批准视觉语法", font=F_CJK_20, fill=P["muted"])
    draw.polygon(((1370, 1738), (1395, 1712), (1420, 1738)), fill=P["paperDeep"], outline=P["blue"])
    draw.text((1434, 1708), "折纸焦点重排", font=F_CJK_20, fill=P["muted"])
    draw.text((2015, 1708), "NO FINAL CHANNEL ART YET", font=F_DISPLAY_24, fill=P["coral"])

    canvas.save(OUT / "preview.png", optimize=True)


if __name__ == "__main__":
    render()
