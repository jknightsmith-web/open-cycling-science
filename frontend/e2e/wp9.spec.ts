import { readFileSync } from "node:fs";
import { expect, repoPath, seed, test, type Seed } from "./fixtures";

// WP9 in the browser: export, deletion, delete everything and restore, on the same seeded server.
// Runs after screens.spec.ts (one worker, files in name order) and changes the data root.
test.describe.configure({ mode: "serial" });
let S: Seed;
let archivePath = "";
let archived = 0;   // activities in the library when the archive was made (earlier specs may have imported more)
test.beforeAll(() => { S = seed(); });

test("WP9 export a full archive from Settings and download it", async ({ page }, info) => {
  await page.goto("/settings");
  await expect(page.getByRole("note")).toContainText("GPS");
  const row = page.getByRole("table", { name: "Export kinds" }).locator("tr", { hasText: "Full archive" });
  await row.getByRole("button", { name: "Export" }).click();
  const saved = page.getByRole("table", { name: "Saved exports" }).locator("tr[data-export]");
  await expect(saved).toHaveCount(1);
  await expect(saved).toContainText("archive");
  const [download] = await Promise.all([page.waitForEvent("download"), saved.getByRole("link").click()]);
  archivePath = info.outputPath("archive.zip");
  await download.saveAs(archivePath);
  expect(readFileSync(archivePath).subarray(0, 2).toString()).toBe("PK");
  archived = (await (await page.request.get("/api/activities")).json()).total;
  expect(archived).toBeGreaterThanOrEqual(5);
});

test("WP9 delete one recording after a confirmation that lists what goes", async ({ page }) => {
  await page.goto(`/activities/${S.low_coverage}`);
  await page.getByRole("button", { name: "Delete this recording" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Confirm deletion" });
  await expect(dialog).toContainText("half_power.fit");
  await expect(dialog).toContainText("Exports in the data folder that contain it");
  await dialog.getByRole("button", { name: "Delete permanently" }).click();
  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByRole("status")).toHaveText("The recording was deleted.");
  await expect(page.locator(`tr[data-activity="${S.low_coverage}"]`)).toHaveCount(0);
  expect((await page.request.get(`/api/activities/${S.low_coverage}`)).status()).toBe(404);
  await page.goto("/settings");
  await expect(page.getByRole("table", { name: "Saved exports" })).toHaveCount(0);   // the export held it
});

test("WP9 deleting a confirmed ride's power source flags the ride for review", async ({ page }) => {
  const g = await (await page.request.get(`/api/duplicate-groups/${S.group}`)).json();
  const sel = { timer: S.fenix, power: S.hub, heart_rate: S.fenix, cadence: S.whoosh, speed: null, distance: null, temperature: null };
  for (const f of ["speed", "distance", "temperature"] as const) {
    for (const m of g.members) {
      const a = await (await page.request.get(`/api/activities/${m.activity_id}`)).json();
      if (a.channels[f]?.present && (sel as Record<string, number | null>)[f] === null) (sel as Record<string, number | null>)[f] = a.id;
    }
  }
  const ride = (await (await page.request.post(`/api/duplicate-groups/${S.group}/confirm`, { data: { selection: sel } })).json()).ride_id;
  await page.goto(`/activities/${S.hub}`);
  await page.getByRole("button", { name: "Delete this recording" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Confirm deletion" });
  await expect(dialog).toContainText("Power will have no source");
  await expect(dialog).toContainText("No other recording changes");
  await dialog.getByRole("button", { name: "Delete permanently" }).click();
  await expect(page).toHaveURL(/\/library$/);
  await page.goto("/");
  await expect(page.getByTestId("needs-review")).toContainText("A ride needs new sources");
  await page.getByTestId("needs-review").getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/rides/${ride}$`));
  await expect(page.getByTestId("needs-review")).toContainText("Power now have no source");
  await expect(page.getByTestId("metric-M002")).toContainText("Not available");
});

test("WP9 delete everything after one confirmation, then restore the archive", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByText("Restoring needs an empty library")).toBeVisible();
  await page.getByRole("button", { name: "Delete everything…" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Confirm delete everything" });
  await expect(dialog).toContainText("original files");
  await expect(dialog).toContainText("Kept, because the app did not create them");
  await dialog.getByRole("button", { name: "Delete everything" }).click();
  await expect(page.getByText("Everything was deleted. The library is empty.")).toBeVisible();
  expect((await (await page.request.get("/api/activities")).json()).total).toBe(0);
  await expect(page.getByLabel("Archive to restore")).toBeVisible();
  await page.getByLabel("Archive to restore").setInputFiles(archivePath);
  await expect(page.getByTestId("restore-report")).toContainText("reproduced the archived values exactly", { timeout: 60_000 });
  await page.goto("/library");
  // The archive was made before the two deletions, so every recording it held returns.
  await expect(page.locator("tr[data-activity]")).toHaveCount(archived);
  await page.goto(`/activities/${S.validity}`);
  await expect(page.getByTestId("metric-M001")).toContainText("9:30");
});

test("spec 8.5 the server made no network call except on 127.0.0.1 during every test", () => {
  const events = readFileSync(repoPath("build/e2e-data/net.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
  expect(events.some((e) => e.event === "socket.bind" && e.host === "127.0.0.1")).toBe(true);
  expect(events.filter((e) => !e.loopback)).toEqual([]);
});
