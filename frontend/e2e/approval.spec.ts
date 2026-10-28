import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Browser, type TestInfo } from "@playwright/test";

import { acceptConsentIfAsked, signIn, signUp } from "./helpers";

// Supervisor check: a stranger can ask for an account but cannot use it until an administrator approves it.
const SHOTS = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "screenshots", "e2e");
const PASSWORD = process.env.E2E_PASSWORD!;

/** A separate browser session with this project's device and base URL (stranger and admin side by side). */
async function session(browser: Browser, info: TestInfo) {
  const { viewport, userAgent, deviceScaleFactor, isMobile, hasTouch, baseURL } = info.project.use;
  return (await browser.newContext({ viewport, userAgent, deviceScaleFactor, isMobile, hasTouch, baseURL })).newPage();
}

async function adminSession(browser: Browser, info: TestInfo) {
  const admin = await session(browser, info);
  await signIn(admin, process.env.E2E_ADMIN_EMAIL!);
  await acceptConsentIfAsked(admin);
  await admin.goto("/admin/users");
  return admin;
}

test("fake sign-up stays pending, cannot sign in, and works only after an admin approves it", async ({ browser }, info) => {
  const email = `fake.${info.project.name}@example.org`;
  const stranger = await session(browser, info);
  await signUp(stranger, "Fake Person", email);
  await stranger.screenshot({ path: path.join(SHOTS, `${info.project.name}-10-fake-signup-pending.png`) });

  await stranger.goto("/login");
  await stranger.getByLabel("Email").fill(email);
  await stranger.getByLabel("Password", { exact: true }).fill("Wrong-password-1");
  await stranger.getByRole("button", { name: "Sign in" }).click();
  await expect(stranger.getByText("Incorrect email or password.")).toBeVisible(); // wrong password: generic message
  await stranger.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await stranger.getByRole("button", { name: "Sign in" }).click();
  await expect(stranger.getByText("Your account is waiting for administrator approval.")).toBeVisible();
  await expect(stranger).toHaveURL(/\/login$/);
  await stranger.screenshot({ path: path.join(SHOTS, `${info.project.name}-11-pending-login-refused.png`) });

  const admin = await adminSession(browser, info);
  const card = admin.locator("div.rounded-lg", { hasText: email }).last();
  await expect(card).toContainText("Requested role: Health worker");
  await expect(card).not.toContainText(/registration|Facility:/i); // sign-up collects no facility
  await card.getByLabel(/Facility for/).fill("E2E Health Centre"); // optional, set by the admin
  await admin.screenshot({ path: path.join(SHOTS, `${info.project.name}-12-admin-pending-list.png`), fullPage: true });
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByRole("button", { name: "Approve" })).toHaveCount(0);
  await expect(card).toContainText("Facility: E2E Health Centre");

  await stranger.getByRole("button", { name: "Sign in" }).click();
  await stranger.waitForURL((url) => !url.pathname.startsWith("/login"));
});

test("a second sign-up with a registered email is refused and changes nothing", async ({ browser }, info) => {
  const email = `dup.${info.project.name}@example.org`;
  const first = await session(browser, info);
  await signUp(first, "Original Name", email);

  const second = await session(browser, info);
  await second.goto("/signup");
  await second.getByLabel("Full name").fill("Different Name");
  await second.getByLabel("Email").fill(email.toUpperCase());
  await second.getByLabel("Password", { exact: true }).fill("Another-pass-2");
  await second.getByLabel("I am requesting access as").selectOption("specialist");
  await second.getByRole("button", { name: "Create account" }).click();
  await expect(second.getByRole("alert")).toContainText("already registered");

  const admin = await adminSession(browser, info);
  const cards = admin.locator("div.rounded-lg", { hasText: email });
  await expect(cards.first()).toContainText("Original Name");
  await expect(admin.getByText("Different Name")).toHaveCount(0);
  await expect(cards.last()).toContainText("Requested role: Health worker"); // not changed to specialist
  const login = await second.request.post("/api/auth/login", { data: { email, password: "Another-pass-2" } });
  expect(login.status()).toBe(401); // the second password was never stored
});

test("an administrator rejects a sign-up with a reason and the person still cannot sign in", async ({ browser }, info) => {
  const email = `reject.${info.project.name}@example.org`;
  const stranger = await session(browser, info);
  await signUp(stranger, "Unknown Person", email);

  const admin = await adminSession(browser, info);
  const card = admin.locator("div.rounded-lg", { hasText: email }).last();
  await card.getByRole("button", { name: "Reject" }).click();
  await card.getByRole("button", { name: "Confirm rejection" }).click();
  await expect(card.getByText("Give a reason.")).toBeVisible(); // a rejection always needs a reason
  await card.getByLabel(/Reason for rejecting/).fill("Not on the facility staff list.");
  await card.getByRole("button", { name: "Confirm rejection" }).click();
  await expect(card).toContainText("Rejected: Not on the facility staff list.");

  const response = await stranger.request.post("/api/auth/login", { data: { email, password: PASSWORD } });
  expect(response.status()).toBe(403);
});

test("specialist sign-up: pending, refused, approved by an admin, then only the specialist sees the review queue", async ({ browser }, info) => {
  test.setTimeout(150_000); // four browser sessions, each with an Argon2 sign-in
  const email = `specialist.${info.project.name}@example.org`;
  const applicant = await session(browser, info);
  await signUp(applicant, "Requested Specialist", email, "specialist");
  const early = await applicant.request.post("/api/auth/login", { data: { email, password: PASSWORD } });
  expect(early.status()).toBe(403); // the requested role grants nothing yet

  const admin = await adminSession(browser, info);
  const card = admin.locator("div.rounded-lg", { hasText: email }).last();
  await expect(card).toContainText("Requested role: Specialist");
  await expect(card.getByLabel(/Role to grant/)).toHaveValue("specialist");
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByRole("button", { name: "Approve" })).toHaveCount(0);

  await signIn(applicant, email);
  await acceptConsentIfAsked(applicant);
  await applicant.goto("/reviews");
  await expect(applicant.getByRole("heading", { name: "Review queue" })).toBeVisible();

  const worker = await session(browser, info);
  await signIn(worker, process.env.E2E_SEEDED_WORKER_EMAIL!);
  await acceptConsentIfAsked(worker);
  await worker.goto("/reviews");
  await expect(worker).toHaveURL(/\/$/); // a health worker is sent back to their own home
  const token = await worker.evaluate(() => JSON.parse(localStorage.getItem("retina.tokens") ?? "{}").access_token);
  expect((await worker.request.get("/api/reviews/queue", { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(403);
});

