import { test as base, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

export type Seed = { fenix: number; hub: number; whoosh: number; group: number; validity: number; low_coverage: number; upload_dir: string };
export const seed = (): Seed => JSON.parse(readFileSync(resolve(here, "../../build/e2e-data/seed.json"), "utf8"));
export const repoPath = (p: string) => resolve(here, "../..", p);

/** Every page aborts any request that is not to 127.0.0.1 and the test fails if one was attempted (UI-02). */
export const test = base.extend<{ outbound: string[] }>({
  outbound: async ({ context }, use) => {
    const seen: string[] = [];
    await context.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (url.hostname === "127.0.0.1" || url.protocol === "data:" || url.protocol === "blob:") return route.continue();
      seen.push(url.href);
      return route.abort();
    });
    await use(seen);
    expect(seen, "requests that left 127.0.0.1").toEqual([]);
  },
  page: async ({ page, outbound }, use) => {
    void outbound;
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await use(page);
    expect(errors, "browser errors").toEqual([]);
  },
});
export { expect };
