# Image generation record｜v0

Mode: built-in image generation tool.  
Use case: `product-mockup`, followed by one `precise-object-edit`.  
Artwork master: `inputs/01-ip_artwork.png`.

## Study 01 prompt

```text
Use case: product-mockup
Asset type: client-review desktop acrylic standee mockup, explicitly non-production
Input images: Image 1 is the approved master artwork and exact front-face print insert. Preserve it exactly and do not redraw, restyle, crop, alter, re-typeset, or add to it. The crescent, star, white border, navy gradient, and the exact verbatim lettering “LUNA CLUB” must remain unchanged.
Primary request: create a polished photorealistic three-quarter product mockup of Image 1 manufactured as a small freestanding clear acrylic desk standee, approximately 90 mm overall finished height as a visual scale cue only.
Scene/backdrop: warm-light neutral gray studio tabletop with a clean soft gradient background, no props.
Subject: one acrylic character piece whose visible printed front face is exactly Image 1, seated upright in a restrained clear transparent base. The base should be visually quiet, compact, low-profile, and should not cover the artwork. Show the acrylic edge and subtle realistic refraction, but keep the artwork face-on enough to remain readable.
Style/medium: premium realistic product photography / industrial design mockup.
Composition/framing: landscape, single product centered, slight three-quarter view, generous margins, eye-level just above tabletop.
Lighting/mood: soft studio key light, controlled highlights on clear acrylic, subtle contact shadow.
Materials/textures: optically clear acrylic appearance; crisp high-fidelity UV print appearance.
Constraints: concept visualization only, not a technical drawing. Do not display any dimensions, thickness, slot width, tolerances, manufacturing callouts, extra labels, logos, watermark, packaging, or hands. Do not imply an exact acrylic thickness. Preserve every pixel-like visual feature of the approved artwork as closely as possible; do not modify unedited regions.
Avoid: oversized or colored base; opaque base; base overlapping the moon artwork; extra stars; altered spelling; perspective distortion that makes the lettering unreadable; exploded views; dimension arrows; production diagram.
```

## Study 02 refinement prompt

```text
Use case: precise-object-edit
Asset type: client-review acrylic standee concept mockup, explicitly non-production
Input images: Image 1 is the existing product mockup to refine. Image 2 is the approved artwork master that must remain visually unchanged and is the sole reference for all printed artwork.
Primary request: refine only the clear base and its visual connection in Image 1. Make the base more restrained, lower-profile, and visually quiet. Remove the two conspicuous upright clear support tabs/legs. Keep the joint visually generic and mostly hidden behind the lower edge of the artwork so it does not communicate a decided slot geometry, thickness, or tolerance.
Composition/framing: keep the same centered landscape studio product-photo composition and readable near-front three-quarter view.
Materials/textures: optically clear acrylic, realistic restrained highlights and subtle contact shadow.
Constraints: change only the base and its visible connection. Preserve the backdrop, camera, lighting, product position, and approved front artwork. The visible crescent, star, white border, navy fill/gradient, silhouette and exact verbatim text “LUNA CLUB” must match Image 2; do not redraw, restyle, crop, re-typeset, add, or omit any artwork element. Concept visualization only, not a technical drawing. Do not show or imply exact acrylic thickness, slot width, tabs, tolerances, dimension arrows, callouts, extra text, watermark, packaging, or props.
Avoid: visible structural pegs or multiple tabs; thick bulky base; colored or opaque base; base covering the artwork; altered spelling; new artwork; production diagram.
```
