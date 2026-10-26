import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

// Throwaway credentials for the disposable e2e database only (data/e2e.db is recreated each run).
const E2E = {
  E2E_PASSWORD: "e2e-only-Passw0rd!",
  E2E_ADMIN_EMAIL: "admin.e2e@example.org",
  E2E_SPECIALIST_EMAIL: "specialist.e2e@example.org",
  E2E_SEEDED_WORKER_EMAIL: "seeded.worker.e2e@example.org",
};
Object.assign(process.env, E2E);

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..");
const python = path.join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: { baseURL: "http://localhost:4174", trace: "retain-on-failure" },
  projects: [
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: `"${python}" "${path.join(repo, "scripts", "e2e_server.py")}"`,
      url: "http://127.0.0.1:8001/api/health",
      timeout: 120_000,
      reuseExistingServer: false,
      env: E2E,
    },
    {
      command: "npx vite build && npx vite preview --port 4174 --strictPort",
      url: "http://localhost:4174",
      timeout: 180_000,
      reuseExistingServer: false,
      env: { E2E_API_TARGET: "http://127.0.0.1:8001" },
    },
  ],
});
