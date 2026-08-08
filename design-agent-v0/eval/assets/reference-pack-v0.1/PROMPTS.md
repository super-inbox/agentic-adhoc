# Reference Pack v0.1 — generation prompts

Generated on 2026-08-07 with the built-in image generation tool. The only reused asset is
`design-vote/mens-grooming-abcd.png`, copied from the existing Design Agent demo.

## `image-edit/poster-summer-form.png`

```text
Use case: ads-marketing
Asset type: editable poster reference fixture for a multimodal design-agent evaluation
Primary request: create a polished vertical poster for an independent summer design market
Scene/backdrop: warm off-white paper texture with a restrained cobalt blue and coral geometric system
Subject: clear typographic poster with one oversized headline, small event details, simple abstract circular logo, and a product-like paper object
Style/medium: premium contemporary Swiss editorial graphic design, realistic printed poster mockup shown front-on
Composition/framing: portrait 4:5, full poster visible, generous safe margins; headline centered in upper half; small circular logo in lower right corner
Text (verbatim): "SUMMER FORM", "Design Market", "08—10 AUG", "BROOKLYN"
Constraints: render each requested text exactly once and legibly; make the headline and logo easy to detect and edit; original design; no other text; no trademarks; no watermark
Avoid: tilted perspective, hands, busy background, tiny illegible text
```

## `design-vote/noma-logo-options.png`

```text
Use case: logo-brand
Asset type: four-option logo comparison board for a multimodal design-agent evaluation
Primary request: create four distinct original minimal logo concepts for a fictional contemporary home-goods brand named "NOMA"
Style/medium: clean vector-like flat logo marks, black and warm terracotta on an off-white background
Composition/framing: landscape comparison board, four equal columns, each option centered with generous spacing
Text (verbatim): "A", "B", "C", "D", "NOMA"
Constraints: label the four columns A, B, C, D in order; show the word NOMA once beneath each mark; strong distinct silhouettes; no mockups, no 3D, no trademarks, no watermark, no extra text
```

## `tryon/synthetic-adult-selfie.png`

```text
Use case: photorealistic-natural
Asset type: synthetic person reference for virtual try-on evaluation
Primary request: a clearly adult East Asian man taking a neutral full-body self portrait for a clothing try-on tool
Scene/backdrop: plain light-gray studio wall and pale wood floor
Subject: fictional adult man approximately 28 years old, relaxed neutral expression, short dark hair, standing straight with arms slightly away from torso, wearing a fitted plain white T-shirt and straight black trousers
Style/medium: photorealistic natural smartphone photo with realistic skin and fabric texture
Composition/framing: full body head-to-toe, front-facing, portrait 4:5, centered with generous margins
Lighting/mood: soft even daylight, low shadows, neutral color
Constraints: fictional synthetic adult; hands visible; body and clothing silhouette clear; no mirror or phone visible; no logos, text, watermark, accessories, or other people
```

## `tryon/sage-hoodie.png`

```text
Use case: product-mockup
Asset type: garment reference for virtual try-on evaluation
Primary request: a single unisex pullover hoodie photographed as a clean ecommerce catalog product
Scene/backdrop: seamless very light gray studio background
Subject: sage green heavyweight cotton hoodie, front view, hood up enough to show shape, long sleeves naturally spread, no model
Style/medium: photorealistic ecommerce product photography
Composition/framing: centered front-on flat-lay / invisible mannequin appearance, full garment visible with generous padding, portrait 4:5
Lighting/mood: soft even studio light
Materials/textures: realistic brushed cotton fleece, ribbed cuffs and hem
Constraints: no logos, drawstrings text, graphics, hangers, hands, watermark, or extra objects
```

## `tryon/navy-bomber-jacket.png`

```text
Use case: product-mockup
Asset type: garment reference for virtual try-on evaluation
Primary request: a single contemporary jacket photographed as a clean ecommerce catalog product
Scene/backdrop: seamless very light gray studio background
Subject: navy lightweight bomber jacket with matte silver zipper, front view, sleeves naturally spread, no model
Style/medium: photorealistic ecommerce product photography
Composition/framing: centered front-on invisible mannequin appearance, jacket fully visible with generous padding, portrait 4:5
Lighting/mood: soft even studio light
Materials/textures: realistic woven nylon, rib-knit collar cuffs and hem
Constraints: no logos, text, graphics, hangers, hands, watermark, or extra objects
```

## `factory/luna-club-sticker.png`

```text
Use case: product-mockup
Asset type: simple opaque sticker artwork for die-cut and print-production evaluation
Primary request: create a playful die-cut sticker shaped like a rounded crescent moon with a tiny star, containing the words "LUNA CLUB"
Scene/backdrop: perfectly flat solid #00ff00 chroma-key background for local background removal
Subject: one fully opaque navy and pale yellow sticker with a thick white border, clean compact silhouette
Style/medium: crisp flat vector-like print artwork
Composition/framing: centered, front-on, generous padding around the entire sticker
Text (verbatim): "LUNA CLUB"
Constraints: render text exactly once and legibly; background must be one uniform #00ff00 color with no shadows, gradients, texture, reflection, floor plane, or lighting variation; crisp edges; no holes; do not use green in the sticker; no watermark or extra objects
```

