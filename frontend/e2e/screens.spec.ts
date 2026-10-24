import { readdirSync, readFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { expect, repoPath, seed, test, type Seed } from "./fixtures";

// One serial run on one seeded data root. Tests that change state restore it before they finish,
// except the import test, which runs last.
test.describe.configure({ mode: "serial" });
let S: Seed;
test.beforeAll(() => { S = seed(); });

const totalRides = async (page: Page) => {
  await page.goto("/");
  await expect(page.getByTestId("total-duration")).toBeVisible();
  return {
    duration: (await page.getByTestId("total-duration").textContent())!.trim(),
    rides: (await page.locator(".card .meta", { hasText: "rides" }).first().textContent())!.trim(),
    notice: await page.getByTestId("overcount").count(),
  };
};

test("UI-02 the built bundle names no remote host except DOI links and fixed identifier strings", () => {
  const dist = repoPath("frontend/dist/assets");
  const text = readdirSync(dist).map((f) => readFileSync(`${dist}/${f}`, "utf8")).join("\n") + readFileSync(repoPath("frontend/dist/index.html"), "utf8");
  const urls = [...new Set(text.match(/https?:\/\/[a-zA-Z0-9.-]+/g) ?? [])];
  // XML namespace identifiers, the localhost base React Router uses to parse paths, and two library
  // error message strings. None is fetched; the route guard in every test below proves that at run time.
  const allowed = new Set(["https://doi.org", "http://www.w3.org", "http://localhost", "https://react.dev", "https://reactrouter.com"]);
  expect(urls.filter((u) => !allowed.has(u))).toEqual([]);
  expect(text).not.toMatch(/fonts\.googleapis|cdn\.|unpkg|jsdelivr/);
});

test("UI-04 a two source ride is proposed with its evidence and the Overview shows the overcount", async ({ page }) => {
  const t = await totalRides(page);
  expect(t.rides).toContain("5 rides");
  expect(t.duration).toBe("1:49:15");
  await expect(page.getByTestId("overcount")).toContainText("1 possible duplicate ride is unconfirmed");
  await expect(page.locator("nav .badge, header .badge").first()).toHaveText("1");
  await page.getByRole("link", { name: "Review duplicates" }).click();
  await expect(page.locator(`tr[data-group="${S.group}"]`)).toHaveAttribute("data-status", "proposed");
  await page.getByRole("link", { name: `Group ${S.group}` }).click();
  const evidence = page.getByRole("table", { name: "Evidence" });
  await expect(evidence.locator("tbody tr")).toHaveCount(3);
  await expect(evidence).toContainText("Timer overlap");
  await expect(page.getByRole("button", { name: "Confirm as one ride" })).toBeVisible();
});

async function chooseSources(page: Page, picks: Record<string, RegExp>) {
  for (const row of await page.locator("form tr[data-field]").all()) {
    const field = (await row.getAttribute("data-field"))!;
    const group = row.getByRole("radiogroup");
    if (!(await group.count())) continue;
    if (picks[field]) await group.getByRole("radio", { name: picks[field] }).check();
    else if (await group.getByRole("radio", { name: "none" }).count()) await group.getByRole("radio", { name: "none" }).check();
    else await group.getByRole("radio").first().check();
  }
}

test("UI-05 UI-06 confirming gives one ride with per field sources; reopen and reject restore the totals", async ({ page }) => {
  await page.goto(`/library/duplicates/${S.group}`);
  const submit = page.getByRole("button", { name: "Confirm as one ride" });
  await expect(submit).toBeVisible();
  // Power, heart rate and cadence from three different files.
  await chooseSources(page, { timer: new RegExp(`#${S.fenix}\\)`), power: new RegExp(`#${S.hub}\\)`),
    heart_rate: new RegExp(`#${S.fenix}\\)`), cadence: new RegExp(`#${S.whoosh}\\)`) });
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByTestId("ride")).toBeVisible();
  const sources = page.getByRole("table", { name: "Sources" });
  await expect(sources.locator('tr[data-field="power"]')).toContainText(`#${S.hub})`);
  await expect(sources.locator('tr[data-field="heart_rate"]')).toContainText(`#${S.fenix})`);
  await expect(sources.locator('tr[data-field="cadence"]')).toContainText(`#${S.whoosh})`);
  await expect(page.getByTestId("metric-M002")).toContainText(`from Wattbike Hub (TCX, #${S.hub})`);
  await expect(page.getByTestId("metric-M001")).toContainText(`#${S.fenix})`);

  let t = await totalRides(page);
  expect(t).toEqual({ duration: "49:30", rides: expect.stringContaining("3 rides"), notice: 0 });

  await page.goto(`/library/duplicates/${S.group}`);
  await page.getByRole("button", { name: /^Reopen/ }).click();
  await expect(page.getByRole("button", { name: "Confirm as one ride" })).toBeVisible();
  t = await totalRides(page);
  expect(t).toEqual({ duration: "1:49:15", rides: expect.stringContaining("5 rides"), notice: 1 });

  await page.goto(`/library/duplicates/${S.group}`);
  await page.getByRole("button", { name: "Not the same ride" }).click();
  await expect(page.getByText("Kept as separate rides.")).toBeVisible();
  t = await totalRides(page);
  expect(t).toEqual({ duration: "1:49:15", rides: expect.stringContaining("5 rides"), notice: 0 });

  await page.goto(`/library/duplicates/${S.group}`);
  await page.getByRole("button", { name: "Reopen" }).click();
  await expect(page.getByRole("button", { name: "Confirm as one ride" })).toBeVisible();
});

