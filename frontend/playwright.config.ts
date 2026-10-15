import { randomBytes } from "node:crypto";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * E2E de punta a punta: API real (base aislada `wfa_e2e`) + Next.js compilado.
 * Las credenciales del admin de prueba se generan en cada corrida si no vienen por entorno.
 */
const isWin = process.platform === "win32";
const python =
  process.env.E2E_PYTHON || path.resolve(__dirname, "../backend/.venv", isWin ? "Scripts/python.exe" : "bin/python");
const apiPort = Number(process.env.E2E_API_PORT || 8100);
const webPort = Number(process.env.E2E_WEB_PORT || 3100);
process.env.E2E_ADMIN_EMAIL ||= "admin-e2e@example.com";
process.env.E2E_ADMIN_PASSWORD ||= `E2e-${randomBytes(9).toString("base64url")}9a`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" ../backend/scripts/e2e_server.py`,
      url: `http://127.0.0.1:${apiPort}/api/health/live`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: process.env.E2E_DATABASE_URL || "postgresql+psycopg://wfa:wfa@localhost:5432/wfa_e2e",
        E2E_PORT: String(apiPort),
        E2E_ADMIN_EMAIL: process.env.E2E_ADMIN_EMAIL,
        E2E_ADMIN_PASSWORD: process.env.E2E_ADMIN_PASSWORD,
        LOG_LEVEL: "WARNING",
      },
    },
    {
      command: `npx next start -p ${webPort}`,
      url: `http://127.0.0.1:${webPort}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { API_INTERNAL_URL: `http://127.0.0.1:${apiPort}`, NEXT_TELEMETRY_DISABLED: "1" },
    },
  ],
});
