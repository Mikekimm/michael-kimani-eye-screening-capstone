import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page, type TestInfo } from "@playwright/test";

// End-to-end journeys against the real FastAPI backend and the real DR model (LiteRT).
// The uploaded image is a SYNTHETIC fixture (a textured disc): it exercises the pipeline and the UI,
// it is not a retinal photograph and its score means nothing clinically.

const PASSWORD = process.env.E2E_PASSWORD!;
const SPECIALIST = process.env.E2E_SPECIALIST_EMAIL!;
const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(here, "fixtures");
const SHOTS = path.join(here, "..", "..", "docs", "screenshots", "e2e");

const shot = (page: Page, info: TestInfo, name: string) =>
  page.screenshot({ path: path.join(SHOTS, `${info.project.name}-${name}.png`), fullPage: true });

const workerEmail = (info: TestInfo) => `nurse.${info.project.name}@example.org`;
const patientCode = (info: TestInfo) => `E2E-${info.project.name === "mobile-chromium" ? "MOB" : "DSK"}-01`;

async function acceptConsentIfAsked(page: Page) {
  if (page.url().endsWith("/consent")) {
    await page.getByLabel("I understand and will follow local referral guidance.").check();
    await page.getByRole("button", { name: "Continue" }).click();
  }
}

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await acceptConsentIfAsked(page);
}

test.describe.serial("clinical journeys", () => {
  test("health worker: sign up, register patient, screen with the real model, see history", async ({ page }, info) => {
    await page.goto("/signup");
    await page.getByLabel("Full name").fill("E2E Nurse");
    await page.getByLabel("Email").fill(workerEmail(info));
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await shot(page, info, "01-signup");
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/consent");
    await shot(page, info, "02-consent");
    await acceptConsentIfAsked(page);
    await expect(page.getByRole("heading", { name: /Hello, E2E/ })).toBeVisible();
    await shot(page, info, "03-home");

    await page.getByRole("link", { name: "New patient" }).click();
    await page.getByLabel("Patient code").fill(patientCode(info));
    await page.getByLabel("Year of birth").fill("1968");
    await page.getByLabel("Known diabetes").selectOption("yes");
    await page.getByRole("button", { name: "Register patient" }).click();
    await expect(page.getByRole("heading", { name: patientCode(info) })).toBeVisible();

    await page.locator(`a[href^="/screen?patient="]`).click(); // the patient page's Screen button, not the nav link
    await page.getByRole("button", { name: `Continue with ${patientCode(info)}` }).click();
    await page.getByRole("button", { name: "Left eye" }).click();
    await page.locator('input[type="file"][accept="image/jpeg,image/png"]').setInputFiles(path.join(FIXTURES, "synthetic-fundus.jpg"));
    await expect(page.getByAltText("Captured fundus photo preview")).toBeVisible();
    await shot(page, info, "04-capture");
    await page.getByRole("button", { name: "Analyse photo" }).click();

    await page.waitForURL("**/screenings/*");
    const dr = page.getByTestId("result-dr");
    await expect(dr).toContainText("model mobilenetv2-dr-binary-0.3");
    await expect(dr).toContainText("Estimated severity band");
    await expect(page.getByTestId("result-glaucoma")).toContainText("Model not available yet");
    await expect(page.getByTestId("result-cataract")).toContainText("Model not available yet");
    await expect(page.getByText(/not a diagnosis/i).first()).toBeVisible();
    await shot(page, info, "05-result");

    // The synthetic image may or may not be referred by the policy; make sure the specialist sees it.
    const referButton = page.getByRole("button", { name: "Refer to a specialist anyway" });
    if (await referButton.isVisible()) {
      await referButton.click();
      await expect(page.getByText("Sent to the specialist review queue.")).toBeVisible();
    }
    await expect(page.getByText("Awaiting specialist")).toBeVisible();

    await page.getByRole("link", { name: "History" }).first().click();
    await expect(page.getByText(`${patientCode(info)} · Left eye`)).toBeVisible();
    await shot(page, info, "06-history");
  });

  test("specialist: review queue, approve with note, history preserved", async ({ page }, info) => {
    await signIn(page, SPECIALIST);
    await expect(page).toHaveURL(/\/reviews$/);
    await page.getByText(`${patientCode(info)} · Left eye`).click();
    await expect(page.getByRole("heading", { name: "Case review" })).toBeVisible();
    await shot(page, info, "07-case-review");

    await page.getByLabel("Note (optional)").fill("E2E: approved after review.");
    await page.getByRole("button", { name: "Save review" }).click();
    await expect(page.getByText("Approved the screening result")).toBeVisible();

    await page.getByLabel("Decision").selectOption("comment");
    await page.getByLabel("Note", { exact: true }).fill("E2E: follow up in 12 months.");
    await page.getByRole("button", { name: "Save review" }).click();
    await expect(page.getByText('"E2E: follow up in 12 months."')).toBeVisible();
    await expect(page.getByText('"E2E: approved after review."')).toBeVisible(); // earlier entry still there
    await shot(page, info, "08-review-history");
  });

  test("unauthorized access is blocked in the UI and by the API", async ({ page }, info) => {
    await signIn(page, workerEmail(info));
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/$/); // health worker sent back to their own home
    const anonymous = await page.request.get("/api/admin/users");
    expect(anonymous.status()).toBe(401);
    const token = await page.evaluate(() => JSON.parse(localStorage.getItem("retina.tokens") ?? "{}").access_token);
    const asWorker = await page.request.get("/api/admin/users", { headers: { Authorization: `Bearer ${token}` } });
    expect(asWorker.status()).toBe(403);
  });

  test("invalid input: name-like patient code and a blank photo are rejected with clear messages", async ({ page }, info) => {
    await signIn(page, workerEmail(info));
    await page.goto("/patients/new");
    await page.getByLabel("Patient code").fill("Jane Doe");
    await page.getByRole("button", { name: "Register patient" }).click();
    await expect(page.getByText(/a clinic code, not a name/)).toBeVisible();

    await page.goto("/screen");
    await page.getByRole("button", { name: patientCode(info) }).click();
    await page.getByRole("button", { name: "Right eye" }).click();
    await page.locator('input[type="file"][accept="image/jpeg,image/png"]').setInputFiles(path.join(FIXTURES, "blank.jpg"));
    await page.getByRole("button", { name: "Analyse photo" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "cannot be screened" })).toContainText("blank or uniform");
    await shot(page, info, "09-unusable-image");
  });
});
