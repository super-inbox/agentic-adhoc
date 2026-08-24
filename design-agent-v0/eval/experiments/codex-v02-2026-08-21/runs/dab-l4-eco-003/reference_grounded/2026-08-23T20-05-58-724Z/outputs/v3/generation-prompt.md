# v3 底部小标签编辑提示词

使用模式：内置 imagegen，`precise-object-edit`。

```text
Use case: precise-object-edit
Asset type: Taobao mobile product-detail first screen, version v3
Input images: the most recent image is the approved v2 edit target.
Primary request: add exactly one small bottom tag for the third benefit. Place a compact warm-cream rounded capsule centered horizontally inside the existing terracotta footer band at the very bottom. The capsule must contain only the exact Chinese text "陶土触感" in small, clean, charcoal sans-serif type. No icon.
Composition: keep the tag visibly subordinate to the existing centered "低噪运行" benefit. The tag should fit fully inside the existing footer band with comfortable side padding and minimal height; do not enlarge the band or turn it into a third feature column.
Text (verbatim, preserve existing text and add the new label exactly once): "让香气慢下来" "低噪运行" "陶土触感"
Constraints: change only the small tag area inside the existing bottom terracotta band. Preserve every other element exactly: canvas size, source-matched product terracotta color, product position and geometry, warm-cream background, paper texture, curved tonal shapes, top rule, platform and shadows, headline position and typography, centered low-noise icon and label, benefits-panel spacing, and footer-band height and color. Do not add "定时关闭". Do not restore a three-column feature row. No new icon, no extra copy, no watermark.
Avoid: crowded layout, large badge, full-width label, three-column structure, moving any existing text, altering product color, recoloring the background, changing the footer-band height.
```

最终稿只从生成编辑中提取圆角标签本身，并合成到 v2；标签胶囊之外全部保留 v2 像素。

