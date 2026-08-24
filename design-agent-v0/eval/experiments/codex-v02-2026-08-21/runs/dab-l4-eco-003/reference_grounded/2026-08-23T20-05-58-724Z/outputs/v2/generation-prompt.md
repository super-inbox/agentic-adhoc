# v2 产品颜色校正提示词

使用模式：内置 imagegen，`precise-object-edit`。

```text
Use case: precise-object-edit
Asset type: Taobao mobile product-detail first screen, version v2
Input images:
- Image 1: the approved v1 first-screen edit target.
- Image 2: the authoritative original product source and sole color reference.
Primary request: correct only the red-colored product surfaces in Image 1 so the diffuser's body, lid, and front circular button match the exact muted clay-red / red-brown terracotta hue and saturation of the product in Image 2. The current product in Image 1 reads too orange/salmon; shift it subtly away from orange toward the deeper, muted earthy terracotta red shown in Image 2.
Constraints: change color only on the existing matte terracotta surfaces of the diffuser. Preserve the product's exact position, size, silhouette, proportions, lid geometry, black narrow gap, black outlines, button geometry, camera angle, material texture, highlights, shading, contact shadow, and edges. Keep the entire warm-cream background, all paper texture and curved tonal shapes, top rule, platform, headline "让香气慢下来", centered low-noise icon and label "低噪运行", typography, spacing, benefits panel, and bottom terracotta band unchanged. No layout change, no text change, no background recoloring, no new objects, no watermark.
Avoid: orange or coral product color; changing the background warmth; moving any text; changing product geometry; recoloring the black gap or shadow; editing anything outside the product's red surfaces.
```

为严格执行“只校正产品本体颜色”，最终稿以产品源图测得的陶土红色相和饱和度为目标，仅在 v1 产品红色表面蒙版内校正；保留 v1 的明暗值、纹理、轮廓、阴影及全部非产品像素。

