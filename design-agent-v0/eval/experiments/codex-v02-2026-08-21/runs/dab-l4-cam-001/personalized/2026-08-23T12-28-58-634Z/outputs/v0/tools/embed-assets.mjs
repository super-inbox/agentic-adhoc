import fs from "node:fs";
import path from "node:path";

const workspace = "/private/var/folders/l_/05d4s2wx2r553r67w2zvqng40000gn/T/codex-v02-1YLHlo";
const source = path.join(workspace, "outputs/v0/mori-kv-territories-v0.svg");
const destination = path.join(workspace, "outputs/v0/mori-kv-territories-v0-self-contained.svg");

const assets = new Map([
  ["../../inputs/01-brand_guideline.png", path.join(workspace, "inputs/01-brand_guideline.png")],
  ["../../inputs/02-launch_product.png", path.join(workspace, "inputs/02-launch_product.png")],
  ["assets/territory-a-tactile-dusk-bg.png", path.join(workspace, "outputs/v0/assets/territory-a-tactile-dusk-bg.png")],
  ["assets/territory-b-quiet-measure-bg.png", path.join(workspace, "outputs/v0/assets/territory-b-quiet-measure-bg.png")],
  ["assets/territory-c-night-landing-bg.png", path.join(workspace, "outputs/v0/assets/territory-c-night-landing-bg.png")],
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
