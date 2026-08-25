# Image generation record — v2

- Mode: built-in `image_gen`
- Intent: precise-object-edit
- Edit target: middle ecommerce panel of `outputs/v1/assets/territory-02-daylight-grain-refined.png`
- Scope: Taobao main image only
- Deterministic text overlay: `outputs/v2/render_taobao_main.py`
- Final selling sentence: `始于 1998，中式酥点成礼。`

## Image edit prompt

```text
Use case: precise-object-edit
Asset type: Taobao product main image, portrait 4:5, derived only from the middle ecommerce panel of the approved v1 Daylight Grain triptych
Primary request: Isolate and adapt only the middle ecommerce scene into a clean portrait 4:5 hero image. Preserve the approved composition language exactly: warm-white negative space, pale sky-blue circular plates, one large flaky Chinese pastry entering from the lower-left, one smaller bitten pastry entering from the upper-right, crisp soft morning daylight, and one very thin grain-yellow curved edge near the lower-right. Keep the food appearance, palette, lighting, spacing, and circular crop system consistent with the v1 middle panel.
Input image: approved v1 B triptych. Use only its middle panel as the edit target and visual source. Do not include or modify the packaging panel or retail panel.
Composition/framing: 4:5 portrait; spacious central copy-safe area; no new objects and no decorative redesign.
Text: none. Leave the copy-safe area empty for deterministic typesetting later.
Constraints: remove or omit every price tag, price number, currency symbol, discount badge, sale burst, coupon, crossed-out price, promotion sticker, button, label box, multiple selling-point block, pseudo-text, Logo, wordmark, watermark, or UI element. Preserve the existing visual system and all unrelated visual features. Do not introduce a new symbol or change the gift-box/brand system.
Avoid: promotional ecommerce styling, dense information, red sale graphics, yellow price badges, influencer stickers, extra props, new palettes, dark luxury, beige spa mood.
```

## Deterministic typesetting

The clean background was fitted to `1200×1500` and received exactly one `draw.text` call with the sentence `始于 1998，中式酥点成礼。`. No price or promotional component is created in the renderer.

