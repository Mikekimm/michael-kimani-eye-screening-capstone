import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { acceptConsentIfAsked, analysePhoto, askButton, fillAskForm, registerPatient, signIn } from "./helpers";

// Specialty routing (an extension beyond the proposal): the health worker names the conditions and the priority,
// the specialist finds the case under "My specialties", takes it, decides, and the decision comes back.
const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(here, "..", "..", "docs", "screenshots", "e2e");

test("routing loop: ask about DR (urgent) -> My specialties -> Take -> Being reviewed by -> decision returned", async ({ page, browser }, info) => {
  test.setTimeout(150_000);
  await signIn(page, process.env.E2E_SEEDED_WORKER_EMAIL!);
  await acceptConsentIfAsked(page);
  const patient = await registerPatient(page);
  await page.goto(`/screen?patient=${patient.id}`);
  await page.getByRole("button", { name: /Continue with/ }).click();
  await page.getByRole("button", { name: "Left eye" }).click();
  await analysePhoto(page, path.join(here, "fixtures", "synthetic-fundus.jpg"));
  await page.waitForURL("**/screenings/*");
  const screeningUrl = page.url();

  await askButton(page).click();
  const group = page.getByRole("group", { name: "What is your question about?" });
  for (const box of await group.getByRole("checkbox").all()) await box.uncheck();
  await group.getByLabel("Diabetic retinopathy").check();
  await fillAskForm(page, "E2E routing: is this referable DR?", "urgent");
  await page.getByRole("button", { name: "Send to specialist" }).click();
  await expect(page.getByTestId("status-label").first()).toHaveText("Awaiting specialist");
  await expect(page.getByTestId("referral-question")).toContainText("Diabetic retinopathy");
  await expect(page.getByTestId("review-waiting")).toContainText("urgent");

  const { viewport, userAgent, deviceScaleFactor, isMobile, hasTouch, baseURL } = info.project.use;
  const specialist = await (await browser.newContext({ viewport, userAgent, deviceScaleFactor, isMobile, hasTouch, baseURL })).newPage();
  await signIn(specialist, process.env.E2E_SPECIALIST_EMAIL!);
  await acceptConsentIfAsked(specialist);
  await specialist.goto("/reviews");
  await expect(specialist.getByRole("tab", { name: /My specialties/ })).toHaveAttribute("aria-selected", "true");
  const card = specialist.getByTestId("queue-card").filter({ hasText: patient.code });
  await expect(card).toContainText("E2E routing: is this referable DR?");
  await card.getByRole("button", { name: "Take this case" }).click();
  await expect(card).toContainText("Taken by you");
  await specialist.screenshot({ path: path.join(SHOTS, `${info.project.name}-14-queue-taken.png`) });

  await page.goto(screeningUrl);
  await expect(page.getByTestId("being-reviewed")).toContainText("Being reviewed by Demo Specialist");

  await card.getByRole("link").click();
  await specialist.getByLabel("Decision").selectOption("approve");
  await specialist.getByLabel("Note (optional)").fill("E2E routing: referable, refer this month.");
  await specialist.getByRole("button", { name: "Save review" }).click();
  await expect(specialist.getByText("Approved the screening result")).toBeVisible();

  // "New decisions": the history item is marked until the health worker opens the screening.
  await page.goto("/history");
  const item = page.locator("a", { hasText: `${patient.code} · Left eye` }).first();
  await expect(item.getByTestId("status-label")).toHaveText("Reviewed");
  await expect(item.getByTestId("new-decision")).toBeVisible();
  await page.goto(screeningUrl);
  await expect(page.getByTestId("status-label").first()).toHaveText("Reviewed");
  await expect(page.getByText("E2E routing: referable, refer this month.")).toBeVisible();
  await page.goto("/history");
  await expect(page.locator("a", { hasText: `${patient.code} · Left eye` }).first().getByTestId("new-decision")).toHaveCount(0);
});
