import { defineConfig } from "@playwright/test";

// Performance run (design 06 UI-12, UI-16 to UI-18): 1,000 synthetic 30 minute activities plus one
// 3 h, 1 Hz recording. Seeding takes about a minute and is reused while build/perf-data/seed.json exists.
const PORT = 8792;
const ROOT = "build/perf-data";

export default defineConfig({
  testDir: "e2e",
  testMatch: "perf.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 300_000,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    locale: "en-GB",
    timezoneId: "Europe/London",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  },
  webServer: {
    cwd: "..",
    command: `( test -f ${ROOT}/seed.json || ( rm -rf ${ROOT} && mkdir -p ${ROOT} && uv run --offline python tests/e2e_seed.py ${ROOT} --perf 1000 ) ) && ` +
      `OCS_DATA_ROOT=${ROOT} OCS_PORT=${PORT} uv run --offline python -m backend.api`,
    url: `http://127.0.0.1:${PORT}/api/system`,
    reuseExistingServer: false,
    timeout: 600_000,
  },
});
