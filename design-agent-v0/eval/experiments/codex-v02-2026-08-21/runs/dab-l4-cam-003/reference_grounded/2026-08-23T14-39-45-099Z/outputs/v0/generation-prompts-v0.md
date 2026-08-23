# MORI v0 视觉生成提示词

生成模式：内置图像生成工具；用途分类：`ads-marketing`。生成对象均为无文字、无产品的品牌化底图，最终产品与文字采用确定性合成。

## 天猫首图底图

```text
Asset type: 天猫首图 1:1 square campaign backdrop, background only
Reference roles: MORI brand board supplies palette and calm brand tokens; Candidate A is the selected evaluation direction and supplies only the quiet editorial hierarchy; Candidate B is rejected and must not influence the output; the product image supplies only reserved placement, scale and lighting context.
Primary request: Create a refined empty MORI e-commerce backdrop that clearly extends selected direction A, not a third direction.
Scene/backdrop: warm ivory studio wall and surface, subtle paper grain, restrained translucent sage shadow, faint powder-blue daylight wash, one small muted-terracotta accent.
Composition: large clean product zone in the lower middle, generous headline space upper left, small badge zone upper right, mobile-first hierarchy.
Mood: soft diffused morning light, calm, premium, tactile, low contrast.
Constraints: background only; no product, vessel, props, text, letters, logo, icon or watermark; do not copy reference wording.
Avoid: dense geometry, saturated navy, bright coral, hard grids, busy patterns or a third visual direction.
```

## 详情页首屏底图

```text
Asset type: 天猫详情页首屏 portrait 3:4 campaign backdrop, background only
Reference roles: same locked brand palette and selected direction A; square hero backdrop is the continuity reference; product image supplies only placement, scale and lighting context.
Primary request: Create a matching empty portrait backdrop for the first mobile detail-page screen, directly extending the square backdrop.
Scene/backdrop: warm ivory wall and tabletop, subtle paper grain, soft sage botanical shadow along one edge, faint powder-blue wash, restrained terracotta accent.
Composition: clear headline zone at top, uncluttered product zone in center, quiet lower information band for three items and one CTA, wide safe margins.
Mood: calm, natural, premium, low contrast.
Constraints: background only; no product, props, text, letters, logo, icon or watermark; no copied reference wording.
Avoid: dense poster geometry, saturated navy, bright coral, hard grid, busy pattern or a third visual direction.
```

## 确定性合成约束

- 品牌色：`#393937`, `#EEE9D5`, `#879466`, `#AF543F`, `#B7D2D9`。
- 产品：附件原图 RGB 保持不变，仅把近白背景转换为透明度，再等比缩放与放置。
- 成品文案：全部为本次原创；不复用候选稿文字，也不添加未提供的价格、促销或功能参数。
