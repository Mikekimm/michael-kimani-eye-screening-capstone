// Renders docs/diagrams/src/*.mmd to docs/diagrams/*.png with Mermaid inside local Chromium.
// Usage (from frontend/): node scripts/render-diagrams.mjs
// Only the Mermaid library is downloaded (pinned version); diagram text never leaves the machine.
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(here, "../../docs/diagrams/src");
const OUT = path.resolve(here, "../../docs/diagrams");
const MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.min.js";

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1600, height: 1200 } });
await page.setContent(`<html><body style="margin:0;background:#fff"><div id="out"></div></body></html>`);
await page.addScriptTag({ url: MERMAID });
await page.evaluate(() => window.mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" }));

for (const file of (await readdir(SRC)).filter((f) => f.endsWith(".mmd")).sort()) {
  const name = path.basename(file, ".mmd");
  const text = await readFile(path.join(SRC, file), "utf8");
  await page.evaluate(async ({ name, text }) => {
    const { svg } = await window.mermaid.render(`d-${name}`, text);
    document.getElementById("out").innerHTML = svg;
  }, { name, text });
  await page.locator("#out svg").screenshot({ path: path.join(OUT, `${name}.png`) });
  console.log(`rendered ${name}.png`);
}
await browser.close();
