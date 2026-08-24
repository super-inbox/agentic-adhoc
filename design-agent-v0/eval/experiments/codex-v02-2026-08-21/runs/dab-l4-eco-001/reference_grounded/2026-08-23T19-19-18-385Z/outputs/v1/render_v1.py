from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PATH = ROOT / "inputs" / "01-product_master.png"
BACKGROUND_PATH = ROOT / "outputs" / "v1" / "assets" / "city-commute-minimal-background.png"
CUTOUT_PATH = ROOT / "outputs" / "v1" / "assets" / "product-cutout-exact.png"
KEYFRAME_PATH = ROOT / "outputs" / "v1" / "city-loop-premium-keyframe.png"
BOARD_PATH = ROOT / "outputs" / "v1" / "city-loop-visual-direction-v1.png"

FONT_MEDIUM = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"

CHARCOAL = "#30312f"
MUTED = "#72756f"
OFF_WHITE = "#f6f5f0"
HAIRLINE = "#d7d7d0"


def font(size, medium=False):
    return ImageFont.truetype(FONT_MEDIUM if medium else FONT_LIGHT, size)


def cover(image, size):
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize((round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def make_exact_rgb_cutout():
    src = Image.open(PRODUCT_PATH).convert("RGB")
    rgb = np.asarray(src, dtype=np.uint8)
    values = rgb.astype(np.float32)
    saturation_span = values.max(axis=2) - values.min(axis=2)
    mean_value = values.mean(axis=2)

    # Separate the teal fabric by chroma and the charcoal base by darkness.
    # This deliberately excludes the pale gray studio cast shadow so it cannot
    # create a white halo on the new scene. RGB values remain byte-for-byte
    # identical to the master; only alpha is derived.
    alpha_from_chroma = np.clip((saturation_span - 1.5) / 18.0 * 255.0, 0, 255)
    alpha_from_darkness = np.clip((185.0 - mean_value) / 34.0 * 255.0, 0, 255)
    alpha = np.maximum(alpha_from_chroma, alpha_from_darkness)
    alpha = np.clip((alpha - 32.0) / 223.0 * 255.0, 0, 255).astype(np.uint8)
    alpha = np.asarray(Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(0.38)))
    rgba = np.dstack([rgb, alpha])
    cutout = Image.fromarray(rgba, "RGBA")
    CUTOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cutout.save(CUTOUT_PATH)
    return cutout


def nonempty_bbox(alpha):
    return alpha.point(lambda value: 255 if value >= 32 else 0).getbbox()


def place_product(base, cutout, desired_height, xy_bottom):
    bbox = nonempty_bbox(cutout.getchannel("A"))
    cropped = cutout.crop(bbox)
    scale = desired_height / cropped.height
    resized = cropped.resize((round(cropped.width * scale), desired_height), Image.Resampling.LANCZOS)
    x_center, bottom = xy_bottom
    x = round(x_center - resized.width / 2)
    y = bottom - resized.height

    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    shadow_w = round(resized.width * 0.72)
    sd.ellipse(
        (x_center - shadow_w // 2, bottom - 23, x_center + shadow_w // 2, bottom + 28),
        fill=(20, 25, 24, 56),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(17))
    base.alpha_composite(shadow)
    base.alpha_composite(resized, (x, y))
    return (x, y, x + resized.width, y + resized.height)


def make_keyframe(cutout):
    bg = Image.open(BACKGROUND_PATH).convert("RGBA")
    canvas = cover(bg, (1600, 900)).convert("RGBA")

    # A light veil keeps the scene restrained while preserving real texture.
    veil = Image.new("RGBA", canvas.size, (248, 247, 242, 18))
    canvas.alpha_composite(veil)
    place_product(canvas, cutout, desired_height=500, xy_bottom=(1218, 650))

    draw = ImageDraw.Draw(canvas)
    keyframe_type = "#f2f0e8"
    draw.text((92, 94), "城市轻行", font=font(66, True), fill=keyframe_type)
    draw.line((96, 187, 216, 187), fill=keyframe_type, width=2)
    draw.text((94, 214), "一体式挂环", font=font(27), fill=keyframe_type)
    canvas.convert("RGB").save(KEYFRAME_PATH, quality=96)


def text_block(draw, xy, text, fnt, fill, max_width, gap=8):
    x, y = xy
    line = ""
    lines = []
    for ch in text:
        candidate = line + ch
        if line and draw.textlength(candidate, font=fnt) > max_width:
            lines.append(line)
            line = ch
        else:
            line = candidate
    if line:
        lines.append(line)
    h = fnt.getbbox("国A")[3] - fnt.getbbox("国A")[1]
    for value in lines:
        draw.text((x, y), value, font=fnt, fill=fill)
        y += h + gap
    return y


def make_board():
    board = Image.new("RGB", (1600, 1900), OFF_WHITE)
    draw = ImageDraw.Draw(board)

    draw.text((80, 66), "城市轻行", font=font(54, True), fill=CHARCOAL)
    draw.text((80, 132), "视觉语气修订 · V1", font=font(22), fill=MUTED)
    draw.text((1210, 76), "方向已锁定", font=font(20, True), fill=CHARCOAL)
    draw.text((1210, 113), "CITY LOOP", font=font(18), fill=MUTED)
    draw.line((80, 184, 1520, 184), fill=HAIRLINE, width=2)

    keyframe = Image.open(KEYFRAME_PATH).convert("RGB").resize((1440, 810), Image.Resampling.LANCZOS)
    board.paste(keyframe, (80, 232))

    draw.line((80, 1100, 1520, 1100), fill=HAIRLINE, width=2)
    draw.text((80, 1152), "本轮调整", font=font(27, True), fill=CHARCOAL)
    draw.text((80, 1202), "克制光影", font=font(36, True), fill=CHARCOAL)
    draw.text((360, 1202), "更多留白", font=font(36, True), fill=CHARCOAL)
    draw.text((640, 1202), "更少文字", font=font(36, True), fill=CHARCOAL)
    draw.text((920, 1202), "无金色", font=font(36, True), fill=CHARCOAL)
    draw.text((1160, 1202), "产品原色", font=font(36, True), fill=CHARCOAL)

    draw.line((80, 1285, 1520, 1285), fill=HAIRLINE, width=1)
    draw.text((80, 1340), "画面规则", font=font(25, True), fill=CHARCOAL)
    rules = [
        "留白约占一半以上；产品保持单一视觉焦点。",
        "只用柔和晨光与一处长阴影；避免霓虹、硬高光和高反射材质。",
        "主视觉最多一条标题＋一条批准卖点；不使用漂浮标签或装饰英文。",
        "暖白 / 冷灰 / 炭黑 / 极淡天蓝 / 少量灰橄榄；不使用金色、黄铜、铜色。",
    ]
    y = 1392
    for i, rule in enumerate(rules, 1):
        draw.text((80, y), f"0{i}", font=font(19, True), fill=MUTED)
        y = text_block(draw, (130, y - 3), rule, font(22), CHARCOAL, 690, gap=6) + 20

    draw.text((900, 1340), "保持不变", font=font(25, True), fill=CHARCOAL)
    keep = [
        "城市通勤四个低成本场景假设",
        "12 小时续航 / IPX4 防泼水 / 一体式挂环",
        "产品外观、接口、Logo 与蓝绿色",
        "不增加按钮、挂绳、登山扣或固定支架",
    ]
    y2 = 1392
    for i, item in enumerate(keep, 1):
        draw.text((900, y2), f"0{i}", font=font(19, True), fill=MUTED)
        y2 = text_block(draw, (950, y2 - 3), item, font(22), CHARCOAL, 560, gap=6) + 20

    draw.line((80, 1740, 1520, 1740), fill=HAIRLINE, width=1)
    draw.text((80, 1790), "制作检查点", font=font(21, True), fill=CHARCOAL)
    draw.text((250, 1790), "挂包连接画面仍需官方挂环侧/背面素材；当前不虚构挂点或配件。", font=font(21), fill=MUTED)
    draw.text((80, 1840), "产品图仅做背景分离、等比缩放和位置合成；未调色、未重绘。", font=font(18), fill=MUTED)

    board.save(BOARD_PATH, quality=96)


if __name__ == "__main__":
    exact_cutout = make_exact_rgb_cutout()
    make_keyframe(exact_cutout)
    make_board()
    print(CUTOUT_PATH)
    print(KEYFRAME_PATH)
    print(BOARD_PATH)
