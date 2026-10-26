// Renders docs/report/report.html to docs/report/report.pdf (A4) with local Chromium and checks the
// 5-page limit. Usage (from frontend/): node scripts/build-report.mjs
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = path.resolve(here, "../../docs/report/report.html");
const pdf = path.resolve(here, "../../docs/report/report.pdf");

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(html).href, { waitUntil: "networkidle" });
await page.pdf({ path: pdf, format: "A4", printBackground: true, preferCSSPageSize: true });
await browser.close();

const pages = ((await readFile(pdf)).toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? []).length;
console.log(`report.pdf: ${pages} page(s)${pages > 5 ? "  <-- OVER THE 5-PAGE LIMIT" : ""}`);
process.exit(pages > 5 ? 1 : 0);
