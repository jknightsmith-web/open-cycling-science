import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { Series } from "../api/client";
import { CHANNEL_NAMES, CHANNEL_UNITS, timeOfDay } from "../format/format";
import { toChartData } from "./chartData";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#1d5f8a";

function hatch(ctx: CanvasRenderingContext2D, color: string, dir: 1 | -1): CanvasPattern | string {
  const c = document.createElement("canvas");
  c.width = c.height = 8;
  const g = c.getContext("2d");
  if (!g) return color;
  g.strokeStyle = color;
  g.globalAlpha = 0.55;
  g.beginPath();
  if (dir === 1) { g.moveTo(0, 8); g.lineTo(8, 0); } else { g.moveTo(0, 0); g.lineTo(8, 8); }
  g.stroke();
  return ctx.createPattern(c, "repeat") ?? color;
}

/** Draws pauses, missing, gap, invalid and suspect zero bands under the line (design 06, 4.2). */
function bandsPlugin(series: Series): uPlot.Plugin {
  return {
    hooks: {
      drawClear: [(u: uPlot) => {
        const { ctx } = u;
        const { top, height } = u.bbox;
        const muted = css("--muted"), bad = css("--bad"), paused = css("--paused"), suspect = css("--suspect");
        const px = (t: number) => u.valToPos(t, "x", true);
        ctx.save();
        for (const br of series.breaks) {
          const x0 = px(br.start), x1 = px(br.end), w = Math.max(1, x1 - x0);
          if (br.reason === "paused") { ctx.globalAlpha = 0.18; ctx.fillStyle = paused; ctx.fillRect(x0, top, w, height); }
          else if (br.reason === "invalid") {
            ctx.globalAlpha = 0.9; ctx.fillStyle = bad;
            for (let x = x0; x < x1; x += 4) ctx.fillRect(x, top + height - 8, 2, 8);
          } else { ctx.globalAlpha = 1; ctx.fillStyle = hatch(ctx, muted, br.reason === "gap" ? -1 : 1); ctx.fillRect(x0, top, w, height); }
        }
        for (const [a, b] of series.suspect_zero) {
          ctx.globalAlpha = 0.22; ctx.fillStyle = suspect; ctx.fillRect(px(a), top, Math.max(1, px(b) - px(a)), height);
        }
        ctx.restore();
      }],
    },
  };
}

export function TimeSeriesChart({ series, zone, height = 260 }: { series: Series; zone: string; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const data = toChartData(series);
    const stroke = css("--series");
    const label = `${CHANNEL_NAMES[series.channel]}${series.simulated ? " (simulated)" : ""}`;
    const opts: uPlot.Options = {
      width: node.clientWidth || 800, height,
      plugins: [bandsPlugin(series)],
      cursor: { drag: { x: true, y: false } },
      scales: { x: { time: false } },
      axes: [
        { values: (_u, ticks) => ticks.map((t) => timeOfDay(t, zone)), stroke: css("--muted"), grid: { stroke: css("--line") } },
        { label: CHANNEL_UNITS[series.channel], stroke: css("--muted"), grid: { stroke: css("--line") } },
      ],
      series: [{}, { label, stroke, width: 1.5, spanGaps: false, points: { show: false } }],
      legend: { show: false },
    };
    const u = new uPlot(opts, [data.x, data.y], node);
    (node as HTMLDivElement & { __uplot?: uPlot }).__uplot = u;
    const ro = new ResizeObserver(() => u.setSize({ width: node.clientWidth, height }));
    ro.observe(node);
    return () => { ro.disconnect(); u.destroy(); };
  }, [series, zone, height]);
  return (
    <figure style={{ margin: 0 }}>
      <div ref={el} data-testid="chart" data-channel={series.channel} />
      <figcaption className="chart-legend">
        <span><span className="swatch sw-missing" />missing</span>
        <span><span className="swatch sw-gap" />recording gap</span>
        <span><span className="swatch sw-invalid" />invalid</span>
        <span><span className="swatch sw-paused" />timer paused</span>
        {series.channel === "power" && <span><span className="swatch sw-suspect" />suspect zero (value kept)</span>}
        <span>Drag to zoom, double click to reset. Display envelope of {series.points_returned} points, not a metric.</span>
      </figcaption>
    </figure>
  );
}
