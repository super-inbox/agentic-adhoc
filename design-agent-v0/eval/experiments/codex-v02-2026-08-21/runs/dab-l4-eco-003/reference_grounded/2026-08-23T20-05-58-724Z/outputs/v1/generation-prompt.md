# v1 局部编辑提示词

使用模式：内置 imagegen，`precise-object-edit`。

```text
Use case: precise-object-edit
Asset type: revised Taobao mobile product-detail first screen, version v1
Input images: the most recent image is the sole edit target and the approved v0 first screen.
Primary request: edit only the lower benefits panel. Remove the middle benefit "定时关闭" with its clock icon, remove the right benefit "陶土触感" with its hand-and-vessel icon, and remove both vertical divider lines. Keep the existing left low-noise line icon and its exact label "低噪运行", then move that existing icon-label group horizontally to the center of the same lower warm-cream panel. Keep its original scale, line style, colors, typography, and vertical position.
Text (verbatim, exactly once each and no other text): "让香气慢下来" "低噪运行"
Constraints: preserve everything else exactly. The entire image from the top edge through the headline must remain unchanged: same 3:4 canvas, top terracotta rule, warm-cream paper-textured background, all curved tonal background shapes, platform seam, shadows, exact diffuser position, scale, terracotta color, silhouette, lid geometry, black gap, round front button, camera angle, lighting, and headline placement and typography. Preserve the lower panel's warm-cream background, height, margins, and bottom terracotta band unchanged. Do not redraw, move, resize, recolor, relight, or restyle the product or background. Do not change any Chinese character.
Avoid: any new benefit, new icon, extra copy, divider lines, changes above the benefits panel, background redesign, product drift, watermark.
```

生成后采用像素锁定合成：沿 v0 的卖点区边界，仅替换第 1059–1385 行；第 0–1058 行及第 1386–1447 行直接保留 v0 像素。

