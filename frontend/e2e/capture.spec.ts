import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { acceptConsentIfAsked, analysePhoto, registerPatient, signIn } from "./helpers";

// Capture flow on every profile (mobile and desktop widths): Cancel, a refused non-eye photo, Save and Discard.
const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(here, "fixtures");
const SHOTS = path.join(here, "..", "..", "docs", "screenshots", "e2e");

async function startScreening(page: Page) {
  await signIn(page, process.env.E2E_SEEDED_WORKER_EMAIL!);
  await acceptConsentIfAsked(page);
  const patient = await registerPatient(page);
  await page.goto(`/screen?patient=${patient.id}`);
  await page.getByRole("button", { name: /Continue with/ }).click();
  await page.getByRole("button", { name: "Left eye" }).click();
  return patient;
}

async function screeningCount(page: Page, patientId: string) {
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem("retina.tokens") ?? "{}").access_token);
  const response = await page.request.get(`/api/patients/${patientId}/screenings`, { headers: { Authorization: `Bearer ${token}` } });
  return (await response.json()).length as number;
}

test("Cancel throws the photo away; a non-eye photo is refused with Retake / Upload another and nothing is saved", async ({ page }, info) => {
  const patient = await startScreening(page);
  const file = page.locator('input[type="file"][accept="image/jpeg,image/png"]');

  await file.setInputFiles(path.join(FIXTURES, "synthetic-fundus.jpg"));
  await expect(page.getByAltText("Captured fundus photo preview")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByAltText("Captured fundus photo preview")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "From gallery" })).toBeVisible();

  await analysePhoto(page, path.join(FIXTURES, "not-a-fundus.png"));
  await expect(page.getByTestId("photo-rejected")).toContainText("does not look like a retinal fundus photograph");
  await expect(page.getByTestId("photo-rejected")).toContainText("Nothing was saved");
  await expect(page.getByRole("button", { name: "Retake" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Upload another" })).toBeVisible();
  await expect(page.getByTestId("result-dr")).toHaveCount(0);
  await page.screenshot({ path: path.join(SHOTS, `${info.project.name}-13-not-a-fundus-refused.png`) });
  expect(await screeningCount(page, patient.id)).toBe(0);

  await analysePhoto(page, path.join(FIXTURES, "synthetic-fundus.jpg")); // "Upload another" path: a usable photo
  await page.waitForURL("**/screenings/*");
  await expect(page.getByTestId("result-dr")).toBeVisible();
  expect(await screeningCount(page, patient.id)).toBe(1);
});

test("after a result, Save keeps it and Discard removes it with a reason", async ({ page }) => {
  const patient = await startScreening(page);
  await analysePhoto(page, path.join(FIXTURES, "synthetic-fundus.jpg"));
  await page.waitForURL("**/screenings/*");
  await page.getByRole("button", { name: "Save" }).click();
  await page.waitForURL("**/history");
  await expect(page.getByText("Saved to history.")).toBeVisible();

  await page.goto(`/screen?patient=${patient.id}`);
  await page.getByRole("button", { name: /Continue with/ }).click();
  await page.getByRole("button", { name: "Right eye" }).click();
  await analysePhoto(page, path.join(FIXTURES, "synthetic-fundus.jpg"));
  await page.waitForURL("**/screenings/*");
  await page.getByRole("button", { name: "Discard" }).click();
  await page.getByRole("button", { name: "Discard screening" }).click();
  await expect(page.getByText("Write at least a few words.")).toBeVisible(); // a reason is required
  await page.getByLabel("Why discard this screening?").fill("E2E: wrong eye photographed.");
  await page.getByRole("button", { name: "Discard screening" }).click();
  await page.waitForURL("**/history");
  expect(await screeningCount(page, patient.id)).toBe(1); // only the saved one is left
});
