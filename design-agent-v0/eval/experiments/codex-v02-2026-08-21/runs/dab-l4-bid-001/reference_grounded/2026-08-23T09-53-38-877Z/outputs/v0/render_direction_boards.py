from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"

FONT_PATH = "/opt/X11/share/system_fonts/Hiragino Sans GB.ttc"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_PATH, size=size, index=2 if bold else 0)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap_lines(draw, text, fnt, max_width):
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
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


def draw_wrapped(draw, xy, text, fnt, fill, max_width, line_height=None, max_lines=None):
    x, y = xy
    line_height = line_height or int(fnt.size * 1.4)
    lines = wrap_lines(draw, text, fnt, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while draw.textlength(last + "…", font=fnt) > max_width and last:
            last = last[:-1]
        lines[-1] = last + "…"
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_height
    return y


def draw_label(draw, x, y, text, fill, text_fill="#FFFFFF"):
    fnt = font(23, bold=True)
    w = int(draw.textlength(text, font=fnt)) + 34
    rounded(draw, (x, y, x + w, y + 46), 23, fill)
    draw.text((x + 17, y + 9), text, font=fnt, fill=text_fill)
    return w


def draw_palette(draw, x, y, colors, labels, dark_text="#20211E"):
    sw = 86
    for i, color in enumerate(colors):
        bx = x + i * (sw + 18)
        rounded(draw, (bx, y, bx + sw, y + 42), 8, color, outline="#FFFFFF55", width=1)
        draw.text((bx, y + 53), labels[i], font=font(18), fill=dark_text)


def make_hypothesis_board():
    W, H = 2400, 2000
    bg = "#F4F1EA"
    ink = "#22231F"
    muted = "#696A63"
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)

    d.text((110, 74), "GRAIN & GLOW", font=font(26, bold=True), fill="#8B6A30")
    d.text((110, 120), "冲突地图与 10 个方向假设", font=font(64, bold=True), fill=ink)
    d.text((110, 202), "先展开，再聚类。当前为选择关口，不代表最终设计。", font=font(30), fill=muted)
    draw_label(d, 1930, 90, "V0 · SELECTION", "#252521")
    draw_label(d, 1930, 145, "LOGO LOCKED", "#8B6A30")

    d.text((110, 285), "01  冲突整理", font=font(34, bold=True), fill=ink)
    conflicts = [
        ("年轻  VS.  小红书模板", "年轻感改由裁切、节奏与使用场景产生；避开奶油色静物、居中文案和泛生活方式套版。"),
        ("礼赠可信  VS.  日常触达", "礼感由盒型、闭合、纸张和工艺承担；亲近感由色彩、食物尺度和信息效率承担。"),
        ("Logo 锁定  VS.  系统焕新", "现有 Logo 结构与中文品牌名不动；只改变容器、色彩、影像、版式与空间材料。"),
        ("三参考不一致", "A 提取克制与栅格；B 提取模块色彩；C 提取亲和几何。只取原则，不复制物件、版式或符号。"),
        ("电商快读  VS.  门店沉浸", "同一视觉语法需从 4:5 缩略图扩展到橱窗、柜台、导视与礼盒陈列。"),
        ("1998 底气  VS.  22–30 新客", "让历史成为品质背书，不把历史做成仿古道具；产品本身与当代使用方式是桥梁。"),
    ]
    gap = 26
    col_w = (2180 - 2 * gap) // 3
    card_h = 176
    for i, (title, body) in enumerate(conflicts):
        col, row = i % 3, i // 3
        x = 110 + col * (col_w + gap)
        y = 350 + row * (card_h + 22)
        rounded(d, (x, y, x + col_w, y + card_h), 20, "#FBFAF6", outline="#D8D3C8", width=2)
        d.ellipse((x + 24, y + 26, x + 42, y + 44), fill="#B88B38")
        d.text((x + 58, y + 18), title, font=font(27, bold=True), fill=ink)
        draw_wrapped(d, (x + 25, y + 68), body, font(23), muted, col_w - 50, line_height=34, max_lines=3)

    d.text((110, 775), "02  10 个低成本假设 → 3 组聚类", font=font(34, bold=True), fill=ink)
    d.text((110, 825), "每张卡都写出一个可验证机制及其失败信号；三个簇不是同一套配色换皮。", font=font(26), fill=muted)

    clusters = [
        {
            "title": "A · 静序 / Quiet Craft",
            "color": "#899576",
            "tint": "#EEF0E8",
            "items": [
                ("H01", "纸本留白", "用偏轴栅格与大面积静区提升高级感。", "失效：像香氛或护肤模板"),
                ("H02", "酥层几何", "把酥点层理抽象成压凹与细线，不另造标。", "失效：纹样抢过现有 Logo"),
                ("H03", "一点朱印", "朱红只做日期、口味或礼序信息锚点。", "失效：落入仿古书法"),
            ],
        },
        {
            "title": "B · 日光 / Daylight System",
            "color": "#E7A92C",
            "tint": "#EEF6F7",
            "items": [
                ("H04", "日光双色", "天蓝与谷物黄以大色面建立首屏识别。", "失效：太像快消零食"),
                ("H05", "模块礼盒", "用可叠放封套与 SKU 色码形成系列。", "失效：结构显廉价"),
                ("H06", "圆形截面", "把酥点俯拍与切面放大成电商主视觉。", "失效：食物质感不够诱人"),
                ("H07", "亲和信息", "用粗细统一的几何图示解释口味与食用。", "失效：变卡通或吉祥物"),
            ],
        },
        {
            "title": "C · 炉火 / Fire & Feast",
            "color": "#8A352E",
            "tint": "#F2E9E3",
            "items": [
                ("H08", "火候光影", "用高反差暖光强调酥层、烘焙与手艺。", "失效：过暗或像夜店"),
                ("H09", "透光封套", "琥珀半透明封套制造拆礼仪式。", "失效：成本与耐用性不成立"),
                ("H10", "夜宴陈列", "深木、铜与炉口光构建现代款待场景。", "失效：红金古典奢华套式"),
            ],
        },
    ]

    cluster_y = 890
    cluster_h = 890
    for ci, cluster in enumerate(clusters):
        x = 110 + ci * (col_w + gap)
        rounded(d, (x, cluster_y, x + col_w, cluster_y + cluster_h), 26, cluster["tint"], outline=cluster["color"], width=3)
        d.rectangle((x, cluster_y, x + 16, cluster_y + cluster_h), fill=cluster["color"])
        d.text((x + 38, cluster_y + 28), cluster["title"], font=font(29, bold=True), fill=ink)
        y = cluster_y + 88
        item_h = 183
        for num, title, body, risk in cluster["items"]:
            rounded(d, (x + 32, y, x + col_w - 28, y + item_h), 18, "#FFFFFF", outline="#DAD7CF", width=2)
            draw_label(d, x + 52, y + 22, num, cluster["color"])
            d.text((x + 148, y + 24), title, font=font(29, bold=True), fill=ink)
            draw_wrapped(d, (x + 52, y + 79), body, font(22), ink, col_w - 112, line_height=31, max_lines=2)
            d.text((x + 52, y + 144), risk, font=font(19), fill=cluster["color"])
            y += item_h + 19

    d.line((110, 1870, 2290, 1870), fill="#C9C4B8", width=2)
    d.text((110, 1904), "聚类逻辑：A 用秩序年轻化｜B 用系统年轻化｜C 用叙事年轻化", font=font(25, bold=True), fill=ink)
    d.text((2290, 1904), "10 → 3", anchor="ra", font=font(25, bold=True), fill="#8B6A30")
    out = HERE / "01-conflicts-and-10-hypotheses.png"
    im.save(out, quality=95)


