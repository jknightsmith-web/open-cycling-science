/**
 * Display formatting only (design 06, 4.3). Nothing here computes a metric:
 * values arrive from the API and are converted for display (m/s to km/h, m
 * to km), rounded and placed in the display time zone. Null stays absent and
 * zero stays zero.
 */
import type { MetricValue } from "../api/client";

export const systemZone = (): string => Intl.DateTimeFormat("en-GB").resolvedOptions().timeZone || "UTC";
export const zoneOf = (s?: { display_time_zone?: string | null } | null): string => s?.display_time_zone || systemZone();

const n0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const n1 = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const n2 = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}` : `${m}:${String(r).padStart(2, "0")}`;
}

export function windowLabel(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${seconds / 60} min`;
  return `${seconds / 3600} h`;
}

/** Display units per channel (UI-D3: km/h and km, SI elsewhere). */
export const CHANNEL_UNITS: Record<string, string> = {
  power: "W", heart_rate: "bpm", cadence: "rpm", speed: "km/h", distance: "km", temperature: "°C",
};
export const CHANNEL_NAMES: Record<string, string> = {
  timer: "Timer (duration)", power: "Power", heart_rate: "Heart rate", cadence: "Cadence", speed: "Speed",
  distance: "Distance", temperature: "Temperature",
};

/** Convert a stored channel value to its display unit. */
export function displayChannel(channel: string, value: number): number {
  if (channel === "speed") return value * 3.6;
  if (channel === "distance") return value / 1000;
  return value;
}

export function channelText(channel: string, value: number): string {
  const v = displayChannel(channel, value);
  const f = channel === "distance" ? n2 : channel === "speed" || channel === "temperature" ? n1 : n0;
  return `${f.format(v)} ${CHANNEL_UNITS[channel] ?? ""}`.trim();
}

export function number(units: string, value: number): string {
  if (units === "s") return duration(value);
  return `${n0.format(value)} ${units}`;
}

export function pct(fraction: number | null | undefined): string {
  return fraction === null || fraction === undefined ? "" : `${n1.format(fraction * 100)}%`;
}

/** Plain name for the primary layer; the register name sits in the info control (design 06, 4.5). */
export function metricLabel(m: Pick<MetricValue, "metric_id" | "parameters">): string {
  switch (m.metric_id) {
    case "M001": return "Duration (timer)";
    case "M002": return "Mean power";
    case "M003": return "Work";
    case "M004": return `Highest observed power, ${windowLabel(Number(m.parameters.duration_s))}`;
    default: return m.metric_id;
  }
}

export const AVAILABLE = new Set(["valid", "lower_bound", "unconfirmed_duplicates_included"]);

/** Primary text for a metric value: the number, "at least" for a lower bound, or the named reason. */
export function metricText(m: MetricValue): { main: string; available: boolean; note?: string } {
  if (AVAILABLE.has(m.state) && m.value !== null && m.value !== undefined) {
    const main = number(m.units, m.value);
    if (m.state === "lower_bound") return { main: `at least ${main}`, available: true, note: `${pct(m.coverage)} of time has power` };
    return { main, available: true };
  }
  return { main: "Not available", available: false, note: unavailableReason(m) };
}

export function unavailableReason(m: Pick<MetricValue, "state" | "coverage" | "parameters" | "details">): string {
  switch (m.state) {
    case "insufficient_coverage":
      if (m.coverage !== null && m.coverage !== undefined && m.parameters.min_coverage !== undefined)
        return `only ${pct(m.coverage)} of time has power (needs ${pct(Number(m.parameters.min_coverage))})`;
      if (m.parameters.duration_s !== undefined)
        return `no unbroken stretch of power as long as ${windowLabel(Number(m.parameters.duration_s))}`;
      return "not enough data";
    case "no_power": return "no power recorded";
    case "not_applicable": return "does not apply to this recording";
    case "not_displayable": return "register entry incomplete";
    default: return m.state.replace(/_/g, " ");
  }
}

export function dateTime(utc: number | null | undefined, zone: string): string {
  if (utc === null || utc === undefined) return "";
  return new Intl.DateTimeFormat("en-GB", { timeZone: zone, weekday: "short", day: "numeric", month: "short",
    year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(utc * 1000));
}

export function timeOfDay(utc: number, zone: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: zone, hour: "2-digit", minute: "2-digit", second: "2-digit" })
    .format(new Date(utc * 1000));
}

/** Calendar date (YYYY-MM-DD) of an instant in a zone. */
export function dayIn(utc: number, zone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date(utc * 1000));
}

/** First and last calendar day of the last `weeks` ISO weeks in a zone, ending with the current week. */
export function weekRange(nowUtc: number, zone: string, weeks: number): [string, string] {
  const [y, m, d] = dayIn(nowUtc, zone).split("-").map(Number);
  const today = Date.UTC(y, m - 1, d);
  const dow = (new Date(today).getUTCDay() + 6) % 7;           // Monday = 0
  const monday = today - dow * 86400000;
  const first = new Date(monday - (weeks - 1) * 7 * 86400000).toISOString().slice(0, 10);
  const last = new Date(monday + 6 * 86400000).toISOString().slice(0, 10);
  return [first, last];
}

export const shortHash = (h: string) => `${h.slice(0, 8)}…${h.slice(-4)}`;
