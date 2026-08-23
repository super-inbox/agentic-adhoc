# Image generation record｜v3

Mode: built-in image generation tool.  
Use case: `precise-object-edit`.  
Edit target: `outputs/v0/luna-club-acrylic-mockup-study-02.png`.  
Identity reference: `inputs/01-ip_artwork.png`.

## Selected final prompt

```text
Use case: precise-object-edit
Asset type: v3 client-review acrylic standee mockup
Input images: Image 1 is the approved mockup and exact geometry/composition edit target. Image 2 is the approved artwork master and exact identity reference.
Primary request: edit only the separate horizontal base surface finish in Image 1. Preserve its exact existing outline, low height, apparent thickness, corner radii, footprint, placement, connection point, and perspective. Change the base from polished clear acrylic to HIGH-TRANSMITTANCE LIGHTLY FROSTED TRANSPARENT acrylic: a very fine even satin haze that softens reflections while the tabletop tone and light remain visibly but diffusely transmitted through it. It must read as transparent frosted acrylic, not milky white plastic.
Constraints: every region above the base must remain unchanged. Keep the upright body polished optically clear, not frosted. Preserve the exact crescent and star silhouette, white border, navy gradient, yellow lettering, exact verbatim text “LUNA CLUB”, colors, scale, position, sharpness, and clear edge. Keep the camera, crop, studio background, lighting direction, contact shadow, and product scale unchanged. No geometry changes anywhere. No added supports, slot details, labels, dimensions, watermark, props, or text.
Avoid: opaque or near-opaque base; white base; gray base; colored tint; thicker/taller base; altered ellipse or footprint; frosted upright body; artwork drift; changed lettering; changed scene.
```

## Rejected study 01 prompt

```text
Use case: precise-object-edit
Asset type: v3 client-review acrylic standee product mockup
Input images: Image 1 is the current approved mockup and the edit target. Image 2 is the approved artwork master and identity reference; its crescent, star, white border, navy artwork, yellow lettering, silhouette, and exact verbatim text “LUNA CLUB” must remain unchanged.
Primary request: change only the material appearance of the separate horizontal base in Image 1 from polished optically clear acrylic to neutral frosted transparent acrylic. The base must remain translucent and light-transmitting, with fine even satin diffusion, softened highlights, and visibly frosted faces; it must not become opaque, white, gray, colored, or heavily textured.
Constraints: keep the base geometry, size, corner radii, thickness, position, slot/connection location, camera angle, composition, background, lighting direction, contact shadow, and product scale unchanged. Keep the upright illustrated body as polished clear acrylic with exactly the same shape, edge clarity, print, colors, text, position, and proportions. Change no other region. Do not redraw, re-typeset, crop, distort, add, remove, or restyle the LUNA CLUB artwork. No new objects, labels, dimension marks, watermark, or production annotations.
Avoid: frosted upright body; milky opaque base; colored tint; changed base shape; enlarged base; altered lettering; extra supports; added texture outside the base; changed scene or framing.
```

Study 01 was retained as a non-selected process image because its base appeared too opaque and visually thick.