The generated chroma-key image was processed with `remove_chroma_key.py` using border auto-key,
soft matte, thresholds 12/220, and despill. The final PNG has transparent corners and an opaque
subject.

## `factory/orbit-coffee-artwork.png`

```text
Use case: productivity-visual
Asset type: flat packaging artwork reference for print-ready export evaluation
Primary request: create a clean front-and-back label artwork board for a fictional specialty coffee pouch
Scene/backdrop: plain off-white artboard
Subject: two equal rectangular label panels aligned side by side, front panel and back panel, with crop-safe margins
Style/medium: premium flat vector-like packaging graphic, deep burgundy, cream, and muted orange
Composition/framing: landscape board, orthographic front view, no physical mockup and no perspective
Text (verbatim): "ORBIT COFFEE", "NIGHT BLOOM", "250 g", "FRONT", "BACK"
Constraints: render requested text legibly; front and back artwork clearly separated; simple geometric orbit motif; sufficient blank margin for print marks; no trademarks, barcode, tiny body copy, watermark, or extra text
```

## `logo-upgrade/grain-glow-before-after.png`

```text
Use case: logo-brand
Asset type: before-and-after logo upgrade proposal board for multimodal evaluation
Primary request: show a fictional bakery brand logo before and after a professional redesign
Scene/backdrop: clean warm-white presentation board
Subject: left side old logo, right side upgraded logo for the same brand; old version is cluttered and dated, new version is minimal with a strong wheat-and-sun symbol
Style/medium: flat vector-like branding presentation
Composition/framing: landscape two-column comparison with a central divider and generous spacing
Text (verbatim): "BEFORE", "AFTER", "GRAIN & GLOW"
Constraints: spell text exactly; brand name shown under both logos; no mockups, no 3D, no other text, no trademarks, no watermark
```

## `product-retouch/teal-speaker-white-bg.png`

```text
Use case: product-mockup
Asset type: white-background source product for background-replacement evaluation
Primary request: create a clean ecommerce catalog photo of a single compact portable speaker
Scene/backdrop: seamless pure white studio background
Subject: small cylindrical portable speaker in muted teal woven fabric with a matte charcoal base, no brand
Style/medium: photorealistic ecommerce product photography
Composition/framing: centered at slight three-quarter angle, full product visible with generous padding, square crop
Lighting/mood: soft neutral studio light with a faint natural contact shadow
Materials/textures: detailed woven textile grille and matte rubber
Constraints: one product only; clean silhouette; no logo, text, watermark, props, hands, or scenery
```

## `product-retouch/perfume-bottle-source.png`

```text
Use case: product-mockup
Asset type: source product photo for glass-material retouch evaluation
Primary request: create a straightforward ecommerce source photo of one unbranded perfume bottle before premium retouching
Scene/backdrop: neutral medium-gray seamless studio background
Subject: clear rectangular glass perfume bottle with thick glass base, pale amber liquid, simple matte black cap, blank cream label
Style/medium: photorealistic product photography, competent but intentionally flat and slightly under-polished
Composition/framing: centered three-quarter view, full bottle visible with generous padding, square crop
Lighting/mood: broad soft light with restrained reflections so glass edges are visible but can be enhanced
Materials/textures: realistic transparent glass, liquid meniscus, subtle refraction
Constraints: one bottle only; no brand names, readable text, watermark, hands, flowers, or props; no dramatic luxury scene
```

## `product-retouch/adjustable-wrench-source.png`

```text
Use case: product-mockup
Asset type: source product photo for industrial-detail enhancement evaluation
Primary request: create a clean catalog source photo of one adjustable wrench before detail enhancement
Scene/backdrop: neutral light-gray seamless background
Subject: unbranded forged-steel adjustable wrench, diagonal three-quarter view, fully visible
Style/medium: photorealistic industrial ecommerce photo, accurate tool proportions
Composition/framing: centered, square crop, generous padding
Lighting/mood: soft flat studio light, moderate contrast
Materials/textures: brushed and lightly machined steel, knurled adjustment wheel, realistic tiny usage marks
Constraints: one complete tool only; no logo, engraved text, watermark, hands, packaging, rust, or extra objects
```

## `product-retouch/walnut-chair-detail.png`