test("UI-07 observed zero, missing, invalid and suspect zero are told apart in words; none shows as 0", async ({ page }) => {
  await page.goto(`/activities/${S.validity}`);
  await page.getByTestId("samples").locator("summary").click();
  const found = new Set<string>();
  let zeroObserved = false, suspect = false;
  for (;;) {
    const cells = await page.getByRole("table", { name: "Samples" }).locator("td[data-validity]")
      .evaluateAll((els) => els.map((e) => [e.getAttribute("data-validity")!, e.textContent!.trim()]));
    for (const [v, text] of cells) {
      found.add(v);
      if (v !== "observed") expect(text).toBe(v);
      if (v === "observed" && /^0 W/.test(text)) { zeroObserved = true; if (text.includes("suspect zero")) suspect = true; }
    }
    const samples = page.getByTestId("samples");
    const next = samples.getByRole("button", { name: "Next" });
    if (await next.isDisabled()) break;
    const range = (await samples.getByText(/ of \d+$/).textContent())!;
    await next.click();
    await expect(samples.getByText(/ of \d+$/)).not.toHaveText(range);
    // The pager moves before the page arrives; read the rows only once they are the new page's.
    await expect(page.getByRole("table", { name: "Samples" })).toHaveAttribute("aria-busy", "false");
  }
  expect([...found].sort()).toEqual(["invalid", "missing", "observed"]);
  expect(zeroObserved).toBe(true);
  expect(suspect).toBe(true);
  // The chart legend names each band in words, not by colour alone.
  const legend = page.locator("figcaption.chart-legend");
  for (const w of ["missing", "recording gap", "invalid", "timer paused", "suspect zero"]) await expect(legend).toContainText(w);
});

type Probe = { breaks: [number, number, string][]; bad: { reason: string; x: number }[]; points: number };

