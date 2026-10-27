import { expect, type Page } from "@playwright/test";

// Shared steps for the end-to-end specs. Credentials are the throwaway ones from playwright.config.ts.
const PASSWORD = process.env.E2E_PASSWORD!;
const ADMIN = process.env.E2E_ADMIN_EMAIL!;

/** Fills the public sign-up form and checks the account is left waiting for an administrator. */
export async function signUp(page: Page, fullName: string, email: string, role: "health_worker" | "specialist" = "health_worker") {
  await page.goto("/signup");
  await page.getByLabel("Full name").fill(fullName);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("I am requesting access as").selectOption(role);
  await page.getByLabel("Health facility").fill("E2E Health Centre");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Waiting for administrator approval")).toBeVisible();
}

/** What a clinic administrator does on the Users page, done through the API to keep journeys short. */
export async function approveAsAdmin(page: Page, email: string) {
  const login = await page.request.post("/api/auth/login", { data: { email: ADMIN, password: PASSWORD } });
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const users: { id: string; email: string }[] = await (await page.request.get("/api/admin/users", { headers: auth })).json();
  const user = users.find((u) => u.email === email.toLowerCase());
  expect(user, `pending account ${email}`).toBeTruthy();
  const approved = await page.request.patch(`/api/admin/users/${user!.id}`, { headers: auth, data: { status: "approved" } });
  expect(approved.status()).toBe(200);
}

export async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

export async function acceptConsentIfAsked(page: Page) {
  if (page.url().endsWith("/consent")) {
    await page.getByLabel("I understand and will follow local referral guidance.").check();
    await page.getByRole("button", { name: "Continue" }).click();
  }
}

/** Registers a patient and returns the code the app generated for them. */
export async function registerPatient(page: Page, yearOfBirth?: string): Promise<{ id: string; code: string }> {
  await page.goto("/patients/new");
  if (yearOfBirth) await page.getByLabel("Year of birth").fill(yearOfBirth);
  await page.getByRole("button", { name: "Register patient" }).click();
  await page.waitForURL(/\/patients\/[0-9a-f]{32}$/);
  const code = (await page.getByTestId("new-patient-code").textContent())?.trim() ?? "";
  expect(code).toMatch(/^PHC-[2-9A-HJKMNP-TV-Z]{6}$/);
  return { id: page.url().split("/").pop()!, code };
}

/** Screen step 3: choose a photo, confirm consent and press Analyse. */
export async function analysePhoto(page: Page, file: string) {
  await page.locator('input[type="file"][accept="image/jpeg,image/png"]').setInputFiles(file);
  await expect(page.getByAltText("Captured fundus photo preview")).toBeVisible();
  await page.getByLabel(/The patient agreed/).check();
  await page.getByRole("button", { name: "Analyse", exact: true }).click();
}

/** On a result page: "Ask a specialist" with a question. */
export async function askSpecialist(page: Page, question: string) {
  await page.getByRole("button", { name: "Ask a specialist" }).click();
  await page.getByLabel("Your question for the specialist").fill(question);
  await page.getByRole("button", { name: "Send to specialist" }).click();
  await expect(page.getByTestId("status-label").first()).toHaveText("Awaiting specialist");
}

