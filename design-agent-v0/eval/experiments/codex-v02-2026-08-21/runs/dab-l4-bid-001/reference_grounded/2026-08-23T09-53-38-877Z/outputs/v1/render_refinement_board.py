from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


HERE = Path(__file__).resolve().parent
FONT_PATH = "/opt/X11/share/system_fonts/Hiragino Sans GB.ttc"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_PATH, size=size, index=2 if bold else 0)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap_lines(draw, text, fnt, max_width):
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            trial = current + char
            if draw.textlength(trial, font=fnt) <= max_width or not current:
                current = trial
            else:
                lines.append(current.rstrip())
                current = char.lstrip()
        if current:
            lines.append(current.rstrip())
    return lines


def draw_wrapped(draw, x, y, text, fnt, fill, width, line_height=None, max_lines=None):
    line_height = line_height or int(fnt.size * 1.4)
    lines = wrap_lines(draw, text, fnt, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while draw.textlength(last + "…", font=fnt) > width and last:
            last = last[:-1]
        lines[-1] = last + "…"
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_height
    return y


def pill(draw, x, y, label, fill, text_fill):
    fnt = font(23, bold=True)
    w = int(draw.textlength(label, font=fnt)) + 38
    rounded(draw, (x, y, x + w, y + 48), 24, fill)
    draw.text((x + 19, y + 9), label, font=fnt, fill=text_fill)
    return w


def section_card(draw, x, y, w, title, accent, rows):
    h = 410
    rounded(draw, (x, y, x + w, y + h), 24, "#FFFFFF", outline="#D7D8D1", width=2)
    draw.rectangle((x, y, x + w, y + 10), fill=accent)
    draw.text((x + 30, y + 28), title, font=font(32, bold=True), fill="#202521")
    yy = y + 88
    for label, body in rows:
        draw.text((x + 30, yy), label, font=font(22, bold=True), fill=accent)
        yy = draw_wrapped(draw, x + 30, yy + 32, body, font(23), "#4F5551", w - 60, line_height=34, max_lines=3) + 18
    return h


def main():
    W, H = 2400, 2600
    bg = "#F3F4F0"
    ink = "#202521"
    muted = "#66706A"
    sky = "#A9D6E5"
    grain = "#F3B33D"
    olive = "#657846"

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    draw.text((95, 70), "SELECTED TERRITORY 02 · DAYLIGHT GRAIN · V1", font=font(27, bold=True), fill="#B77D12")
    draw.text((95, 120), "更留白，更礼赠", font=font(68, bold=True), fill=ink)
    draw.text((95, 205), "沿 B 精修：保留日光、模块与年轻识别；提升静区、硬盒结构与材料精度。", font=font(29), fill=muted)

    px = 1700
    px += pill(draw, px, 88, "B SELECTED", grain, ink) + 14
    pill(draw, px, 88, "LOGO LOCKED", ink, "#FFFFFF")

    colors = [("暖白", "#F7F6F0"), ("天蓝", sky), ("谷物黄", grain), ("橄榄", olive), ("炭灰", ink)]
    sx = 95
    for label, color in colors:
        rounded(draw, (sx, 274, sx + 112, 318), 9, color, outline="#C9CAC4", width=1)
        draw.text((sx, 327), label, font=font(19), fill=muted)
        sx += 142
    draw.text((810, 286), "色彩未重做：暖白成为主场，蓝黄退到边缘、内托与少量识别节点。", font=font(23), fill=muted)

    source = Image.open(HERE / "assets/territory-02-daylight-grain-refined.png").convert("RGB")
    hero = ImageOps.fit(source, (2210, 1474), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(hero, (95, 385))
    draw.rectangle((95, 385, 2305, 1859), outline="#FFFFFF", width=4)
    draw.text((95, 1876), "左：高克重硬盒＋精装包角＋天蓝内托｜中：电商主图扩大负空间｜右：门店减少满版图形、提升陈列间距", font=font(23), fill=muted)

    gap = 25
    card_w = (2210 - 2 * gap) // 3
    y = 1935
    section_card(
        draw,
        95,
        y,
        card_w,
        "礼盒 / PACKAGING",
        grain,
        [
            ("保留", "B 的暖白、天蓝内托、谷物黄细节与模块系列感。"),
            ("调整", "折叠纸盒升级为精装硬盒／抽屉盒；增加包角、深盒盖、适配内托、压凹层理与克制缎金边。"),
            ("Logo", "正面留出完整空白牌面，等待现有 Logo 与中文字标原样植入。"),
        ],
    )
    section_card(
        draw,
        95 + card_w + gap,
        y,
        card_w,
        "淘宝主图 / E-COM",
        sky,
        [
            ("保留", "圆形产品裁切、清晨光线与快速食欲识别。"),
            ("调整", "由满版蓝黄改为暖白主场；一主一辅产品、宽信息安全区，仅留窄黄线与浅蓝圆盘。"),
            ("结果", "年轻感仍来自尺度与裁切，不再依赖大面积高饱和色。"),
        ],
    )
    section_card(
        draw,
        95 + 2 * (card_w + gap),
        y,
        card_w,
        "门店 / RETAIL",
        olive,
        [
            ("保留", "浅枫木、天蓝金属边与日间通透感。"),
            ("调整", "移除大面积墙面／柜台图形；增加单盒间距、精装礼盒、标准托盘与白色背景面。"),
            ("结果", "门店从活泼快闪感转向年轻、清晰且更有礼赠秩序。"),
        ],
    )

    rounded(draw, (95, 2390, 2305, 2505), 20, ink)
    draw.text((125, 2417), "DELTA LOCK", font=font(25, bold=True), fill=grain)
    draw.text((330, 2415), "A、C 未改；B 的核心配色、模块、圆形裁切、日光与门店材料未改；只调整留白、色彩占比、礼盒结构与陈列密度。", font=font(24, bold=True), fill="#FFFFFF")
    draw.text((95, 2538), "注：视觉稿不重画 Logo。中文字标与 Logo 源文件缺失，最终落位仍需批准源资产。", font=font(21), fill=muted)

    out = HERE / "01-daylight-grain-v1-refinement-board.png"
    canvas.save(out, quality=95)
    print(out)


if __name__ == "__main__":
    main()
