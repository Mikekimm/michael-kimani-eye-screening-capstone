import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// WCAG 2.1 A/AA audit (axe-core) of every screen, signed in as each role, with real content on the page.
// Lighthouse can only audit the public sign-in page; this covers the rest.

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "..", "..", "docs", "accessibility");
const PASSWORD = process.env.E2E_PASSWORD!;
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

interface PageResult { role: string; route: string; violations: { id: string; impact: string | null; nodes: number; help: string }[] }

/** Audits `route`, or the page as it currently is when `route` starts with "(" (e.g. a wizard step). */
async function audit(page: Page, role: string, route: string, results: PageResult[]) {
  if (!route.startsWith("(")) await page.goto(route);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(300); // let skeletons resolve
  const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  results.push({ role, route, violations: violations.map((v) => ({ id: v.id, impact: v.impact ?? null, nodes: v.nodes.length, help: v.help })) });
}

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  if (page.url().endsWith("/consent")) {
    await page.getByLabel("I understand and will follow local referral guidance.").check();
    await page.getByRole("button", { name: "Continue" }).click();
  }
}

test("every screen meets WCAG 2.1 A/AA checks (axe-core)", async ({ page, browser }, info) => {
  test.skip(!["mobile-chromium", "desktop-chromium"].includes(info.project.name), "audited on Chromium mobile and desktop");
  test.setTimeout(180_000);
  const results: PageResult[] = [];
  const suffix = info.project.name === "mobile-chromium" ? "m" : "d";

  for (const route of ["/login", "/signup"]) await audit(page, "public", route, results);

  // Health worker with real data: a patient, a screening and a referral.
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("A11y Nurse");
  await page.getByLabel("Email").fill(`a11y.nurse.${suffix}@example.org`);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL("**/consent");
  await audit(page, "health_worker", "/consent", results);
  await page.getByLabel("I understand and will follow local referral guidance.").check();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.goto("/patients/new");
  await page.getByLabel("Patient code").fill(`A11Y-${suffix.toUpperCase()}-01`);
  await page.getByRole("button", { name: "Register patient" }).click();
  await page.waitForURL(/\/patients\/[0-9a-f]{32}$/);
  const patientPath = new URL(page.url()).pathname;
  await page.goto(`/screen?patient=${patientPath.split("/").pop()}`);
  await page.getByRole("button", { name: /Continue with/ }).click();
  await page.getByRole("button", { name: "Left eye" }).click();
  await page.locator('input[type="file"][accept="image/jpeg,image/png"]').setInputFiles(path.join(here, "fixtures", "synthetic-fundus.jpg"));
  await expect(page.getByAltText("Captured fundus photo preview")).toBeVisible();
  await audit(page, "health_worker", "(screen: capture step with preview)", results);
  await page.getByRole("button", { name: "Analyse photo" }).click();
  await page.waitForURL("**/screenings/*");
  const screeningPath = new URL(page.url()).pathname;
  const refer = page.getByRole("button", { name: "Refer to a specialist anyway" });
  if (await refer.isVisible()) await refer.click();
  for (const route of ["/", "/patients", "/patients/new", patientPath, screeningPath, "/history", "/about"]) {
    await audit(page, "health_worker", route, results);
  }

  // Specialist and admin in fresh sessions.
  const { viewport, userAgent, deviceScaleFactor, isMobile, hasTouch, baseURL } = info.project.use;
  const newSession = async () =>
    (await browser.newContext({ viewport, userAgent, deviceScaleFactor, isMobile, hasTouch, baseURL })).newPage();
  const specialist = await newSession();
  await signIn(specialist, process.env.E2E_SPECIALIST_EMAIL!);
  for (const route of ["/reviews", `/reviews/${screeningPath.split("/").pop()}`]) await audit(specialist, "specialist", route, results);
  const admin = await newSession();
  await signIn(admin, process.env.E2E_ADMIN_EMAIL!);
  for (const route of ["/admin/analytics", "/admin/users"]) await audit(admin, "admin", route, results);

  mkdirSync(OUT, { recursive: true });
  writeFileSync(path.join(OUT, `axe-${info.project.name}.json`), JSON.stringify({
    measured_at: new Date().toISOString(), tool: "axe-core via @axe-core/playwright 4.10.1", tags: TAGS,
    pages: results.length, total_violations: results.reduce((n, r) => n + r.violations.length, 0), results,
  }, null, 2) + "\n");

  const serious = results.flatMap((r) => r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${r.role} ${r.route}: ${v.id} (${v.impact}, ${v.nodes} nodes) ${v.help}`));
  console.log(`${results.length} pages audited; serious/critical: ${serious.length}`);
  expect(serious, serious.join("\n")).toEqual([]);
});
