# v0 生成提示词记录

使用模式：内置 imagegen。

## 基础生成

```text
Use case: ads-marketing
Asset type: final Taobao mobile product-detail first screen, portrait 3:4 canvas
Primary request: create a polished first-screen product detail graphic for the terracotta-red aroma diffuser, choosing the brand-first direction while abstracting only the layout rhythm of the reference page.
Input images:
- Image 1: style reference only. Abstract its spacious vertical rhythm, clear hero-to-headline-to-three-benefits hierarchy, restrained grid, and premium minimal mood. Do not reproduce its brand, product, words, exact layout, icons, or cold-white/black identity.
- Image 2: product identity and exact product reference. Place this exact product as the hero. Preserve its terracotta-red color, low cylindrical shape, flat floating circular lid, black narrow gap, centered round front button, proportions, silhouette, finish, and camera identity without redesign or recoloring.
- Image 3: brand-system reference. Follow its warm cream, terracotta red, and charcoal palette and calm-care typography; muted sage may appear only as a very small accent. Do not use a cold-white dominant palette.
Scene/backdrop: warm ivory / oatmeal studio field with soft warm tonal panels, subtle tactile paper grain, a grounded soft shadow beneath the product, no lifestyle props.
Subject: the exact terracotta-red diffuser from Image 2, large and centered in the upper-middle hero area, with ample breathing room.
Style/medium: premium editorial e-commerce art direction; clean, modern, tactile, calm; practical mobile-first layout, not a device mockup and not shown inside a phone frame.
Composition/framing: one full-bleed portrait mobile canvas. Small restrained brand-colored rule near top; product hero occupies about 48% of canvas; below it a prominent centered headline; bottom area contains three equal benefit cells in a single row with simple original thin-line symbols and large readable Chinese labels. Use clear separators and generous margins. Preserve the reference's information tempo but create a distinct composition.
Lighting/mood: soft warm diffused studio lighting; calming, quiet, refined.
Color palette: dominant warm cream #F3EAD5, terracotta red #B85A43, charcoal #2E2E2B; tiny muted sage accent #8F9B69 only if useful.
Materials/textures: product finish must stay faithful to Image 2; subtle warm paper and ceramic tactility elsewhere.
Text (verbatim, render exactly once each and no other words): "让香气慢下来" "低噪运行" "定时关闭" "陶土触感"
Typography: headline in large high-contrast elegant Chinese type, charcoal; benefit labels in clean legible sans-serif, charcoal; accurate Chinese characters, strong mobile readability.
Constraints: use the provided product and approved copy; keep product color and shape exactly unchanged; retain enough negative space; make the three selling points immediately scannable on mobile; no logos or words from Image 1; no copied reference icons; no extra product parts; no extra text; no watermark; no phone frame.
Avoid: cold clinical white, black-dominant blocks, generic tech-blue UI, tiny text, English copy, mist clouds that obscure the product, duplicated products, changing the lid or button, changing product proportions.
```

## 单点颜色校正

```text
Use case: precise-object-edit
Asset type: final Taobao mobile product-detail first screen
Input images: Image 2 is the authoritative original product-color and product-identity reference. The most recent image is the current generated mobile first-screen edit target.
Primary request: make one targeted correction only: adjust the diffuser body and lid in the current mobile first-screen so their terracotta-red hue, saturation, value, matte finish, black lid gap, button color, and product appearance match Image 2 as closely and faithfully as possible. The source product is a muted earthy clay terracotta, not a vivid orange-red.
Constraints: change only the product's color fidelity to match Image 2. Keep the product silhouette, lid geometry, black gap, centered round button, scale, position, camera angle, proportions, shadow, and edges unchanged. Keep the warm cream background, top rule, paper texture, architectural tonal shapes, headline, benefit row, icons, separators, margins, and bottom terracotta band unchanged. Preserve all Chinese text exactly and verbatim: "让香气慢下来" "低噪运行" "定时关闭" "陶土触感". No extra text, no new objects, no watermark.
Avoid: changing layout; changing typography; changing any Chinese character; changing product shape; making the product brighter, more orange, or more saturated than Image 2.
```

