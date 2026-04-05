import { defineConfig, devices } from "@playwright/test";
import path from "path";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "html",
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "python -m uvicorn src.api.main:app --port 8000",
      port: 8000,
      timeout: 60_000,
      reuseExistingServer: false,
      cwd: path.resolve(__dirname, "../backend"),
    },
    {
      command: "npm run dev -- --port 3000",
      port: 3000,
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
});
