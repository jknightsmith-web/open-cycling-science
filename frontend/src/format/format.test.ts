import { describe, expect, it } from "vitest";
import { channelText, dayIn, duration, metricText, unavailableReason, weekRange } from "./format";
import type { MetricValue } from "../api/client";

const base: MetricValue = {
  metric_id: "M002", version: "1.0", display_name: "Recorded mean power", classification: "DERIVED", units: "W",
  value: 207.4, state: "valid", coverage: 0.992, parameters: { min_coverage: 0.95 }, details: {},
  input_revision: "x", computation_version: "ocs-0.1.0", calculated_at_utc: 0, source_sha256: [],
  source_activity_ids: [], uncertainty: "not quantified", register_url: "", catalogue_url: "",
};

describe("formatting never turns absence into zero", () => {
  it("shows observed zero as zero", () => {
    expect(channelText("power", 0)).toBe("0 W");
    expect(metricText({ ...base, value: 0 }).main).toBe("0 W");
  });
  it("shows an unavailable metric by its reason, never a number", () => {
    const t = metricText({ ...base, value: null, state: "insufficient_coverage", coverage: 0.81 });
    expect(t.available).toBe(false);
    expect(t.main).toBe("Not available");
    expect(t.note).toBe("only 81.0% of time has power (needs 95.0%)");
  });
  it("labels a lower bound", () => {
    const t = metricText({ ...base, metric_id: "M003", units: "kJ", value: 432, state: "lower_bound", coverage: 0.81 });
    expect(t.main).toBe("at least 432 kJ");
  });
  it("treats a valid state with a null value as unavailable", () => {
    expect(metricText({ ...base, value: null }).available).toBe(false);
  });
  it("names MMP windows that are too long", () => {
    expect(unavailableReason({ state: "insufficient_coverage", coverage: null, parameters: { duration_s: 1200 }, details: {} }))
      .toBe("no unbroken stretch of power as long as 20 min");
  });
});

describe("units and time", () => {
  it("converts speed and distance for display only", () => {
    expect(channelText("speed", 10)).toBe("36.0 km/h");
    expect(channelText("distance", 12345)).toBe("12.35 km");
  });
  it("formats durations", () => {
    expect(duration(3725)).toBe("1:02:05");
    expect(duration(65)).toBe("1:05");
    expect(duration(null)).toBe("");
  });
  it("places an instant in the display zone", () => {
    expect(dayIn(1760311800, "UTC")).toBe("2025-10-12");
    expect(dayIn(1760311800, "Europe/Berlin")).toBe("2025-10-13");
  });
  it("builds ISO week ranges starting Monday", () => {
    expect(weekRange(1760311800, "UTC", 2)).toEqual(["2025-09-29", "2025-10-12"]);
    expect(weekRange(1760311800, "Europe/Berlin", 1)).toEqual(["2025-10-13", "2025-10-19"]);
  });
});
