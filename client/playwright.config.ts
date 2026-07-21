import { defineConfig } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT ?? "4200");
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${port}`;
const angularConfiguration = process.env.PLAYWRIGHT_ANGULAR_CONFIGURATION;
const configurationArgument = angularConfiguration
  ? ` --configuration ${angularConfiguration}`
  : "";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npm run start -- --host 127.0.0.1 --port ${port}${configurationArgument}`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