```text
Use case: product-mockup
Asset type: source image for wooden-furniture material detail evaluation
Primary request: create a close product-detail photo of a modern wooden dining chair emphasizing joinery and grain
Scene/backdrop: simple warm light-gray studio setting
Subject: close three-quarter detail of the chair's curved backrest meeting the rear leg and seat, all essential joinery visible
Style/medium: photorealistic furniture ecommerce detail photography
Composition/framing: tight square crop with the connection point centered, enough context to identify a chair
Lighting/mood: soft side light, natural but not over-polished
Materials/textures: warm walnut grain, satin oil finish, precise mortise-and-tenon joinery
Constraints: one chair only; no person, decor, logo, text, watermark, scratches, or extra furniture
```

## `detail-page/quiet-ritual-reference-page.png`

```text
Use case: ui-mockup
Asset type: ecommerce product-detail-page visual reference for layout replacement evaluation
Primary request: create a polished long-form ecommerce detail-page screenshot for a fictional ceramic aroma diffuser
Scene/backdrop: clean warm-white webpage canvas
Subject: hero product image, three benefit blocks, one close material detail, and one small specification panel
Style/medium: realistic premium ecommerce web design, editorial grid, beige and charcoal palette
Composition/framing: vertical portrait page, full layout visible, strong section rhythm and usable content slots
Text (verbatim): "QUIET RITUAL", "AROMA DIFFUSER", "MIST", "LIGHT", "TIMER"
Constraints: render only the requested short labels; make the product-image and copy regions clearly separable for replacement; no browser chrome, no real brands, no watermark, no tiny fake paragraphs
```

## `detail-page/terra-diffuser-product.png`

```text
Use case: product-mockup
Asset type: user's own product source for ecommerce detail-page replacement evaluation
Primary request: create a clean ecommerce catalog photo of a fictional compact aroma diffuser that is visually distinct from a beige ceramic reference
Scene/backdrop: seamless pure white background
Subject: one low cylindrical terracotta-red metal aroma diffuser with a narrow black vent ring, a single small round button, no branding
Style/medium: photorealistic ecommerce product photography
Composition/framing: centered three-quarter view, square crop, full product visible with generous padding
Lighting/mood: soft neutral studio light with a faint contact shadow
Materials/textures: matte powder-coated metal, crisp seams
Constraints: one product only; no mist, text, logo, watermark, props, hands, or scenery
```

## `sku-system/tumbler-base.png`

```text
Use case: product-mockup
Asset type: base product source for five-color SKU generation evaluation
Primary request: create a single clean ecommerce catalog photo of a modern insulated travel tumbler
Scene/backdrop: seamless very light gray studio background
Subject: one simple matte light-gray cylindrical tumbler with a subtly tapered base, plain lid and small flip tab, no handle
Style/medium: photorealistic ecommerce product photography
Composition/framing: centered front three-quarter view, square crop, full product visible with generous padding
Lighting/mood: soft even studio lighting
Materials/textures: matte powder-coated steel and dark charcoal lid
Constraints: neutral color suitable for recoloring; one product only; no logos, text, watermark, hands, straw, props, or scenery
```

## `sku-system/mori-brand-board.png`

```text
Use case: logo-brand
Asset type: fictional brand identity board for batch ecommerce SKU generation evaluation
Primary request: create a concise identity board for a fictional personal-care brand named "MORI"
Scene/backdrop: clean off-white presentation canvas
Subject: wordmark, simple circular leaf symbol, five-color palette, primary and secondary type samples, and one small packaging pattern swatch
Style/medium: polished flat vector-like brand guideline, minimal Japanese-inspired contemporary design
Composition/framing: landscape board with a clear modular grid and generous whitespace
Text (verbatim): "MORI", "BRAND SYSTEM", "CALM DAILY CARE"
Color palette: charcoal, cream, muted moss, clay red, pale sky blue
Constraints: spell text exactly; readable hierarchy; original design; no physical mockups, no real trademarks, no watermark, no extra text
```

## `sku-system/mori-20-sku-sheet.png`

```text
Use case: productivity-visual
Asset type: twenty-SKU source catalog contact sheet for batch branded ecommerce image evaluation
Primary request: create exactly twenty distinct unbranded personal-care product source photos arranged in a precise 5-column by 4-row grid
Scene/backdrop: uniform very light gray card grid on an off-white canvas
Subject: exactly 20 product cards: pumps, tubes, jars, bottles, soaps, and refill pouches; one isolated product per card, neutral white or light-gray packaging
Style/medium: photorealistic clean ecommerce catalog contact sheet
Composition/framing: landscape 5 columns by 4 rows; consistent card size, camera angle, margins, lighting, and product scale
Text (verbatim): "SKU 01", "SKU 02", "SKU 03", "SKU 04", "SKU 05", "SKU 06", "SKU 07", "SKU 08", "SKU 09", "SKU 10", "SKU 11", "SKU 12", "SKU 13", "SKU 14", "SKU 15", "SKU 16", "SKU 17", "SKU 18", "SKU 19", "SKU 20"
Constraints: exactly twenty cards and twenty products; labels progress left-to-right, top-to-bottom; no brand logos, watermark, decorative props, people, or extra text
```
