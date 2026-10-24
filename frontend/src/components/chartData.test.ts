import { describe, expect, it } from "vitest";
import { bridgesABreak, toChartData } from "./chartData";
import type { Series } from "../api/client";

function series(runs: [number, number][][], breaks: Series["breaks"], channel = "power"): Series {
  return {
    kind: "display_envelope", channel, t_start: 0, t_end: 100, simulated: false, points_requested: 2000,
    points_returned: 0, bucket_width_s: null, suspect_zero: [], timer_segments: [],
    runs: runs.map((r) => ({ t: r.map((p) => p[0]), v: r.map((p) => p[1]) })), breaks,
  };
}

describe("chart arrays never join observations across a break", () => {
  it("puts a null between runs", () => {
    const s = series([[[0, 200], [10, 200]], [[15, 300], [20, 300]]], [{ start: 10, end: 15, reason: "gap" }]);
    const d = toChartData(s);
    expect(d.x).toEqual([0, 10, 12.5, 15, 20]);
    expect(d.y).toEqual([200, 200, null, 300, 300]);
    expect(bridgesABreak(d, s.breaks)).toBe(false);
  });

  it("detects a bridge if the null were missing (the check itself works)", () => {
    expect(bridgesABreak({ x: [0, 10, 15, 20], y: [200, 200, 300, 300] }, [{ start: 10, end: 15 }])).toBe(true);
  });

  it("holds for random runs and breaks", () => {
    let seed = 7;
    const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let trial = 0; trial < 500; trial++) {
      const runs: [number, number][][] = [];
      const breaks: Series["breaks"] = [];
      let t = 0;
      const nRuns = 1 + Math.floor(rand() * 6);
      for (let r = 0; r < nRuns; r++) {
        const run: [number, number][] = [];
        const len = 1 + Math.floor(rand() * 8);
        for (let k = 0; k <= len; k++) run.push([t + k, Math.floor(rand() * 500)]);
        runs.push(run);
        t += len;
        if (r < nRuns - 1) {
          const w = 0.5 + rand() * 5;
          breaks.push({ start: t, end: t + w, reason: (["missing", "invalid", "gap", "paused"] as const)[r % 4] });
          t += w;
        }
      }
      const d = toChartData(series(runs, breaks));
      expect(bridgesABreak(d, breaks)).toBe(false);
      expect(d.y.filter((v) => v === null).length).toBe(nRuns - 1);
    }
  });

  it("converts speed to km/h without touching nulls", () => {
    const d = toChartData(series([[[0, 10]], [[5, 0]]], [{ start: 1, end: 5, reason: "missing" }], "speed"));
    expect(d.y).toEqual([36, null, 0]);
  });
});
