import { defineConfig } from "@playwright/test";

// End to end tests against the real backend on a freshly seeded, synthetic data root.
// The server binds to 127.0.0.1 only; every test aborts and records any other request (UI-02).
const PORT = 8791;
const ROOT = "build/e2e-data";

export default defineConfig({
  testDir: "e2e",
  testIgnore: "**/perf.spec.ts",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "en-GB",
    timezoneId: "Europe/London",
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 1,
  },
  webServer: {
    cwd: "..",
    command: `rm -rf ${ROOT} && mkdir -p ${ROOT} && uv run --offline python tests/e2e_seed.py ${ROOT} && ` +
      `OCS_DATA_ROOT=${ROOT} OCS_PORT=${PORT} uv run --offline python -m backend.api`,
    url: `http://127.0.0.1:${PORT}/api/system`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
