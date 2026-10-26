import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

// Times the real screening round trip (upload -> server quality gate + LiteRT inference -> result card)
// as a user experiences it, with and without an emulated low-end phone on a slow network.
// Emulation uses Chrome DevTools Protocol, so this file runs on Chromium only. It is EMULATION,
// not a measurement on a physical low-end device.

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "..", "..", "docs", "benchmarks");
const PASSWORD = process.env.E2E_PASSWORD!;
const RUNS = 3;

const PROFILES = {
  "no-throttling": null,
  "low-end-phone-slow-3g": { cpuRate: 6, latencyMs: 400, downKbps: 400, upKbps: 400 },
} as const;

async function prepare(page: Page, email: string, code: string) {
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Perf Nurse");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("I understand and will follow local referral guidance.").check();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.goto("/patients/new");
  await page.getByLabel("Patient code").fill(code);
  await page.getByRole("button", { name: "Register patient" }).click();
  await expect(page.getByRole("heading", { name: code })).toBeVisible();
  return page.url().split("/").pop()!;
}

test("screening round trip: normal vs emulated low-end phone on slow 3G", async ({ page, browserName }, info) => {
  test.skip(browserName !== "chromium" || info.project.name !== "mobile-chromium", "CDP throttling: one Chromium project only");
  test.setTimeout(240_000);
  const patientId = await prepare(page, "perf.nurse@example.org", "PERF-0001");
  const cdp = await page.context().newCDPSession(page);
  const results: Record<string, number[]> = {};

  for (const [name, profile] of Object.entries(PROFILES)) {
    if (profile) {
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: profile.cpuRate });
      await cdp.send("Network.enable");
      await cdp.send("Network.emulateNetworkConditions", {
        offline: false, latency: profile.latencyMs,
        downloadThroughput: (profile.downKbps * 1024) / 8, uploadThroughput: (profile.upKbps * 1024) / 8,
      });
    }
    results[name] = [];
    for (let i = 0; i < RUNS; i++) {
      await page.goto(`/screen?patient=${patientId}`);
      await page.getByRole("button", { name: "Continue with PERF-0001" }).click();
      await page.getByRole("button", { name: i % 2 ? "Right eye" : "Left eye" }).click();
      await page.locator('input[type="file"][accept="image/jpeg,image/png"]').setInputFiles(path.join(here, "fixtures", "synthetic-fundus.jpg"));
      const start = Date.now();
      await page.getByRole("button", { name: "Analyse photo" }).click();
      await expect(page.getByTestId("result-dr")).toContainText("Estimated severity band", { timeout: 60_000 });
      results[name].push(Date.now() - start);
    }
  }

  const summary = Object.fromEntries(Object.entries(results).map(([k, v]) => {
    const sorted = [...v].sort((a, b) => a - b);
    return [k, { runs_ms: v, median_ms: sorted[Math.floor(sorted.length / 2)] }];
  }));
  mkdirSync(OUT, { recursive: true });
  appendFileSync(path.join(OUT, "browser-timings.jsonl"), JSON.stringify({
    measured_at: new Date().toISOString(), browser: `${browserName} (${info.project.name})`,
    image: "synthetic-fundus.jpg (512x512, 44 KB)", profiles: PROFILES, summary,
  }) + "\n");
  console.log(JSON.stringify(summary));
  expect(summary["no-throttling"]!.median_ms).toBeLessThan(5_000);
});