/** Reads the drawn canvas inside every break and reports any pixel close to the series stroke colour. */
async function probeChart(page: Page): Promise<Probe> {
  return page.getByTestId("chart").evaluate(async (node) => {
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const u = (node as any).__uplot;
    const ctx: CanvasRenderingContext2D = u.ctx;
    const stroke = getComputedStyle(document.documentElement).getPropertyValue("--series").trim();
    const rgb = [1, 3, 5].map((i) => parseInt(stroke.slice(i, i + 2), 16));
    const channel = node.getAttribute("data-channel")!;
    const res = await fetch(`${location.pathname.replace(/^\/(activities)\/(\d+).*/, "/api/activities/$2")}/series?channel=${channel}`);
    const s = await res.json();
    const { top, height } = u.bbox;
    const bad: { reason: string; x: number }[] = [];
    for (const b of s.breaks) {
      const x0 = Math.ceil(u.valToPos(b.start, "x", true)) + 3, x1 = Math.floor(u.valToPos(b.end, "x", true)) - 3;
      if (x1 <= x0) continue;
      const img = ctx.getImageData(x0, top, x1 - x0, height).data;
      for (let i = 0; i < img.length; i += 4) {
        const d = Math.abs(img[i] - rgb[0]) + Math.abs(img[i + 1] - rgb[1]) + Math.abs(img[i + 2] - rgb[2]);
        if (d < 60 && img[i + 3] > 200) { bad.push({ reason: b.reason, x: x0 + ((i / 4) % (x1 - x0)) }); break; }
      }
    }
    return { breaks: s.breaks.map((b: { start: number; end: number; reason: string }) => [b.start, b.end, b.reason]), bad, points: s.points_returned };
  });
}

test("UI-19 the chart draws no line across a missing, invalid, gap or paused interval", async ({ page }) => {
  await page.goto(`/activities/${S.validity}`);
  await expect(page.getByTestId("chart")).toHaveAttribute("data-channel", "power");
  const p = await probeChart(page);
  expect(new Set(p.breaks.map((b) => b[2]))).toEqual(new Set(["gap", "missing", "invalid", "paused"]));
  expect(p.bad).toEqual([]);
  // Positive control: the same probe sees the stroke inside a run.
  const seen = await page.getByTestId("chart").evaluate((node) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const u = (node as any).__uplot;
    const x = Math.round(u.valToPos(u.data[0][0] + 30, "x", true));
    const col = u.ctx.getImageData(x, u.bbox.top, 1, u.bbox.height).data;
    for (let i = 0; i < col.length; i += 4) if (col[i + 2] > 100 && col[i] < 80 && col[i + 3] > 200) return true;
    return false;
  });
  expect(seen).toBe(true);
  await page.getByRole("tab", { name: "Heart rate" }).click();
  await expect(page.getByTestId("chart")).toHaveAttribute("data-channel", "heart_rate");
  expect((await probeChart(page)).bad).toEqual([]);
});

test("UI-08 every metric shows its class and opens its register entry", async ({ page }) => {
  await page.goto(`/activities/${S.fenix}`);
  const cards = page.locator('[data-testid^="metric-"]');
  await expect(cards).toHaveCount(8);
  for (const c of await cards.all()) {
    await expect(c.locator(".class-label")).toHaveText(/^(observed|derived|modelled|experimental)$/);
    await expect(c.getByRole("button", { name: /^About / })).toBeVisible();
  }
  await page.getByTestId("metric-M002").getByRole("button", { name: /^About / }).click();
  const drawer = page.getByRole("dialog", { name: "About M002" });
  for (const h of ["Class", "Equation", "Assumptions", "Limitations", "Sources", "Source file", "Input revision"]) {
    await expect(drawer.locator("dt", { hasText: new RegExp(`^${h}$`) }).first()).toBeVisible();
  }
  await expect(drawer.locator("dd ul li").first()).toBeVisible();
  await drawer.getByRole("link", { name: "Full register entry" }).click();
  await expect(page.getByTestId("entry-M002")).toContainText("Known limitations");
});

test("UI-09 unavailable metrics name their state; a lower bound reads at least", async ({ page }) => {
  await page.goto(`/activities/${S.low_coverage}`);
  await expect(page.locator('[data-testid^="metric-"]')).toHaveCount(8);
  await expect(page.getByTestId("metric-M002")).toContainText("Not available");
  await expect(page.getByTestId("metric-M002")).toContainText("50.0% of time has power");
  await expect(page.getByTestId("metric-M003").locator(".value")).toHaveText(/^at least \d/);
  for (const c of await page.locator('[data-testid^="metric-"] .value').all()) {
    const v = (await c.textContent())!.trim();
    expect(v).not.toBe("");
    expect(v).not.toMatch(/^0( |$)/);
  }
});

