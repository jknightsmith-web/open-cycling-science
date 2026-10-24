/** Typed access to the local API. Same origin only (spec 8.5). */
import type { components } from "./schema";

export type S = components["schemas"];
export type MetricValue = S["MetricValue"];
export type ActivityRow = S["ActivityRow"];
export type ActivityDetail = S["ActivityDetail"];
export type Series = S["Series"];
export type DuplicateGroup = S["DuplicateGroup"];
export type Ride = S["Ride"];
export type Totals = S["RangeTotals"];
export type WeekTotals = S["WeekTotals"];
export type Settings = S["Settings"];
export type Field = "timer" | "power" | "heart_rate" | "cadence" | "speed" | "distance" | "temperature";
export const FIELDS: Field[] = ["timer", "power", "heart_rate", "cadence", "speed", "distance", "temperature"];
export const CHANNELS = ["power", "heart_rate", "cadence", "speed", "distance", "temperature"] as const;
export type Channel = (typeof CHANNELS)[number];

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* body was not JSON */ }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit =>
  ({ method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  activities: (offset = 0, limit = 50) => call<S["ActivityPage"]>(`/api/activities?offset=${offset}&limit=${limit}`),
  activity: (id: number) => call<ActivityDetail>(`/api/activities/${id}`),
  samples: (id: number, offset: number, limit: number) =>
    call<S["SamplePage"]>(`/api/activities/${id}/samples?offset=${offset}&limit=${limit}`),
  series: (id: number, channel: Channel, points = 2000) =>
    call<Series>(`/api/activities/${id}/series?channel=${channel}&points=${points}`),
  imports: (offset = 0, limit = 50) => call<S["ImportLogPage"]>(`/api/imports?offset=${offset}&limit=${limit}`),
  upload: (file: File) => file.arrayBuffer().then((buf) =>
    call<S["ImportResponse"]>(`/api/imports?filename=${encodeURIComponent(file.name)}`,
      { method: "POST", headers: { "content-type": "application/octet-stream" }, body: buf })),
  groups: (status?: string) => call<DuplicateGroup[]>(`/api/duplicate-groups${status ? `?status=${status}` : ""}`),
  group: (id: number) => call<DuplicateGroup>(`/api/duplicate-groups/${id}`),
  confirm: (id: number, selection: Record<Field, number | null>, exclude: number[]) =>
    call<S["RideId"]>(`/api/duplicate-groups/${id}/confirm`, json("POST", { selection, exclude_activity_ids: exclude })),
  reject: (id: number) => call<S["StatusOut"]>(`/api/duplicate-groups/${id}/reject`, { method: "POST" }),
  reopen: (id: number) => call<S["StatusOut"]>(`/api/duplicate-groups/${id}/reopen`, { method: "POST" }),
  acceptPending: (gid: number, aid: number, selection: Record<Field, number | null>) =>
    call<S["RideId"]>(`/api/duplicate-groups/${gid}/members/${aid}/accept`, json("POST", { selection })),
  excludePending: (gid: number, aid: number) =>
    call<S["StatusOut"]>(`/api/duplicate-groups/${gid}/members/${aid}/exclude`, { method: "POST" }),
  ride: (id: number) => call<Ride>(`/api/rides/${id}`),
  changeSources: (id: number, selection: Record<Field, number | null>) =>
    call<S["RevisionOut"]>(`/api/rides/${id}/channels`, json("PUT", { selection })),
  totals: (start: number, end: number) => call<S["RangeTotals"]>(`/api/aggregates?start_utc=${start}&end_utc=${end}`),
  weekly: (tz: string, first: string, last: string) =>
    call<WeekTotals[]>(`/api/aggregates/weekly?tz=${encodeURIComponent(tz)}&first_day=${first}&last_day=${last}`),
  settings: () => call<Settings>("/api/settings"),
  saveSettings: (s: Settings) => call<Settings>("/api/settings", json("PUT", s)),
  system: () => call<S["System"]>("/api/system"),
  preferences: () => call<Record<string, Record<string, unknown>[]>>("/api/channel-preferences"),
  savePreferences: (p: Record<string, Record<string, string>[]>) =>
    call<Record<string, Record<string, unknown>[]>>("/api/channel-preferences", json("PUT", p)),
  science: () => call<S["ScienceRow"][]>("/api/science/metrics"),
  entry: (id: string) => call<RegisterEntry>(`/api/science/metrics/${id}`),
  states: () => call<StatesDoc>("/api/science/states"),
  // WP9: export, restore, deletion
  exports: () => call<S["ExportEntry"][]>("/api/exports"),
  makeExport: (kind: ExportKind) => call<S["ExportEntry"]>(`/api/exports?kind=${kind}`, { method: "POST" }),
  removeExport: (name: string) => call<S["StatusOut"]>(`/api/exports/${encodeURIComponent(name)}`, { method: "DELETE" }),
  exportUrl: (name: string) => `/api/exports/${encodeURIComponent(name)}`,
  restore: (file: File) => file.arrayBuffer().then((buf) =>
    call<S["RestoreReport"]>("/api/restore", { method: "POST", headers: { "content-type": "application/zip" }, body: buf })),
  previewDeleteActivity: (id: number) => call<Deletion>(`/api/activities/${id}/deletion`),
  deleteActivity: (id: number) => call<Deletion>(`/api/activities/${id}`, { method: "DELETE" }),
  previewDeleteFile: (id: number) => call<Deletion>(`/api/imports/${id}/deletion`),
  deleteFile: (id: number) => call<Deletion>(`/api/imports/${id}`, { method: "DELETE" }),
  deleteAllPreview: () => call<S["DeleteAllPreview"]>("/api/data/delete-all"),
  deleteAll: (token: string) => call<S["DeleteAllResult"]>("/api/data/delete-all", json("POST", { token })),
  ridesNeedingReview: () => call<number[]>("/api/rides-needing-review"),
};

export type ExportKind = "originals" | "derived" | "archive";
export type Deletion = S["DeletionReport"];

export interface SourceRef { id: string; role: string; citation?: string; doi?: string | null; status?: string }
export interface RegisterEntry {
  metric_id: string; version: string; display_name: string; classification: string; evidence_label: string;
  units: string; equation: string; variable_definitions: Record<string, string>; outputs?: Record<string, string>;
  source_refs: SourceRef[]; population_scope: string; input_requirements: string; data_quality_rules: string;
  algorithm: string; parameter_set: Record<string, unknown>; assumptions: string[]; known_limitations: string[];
  validation_protocol: string; software_test_status: string; scientific_validation_status: string;
  uncertainty_statement: string; last_reviewed: string; documentation_path: string; problems: string[];
}
export interface StatesDoc {
  classes: Record<string, string>; validity: Record<string, string>; value_states: Record<string, string>;
}
