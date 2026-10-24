import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { arch, cpus, platform, release, totalmem } from "node:os";
import type { Browser, Page } from "@playwright/test";
import { expect, repoPath, test } from "./fixtures";

const RUNS = 5;
const TARGET_MS = 2000;

// Records performance.now() (ms from navigation start) on the first frame where each condition holds.
const MARKS = () => {
  const w = window as unknown as { __t: Record<string, number> };
  w.__t = {};
  const checks: Record<string, () => boolean> = {
    library: () => document.querySelectorAll("tr[data-activity]").length >= 50,
    overview: () => !!document.querySelector('[data-testid="total-duration"]') && !!document.querySelector('[aria-label="Weekly work"] .bar')
      && document.querySelectorAll("tr[data-activity]").length > 0,
    activity: () => !!document.querySelector('[data-testid="metric-M004-3600"]') && !!document.querySelector('[data-testid="chart"] canvas'),
  };
  const tick = () => {
    for (const [k, f] of Object.entries(checks)) if (!(k in w.__t) && f()) w.__t[k] = performance.now();
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};

async function heapMB(page: Page): Promise<number> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("HeapProfiler.collectGarbage");
  await cdp.send("Performance.enable");
  const { metrics } = await cdp.send("Performance.getMetrics");
  return Math.round((metrics.find((m) => m.name === "JSHeapUsedSize")!.value / 1024 / 1024) * 10) / 10;
}

async function load(browser: Browser, url: string, mark: string) {
  const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, locale: "en-GB", timezoneId: "Europe/London", viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(MARKS);
  const requests: string[] = [];
  ctx.on("request", (r) => requests.push(r.url()));
  const page = await ctx.newPage();
  await page.goto(url);
  await page.waitForFunction((m) => (window as unknown as { __t: Record<string, number> }).__t[m] !== undefined, mark, { timeout: 60_000 });
  const ms = await page.evaluate((m) => (window as unknown as { __t: Record<string, number> }).__t[m], mark);
  return { ms: Math.round(ms), page, ctx, requests };
}

const stats = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return { runs: xs, median: s[Math.floor(s.length / 2)], max: s[s.length - 1] };
};

test("UI-12 UI-16 UI-17 UI-18 load times, heap and chart responsiveness", async ({ browser }) => {
  const seed = JSON.parse(readFileSync(repoPath("build/perf-data/seed.json"), "utf8"));
  const out: Record<string, unknown> = {
    environment: { platform: platform(), release: release(), arch: arch(), cpu: cpus()[0]?.model, cores: cpus().length,
      memory_gb: Math.round(totalmem() / 1024 ** 3), browser: `chromium ${browser.version()}`, headless: true },
    data: seed, runs_per_measure: RUNS, target_ms: TARGET_MS,
  };

  for (const [name, url, mark] of [["library", "/library", "library"], ["overview", "/", "overview"],
    ["activity_3h", `/activities/${seed.three_hour_activity}`, "activity"]] as const) {
    const times: number[] = [];
    let heap = 0;
    let sampleRows = 0;
    for (let i = 0; i < RUNS; i++) {
      const r = await load(browser, url, mark);
      times.push(r.ms);
      // UI-12: no screen fetches all samples. Sample pages are 60 rows; the chart gets a bounded envelope.
      for (const u of r.requests.map((x) => new URL(x))) {
        if (u.pathname.endsWith("/samples")) sampleRows = Math.max(sampleRows, Number(u.searchParams.get("limit")));
        expect(u.pathname.endsWith("/samples") && Number(u.searchParams.get("limit") ?? 0) > 500).toBe(false);
      }
      if (i === RUNS - 1) heap = await heapMB(r.page);
      if (name === "activity_3h" && i === RUNS - 1) out.chart = await chartTimings(r.page);
      await r.ctx.close();
    }
    out[name] = { ...stats(times), js_heap_used_mb: heap, largest_sample_page: sampleRows || null };
  }

  mkdirSync(repoPath("frontend/perf-results"), { recursive: true });
  writeFileSync(repoPath("frontend/perf-results/perf.json"), JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  for (const k of ["library", "activity_3h"]) {
    expect.soft((out[k] as { median: number }).median, `${k} median against the provisional ${TARGET_MS} ms target`).toBeLessThanOrEqual(TARGET_MS);
  }
});

async function chartTimings(page: Page) {
  const zoom = await page.getByTestId("chart").evaluate(async (node) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const u = (node as any).__uplot;
    const xs: number[] = u.data[0];
    const lo = xs[0], hi = xs[xs.length - 1];
    const res: number[] = [];
    for (const frac of [0.5, 0.1, 0.02, 1]) {
      const t0 = performance.now();
      u.setScale("x", { min: lo, max: lo + (hi - lo) * frac });
      await new Promise((r) => requestAnimationFrame(() => r(null)));
      res.push(Math.round((performance.now() - t0) * 10) / 10);
    }
    return { points_drawn: xs.length, redraw_ms: res };
  });
  const switches: number[] = [];
  for (const [tab, ch] of [["Heart rate", "heart_rate"], ["Cadence", "cadence"], ["Power", "power"]]) {
    const ms = await page.evaluate(async ([tabName, channel]) => {
      const btn = [...document.querySelectorAll('[role="tab"]')].find((b) => b.textContent === tabName) as HTMLButtonElement;
      const t0 = performance.now();
      btn.click();
      await new Promise<void>((resolve) => {
        const poll = () => document.querySelector(`[data-testid="chart"][data-channel="${channel}"] canvas`) ? resolve() : requestAnimationFrame(poll);
        poll();
      });
      await new Promise((r) => requestAnimationFrame(() => r(null)));
      return Math.round(performance.now() - t0);
    }, [tab, ch]);
    switches.push(ms);
  }
  return { zoom_redraw_ms_at_50_10_2_100_percent: zoom.redraw_ms, envelope_points: zoom.points_drawn, channel_switch_ms: switches };
}
