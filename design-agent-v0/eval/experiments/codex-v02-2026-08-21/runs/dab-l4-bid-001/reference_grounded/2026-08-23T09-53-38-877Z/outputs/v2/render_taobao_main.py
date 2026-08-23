from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "assets/taobao-main-clean-background.png"
OUT = HERE / "01-taobao-main-v2.png"
FONT_PATH = "/opt/X11/share/system_fonts/Hiragino Sans GB.ttc"


def main():
    source = Image.open(SOURCE).convert("RGB")
    canvas = ImageOps.fit(
        source,
        (1200, 1500),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    draw = ImageDraw.Draw(canvas)

    # Single factual selling-point sentence derived only from supplied brand facts.
    copy = "始于 1998，中式酥点成礼。"
    copy_font = ImageFont.truetype(FONT_PATH, size=47, index=2)
    ink = "#202521"
    grain = "#E4A32C"

    # Keep the approved upper-left identity area and all product crops untouched.
    # Place one unboxed line in the central copy-safe area; no price or promotion UI.
    x, y = 500, 735
    draw.rounded_rectangle((x, y - 28, x + 112, y - 20), radius=4, fill=grain)
    draw.text((x, y), copy, font=copy_font, fill=ink)

    canvas.save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
