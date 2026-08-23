from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "v1/assets/territory-02-daylight-grain-refined.png"
OUT = HERE / "01-store-signage-v3.png"
SOURCE_CROP = HERE / "assets/store-signage-v1-source-crop.png"

# Exact 4:5 crop from the approved v1 retail panel.
# No generated pixels, copy, labels, prices, or promotional elements are added.
CROP_BOX = (1024, 256, 1536, 896)


def main():
    source = Image.open(SOURCE).convert("RGB")
    crop = source.crop(CROP_BOX)
    SOURCE_CROP.parent.mkdir(parents=True, exist_ok=True)
    crop.save(SOURCE_CROP)
    review = crop.resize((1200, 1500), Image.Resampling.LANCZOS)
    review.save(OUT, quality=95)
    print(OUT)
    print(SOURCE_CROP)


if __name__ == "__main__":
    main()