def draw_section(d, x, y, label, body, width, ink, accent):
    d.text((x, y), label, font=font(23, bold=True), fill=accent)
    return draw_wrapped(d, (x, y + 34), body, font(25), ink, width, line_height=36, max_lines=3)


def make_territory_board():
    W, H = 2400, 3000
    bg = "#171715"
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.text((100, 70), "03 CREATIVE TERRITORIES", font=font(28, bold=True), fill="#D1A14A")
    d.text((100, 116), "三个真正不同的品牌世界", font=font(62, bold=True), fill="#F6F2E9")
    d.text((100, 194), "低成本缩略图：验证机制与跨场景延展；Logo 与中文名原样保留，留白区等待原资产植入。", font=font(27), fill="#C5C2B9")
    draw_label(d, 1990, 88, "AWAITING CHOICE", "#D1A14A", text_fill="#171715")

    territories = [
        {
            "num": "01",
            "name": "静序新礼",
            "en": "QUIET CRAFT",
            "tagline": "让 1998 成为安静的品质底气，而不是复古装饰。",
            "bg": "#F1ECE1",
            "ink": "#24231F",
            "muted": "#5D5D55",
            "accent": "#879476",
            "image": ASSETS / "territory-01-quiet-craft-concept.png",
            "colors": ["#F3EBDD", "#25231F", "#8C9B78", "#A64A35"],
            "labels": ["米纸", "墨黑", "青釉", "小朱红"],
            "brief": "年轻来自偏轴栅格、放大切面和克制节奏；礼赠可信度来自纸张、闭合与压凹，不靠老式纹样。",
            "logo": "现有 Logo / 中文名以单色原样落在独立静区；酥层线只做背景，不与标志竞争。",
            "ecom": "4:5 主图用大静区＋一处产品宏观切面；SKU 以细线与小朱红编码，首屏稳定、二屏讲工艺。",
            "store": "米白墙、浅木、青釉色单点；用细黑分隔线与开盒陈列建立安静秩序，适合礼赠咨询。",
            "kill": "若看起来像香氛、护肤或通用米色模板，则该方向失败。",
        },
        {
            "num": "02",
            "name": "日光麦场",
            "en": "DAYLIGHT GRAIN",
            "tagline": "用明亮模块提高新客识别，把礼盒做成可组合的日常礼。",
            "bg": "#EAF3F4",
            "ink": "#202521",
            "muted": "#52605B",
            "accent": "#DF9D1F",
            "image": ASSETS / "territory-02-daylight-grain-concept.png",
            "colors": ["#A9D6E5", "#F3B33D", "#657846", "#202521"],
            "labels": ["天蓝", "谷物黄", "橄榄", "炭灰"],
            "brief": "年轻来自大色面、模块与动态裁切；礼赠属性由硬盒、封套、系列陈列和纸张质感托住。",
            "logo": "现有 Logo / 中文名原样置于干净白区；圆、弧和色块是系统图形，不生成第二标志。",
            "ecom": "4:5 主图用蓝黄高对比、圆形产品特写和大留白信息槽；SKU 色码可扩展到组合装与节庆档。",
            "store": "浅枫木＋天蓝粉末涂层金属；模块托盘、色块橱窗与可替换档期面板，日间识别最强。",
            "kill": "若包装像普通零食、儿童品牌或出现吉祥物感，则该方向失败。",
        },
        {
            "num": "03",
            "name": "炉火夜宴",
            "en": "FIRE & FEAST",
            "tagline": "把酥点的火候与层理变成当代款待仪式。",
            "bg": "#2B1A17",
            "ink": "#F4E8D8",
            "muted": "#C7B3A4",
            "accent": "#DF8C35",
            "image": ASSETS / "territory-03-fire-feast-concept.png",
            "colors": ["#7E2F2A", "#211916", "#D8862E", "#EFE2CD"],
            "labels": ["漆褐", "近黑", "琥珀", "羊皮纸"],
            "brief": "年轻来自电影式光影、强裁切和食物欲望；礼赠可信度来自沉甸盒型、透光封套与拆礼节奏。",
            "logo": "现有 Logo / 中文名原样置于浅色牌面；所有光影与层理退居为叙事，不改标志结构。",
            "ecom": "4:5 主图以近黑底、暖光切面和琥珀带制造停留；后续帧可依次讲层数、火候与礼盒开启。",
            "store": "深木、拉丝铜、琥珀树脂和炉口般的发光框；适合晚间橱窗、节庆礼台与试吃仪式。",
            "kill": "若滑向红金仿古、黑金泛奢华或过暗夜店感，则该方向失败。",
        },
    ]

    row_y = [270, 1110, 1950]
    row_h = 780
    for territory, y in zip(territories, row_y):
        rounded(d, (80, y, 2320, y + row_h), 30, territory["bg"], outline=territory["accent"], width=3)
        d.text((110, y + 45), territory["num"], font=font(30, bold=True), fill=territory["accent"])
        d.text((175, y + 32), territory["name"], font=font(48, bold=True), fill=territory["ink"])
        d.text((485, y + 50), territory["en"], font=font(24, bold=True), fill=territory["accent"])
        d.text((740, y + 47), territory["tagline"], font=font(25), fill=territory["muted"])

        src = Image.open(territory["image"]).convert("RGB")
        fitted = ImageOps.fit(src, (1080, 565), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        im.paste(fitted, (110, y + 130))
        d.rectangle((110, y + 130, 1190, y + 695), outline="#FFFFFF", width=3)
        d.text((110, y + 713), "包装 / 淘宝 / 门店 · 概念缩略图，非最终设计", font=font(21), fill=territory["muted"])

        tx = 1250
        draw_palette(d, tx, y + 120, territory["colors"], territory["labels"], dark_text=territory["muted"])
        sy = y + 225
        sy = draw_section(d, tx, sy, "回应 BRIEF", territory["brief"], 990, territory["ink"], territory["accent"]) + 16
        sy = draw_section(d, tx, sy, "LOGO 锁定策略", territory["logo"], 990, territory["ink"], territory["accent"]) + 16
        sy = draw_section(d, tx, sy, "淘宝主图延展", territory["ecom"], 990, territory["ink"], territory["accent"]) + 16
        sy = draw_section(d, tx, sy, "门店物料延展", territory["store"], 990, territory["ink"], territory["accent"]) + 14
        rounded(d, (tx, y + 688, 2275, y + 742), 12, territory["accent"])
        d.text((tx + 18, y + 701), "KILL CRITERION · " + territory["kill"], font=font(20, bold=True), fill="#FFFFFF" if territory["num"] != "02" else "#18221D")

    rounded(d, (80, 2795, 2320, 2915), 26, "#F4F0E7", outline="#D1A14A", width=3)
    d.text((115, 2822), "选择关口", font=font(30, bold=True), fill="#8B6427")
    d.text((300, 2817), "请选择 01 / 02 / 03 作为主方向；未选择前不进入 Logo 落位、版式定稿或物料精修。", font=font(29, bold=True), fill="#24231F")
    d.text((100, 2950), "现阶段缺口：中文品牌名与 Logo 矢量源文件、实际 SKU / 产品图、门店尺寸与淘宝交付规格。", font=font(23), fill="#C5C2B9")

    out = HERE / "02-three-creative-territories.png"
    im.save(out, quality=95)


if __name__ == "__main__":
    make_hypothesis_board()
    make_territory_board()
    print(HERE / "01-conflicts-and-10-hypotheses.png")
    print(HERE / "02-three-creative-territories.png")
