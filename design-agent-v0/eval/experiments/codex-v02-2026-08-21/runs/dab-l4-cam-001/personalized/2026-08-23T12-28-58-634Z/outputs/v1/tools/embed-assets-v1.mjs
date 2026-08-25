import fs from "node:fs";
import path from "node:path";

const workspace = "/private/var/folders/l_/05d4s2wx2r553r67w2zvqng40000gn/T/codex-v02-1YLHlo";
const source = path.join(workspace, "outputs/v1/mori-night-landing-refinement-v1.svg");
const destination = path.join(workspace, "outputs/v1/mori-night-landing-refinement-v1-self-contained.svg");

const assets = new Map([
  ["../../inputs/01-brand_guideline.png", path.join(workspace, "inputs/01-brand_guideline.png")],
  ["../../inputs/02-launch_product.png", path.join(workspace, "inputs/02-launch_product.png")],
  ["assets/territory-c-soft-side-light-bg-v1.png", path.join(workspace, "outputs/v1/assets/territory-c-soft-side-light-bg-v1.png")]
]);

let svg = fs.readFileSync(source, "utf8");
for (const [reference, assetPath] of assets) {
  const dataUri = `data:image/png;base64,${fs.readFileSync(assetPath).toString("base64")}`;
  const paired = `xlink:href="${reference}" href="${reference}"`;
  if (!svg.includes(paired)) {
    throw new Error(`Missing expected asset reference: ${reference}`);
  }
  svg = svg.replaceAll(paired, `xlink:href="${dataUri}"`);
}

fs.writeFileSync(destination, svg);
console.log(destination);

