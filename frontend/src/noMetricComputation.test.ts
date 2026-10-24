/**
 * UI-13: the frontend formats values; it never computes a metric. Fails if any
 * source file outside the formatters sums or averages over sample values.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname);
const ALLOWED = ["format/format.ts"];
const PATTERNS: [string, RegExp][] = [
  ["reduce over a collection", /\.reduce(Right)?\s*\(/],
  ["running sum", /\b\w*(sum|total|acc)\w*\s*\+=/i],
  ["mean over a collection", /\/\s*[\w.]+\.length\b/],
  ["sample or series value arithmetic", /(\.value|\.v\[\w+\]|\.channels\[[^\]]+\]\.value)\s*[-+*/]\s*[\w(]/],
];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : /\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$|\.d\.ts$/.test(f) ? [p] : [];
  });
}

describe("UI-13 no metric computation in the frontend", () => {
  it("finds no sum or mean over sample values outside the formatters", () => {
    const hits: string[] = [];
    for (const f of files(SRC)) {
      const rel = relative(SRC, f).replace(/\\/g, "/");
      if (ALLOWED.includes(rel)) continue;
      readFileSync(f, "utf8").split("\n").forEach((line, i) => {
        for (const [what, re] of PATTERNS) if (re.test(line)) hits.push(`${rel}:${i + 1} ${what}: ${line.trim()}`);
      });
    }
    expect(hits).toEqual([]);
  });

  it("detects a planted mean, so the guard is not vacuous", () => {
    const planted = "const mean = samples.map((s) => s.value).reduce((a, b) => a + b, 0) / samples.length;";
    expect(PATTERNS.some(([, re]) => re.test(planted))).toBe(true);
  });
});
