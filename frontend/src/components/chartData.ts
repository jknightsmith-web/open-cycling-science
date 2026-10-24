/**
 * Series envelope to chart arrays (design 06 B3, UI-19).
 *
 * Each run from the API is a stretch of contiguous observed values. A null is
 * placed between every pair of runs, and the chart draws with spanGaps false,
 * so no line can join observations across a missing, invalid, gap or paused
 * interval. Values are converted to display units only.
 */
import type { Series } from "../api/client";
import { displayChannel } from "../format/format";

export interface ChartData { x: number[]; y: (number | null)[] }

export function toChartData(series: Series): ChartData {
  const x: number[] = [];
  const y: (number | null)[] = [];
  series.runs.forEach((run, i) => {
    if (i > 0) {
      const prevEnd = x[x.length - 1];
      const nextStart = run.t[0];
      x.push(nextStart > prevEnd ? (prevEnd + nextStart) / 2 : prevEnd);
      y.push(null);
    }
    run.t.forEach((t, j) => {
      x.push(t);
      y.push(displayChannel(series.channel, run.v[j]));
    });
  });
  return { x, y };
}

/** True if any drawn segment (two consecutive non null points) spans a break. Used by tests. */
export function bridgesABreak(data: ChartData, breaks: { start: number; end: number }[]): boolean {
  for (let i = 0; i + 1 < data.x.length; i++) {
    if (data.y[i] === null || data.y[i + 1] === null) continue;
    const a = data.x[i], b = data.x[i + 1];
    if (breaks.some((br) => Math.max(a, br.start) < Math.min(b, br.end))) return true;
  }
  return false;
}