test("UI-10 changing the display time zone changes labels only", async ({ page }) => {
  const read = async () => {
    await page.goto(`/activities/${S.validity}`);
    await expect(page.getByTestId("metric-M001")).toBeVisible();
    return { title: await page.locator("h1").textContent(),
      values: await page.locator('[data-testid^="metric-"]').evaluateAll((els) => els.map((e) => `${e.getAttribute("data-testid")}=${e.querySelector(".value")?.textContent}`)) };
  };
  const before = await read();
  await page.goto("/settings");
  await page.getByLabel("Display time zone").selectOption("Pacific/Auckland");
  await expect(page.getByLabel("Display time zone")).toHaveValue("Pacific/Auckland");
  const after = await read();
  expect(after.values).toEqual(before.values);
  expect(after.title).not.toEqual(before.title);
  await page.goto("/");
  await expect(page.getByRole("table", { name: "Activities" })).toContainText("Date (Pacific/Auckland)");
  await page.goto("/settings");
  await page.getByLabel("Display time zone").selectOption("");
  await expect(page.getByLabel("Display time zone")).toHaveValue("");
});

test("UI-11 recording statistics and flags show without an adequacy verdict", async ({ page }) => {
  await page.goto(`/activities/${S.validity}`);
  const stats = page.locator("dl", { hasText: "Nominal recording interval" });
  await expect(stats).toContainText("Longest interval");
  await expect(stats).toContainText("31 s");
  await expect(stats).toContainText("1, 0:30 in total");
  await expect(stats.locator(".flag")).toContainText(["suspect zero"]);
  await expect(page.locator("article")).not.toContainText(/\b(adequate|inadequate|good quality|poor quality|sufficient for)\b/i);
});

test("UI-14 no screen shows training load, readiness, fitness, fatigue, FTP, zone or kcal", async ({ page }) => {
  const forbidden = /training load|readiness|fitness|fatigue|\bFTP\b|(?<!time )\bzones?\b|kcal|calories|\bTSS\b|\bCTL\b|\bATL\b/i;
  for (const url of ["/", "/library", "/library/imports", "/library/duplicates", `/library/duplicates/${S.group}`,
    `/activities/${S.fenix}`, `/activities/${S.validity}`, "/settings"]) {
    await page.goto(url);
    await expect(page.locator("main h1, main h2").first()).toBeVisible();
    await expect(page.getByText("Loading…")).toHaveCount(0);
    expect((await page.locator("#root").innerText()).match(forbidden), url).toBeNull();
  }
  const ids = await page.request.get("/api/science/metrics").then((r) => r.json()).then((rows: { metric_id: string }[]) => rows.map((r) => r.metric_id));
  expect(ids).toEqual(["M001", "M002", "M003", "M004"]);
});

test("UI-03 importing shows each outcome: imported, identical bytes with a link, failed with the reason", async ({ page }) => {
  await page.goto("/library");
  await page.getByLabel("Choose files").setInputFiles(["new_ride.fit", "same_as_fenix.fit", "corrupt.fit"].map((f) => repoPath(`${S.upload_dir}/${f}`)));
  const results = page.getByRole("table", { name: "Import results" });
  await expect(results.locator("tr")).toHaveCount(3);
  await expect(results.locator('tr[data-status="imported"]')).toContainText("new_ride.fit");
  const same = results.locator('tr[data-status="duplicate_bytes"]');
  await expect(same).toContainText("Identical file already imported");
  await expect(same.getByRole("link", { name: "open it" })).toHaveAttribute("href", `/activities/${S.fenix}`);
  await expect(results.locator('tr[data-status="failed"]')).toContainText(/corrupt\.fit.*Failed \(\w+\): \S+/);
  await page.getByRole("link", { name: "Imports" }).click();
  await expect(page.getByRole("table", { name: "Import log" }).locator('tr[data-status="failed"]')).toContainText("corrupt.fit");
});
