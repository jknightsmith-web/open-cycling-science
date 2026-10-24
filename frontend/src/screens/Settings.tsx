import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, FIELDS, type ExportKind, type S } from "../api/client";
import { useSettings, useZone } from "../api/hooks";
import { CHANNEL_NAMES, dateTime, systemZone } from "../format/format";

const RULE_KEYS = ["source_platform", "source_format", "product"] as const;
type Rule = Record<string, string>;

function Preferences() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["preferences"], queryFn: api.preferences });
  const [prefs, setPrefs] = useState<Record<string, Rule[]>>({});
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (data) setPrefs(data as Record<string, Rule[]>); }, [data]);
  const save = useMutation({
    mutationFn: () => api.savePreferences(Object.fromEntries(Object.entries(prefs).filter(([, r]) => r.length))),
    onSuccess: () => { setMsg("Saved."); qc.invalidateQueries({ queryKey: ["preferences"] }); qc.invalidateQueries({ queryKey: ["group"] }); },
    onError: (e) => setMsg(e instanceof ApiError ? e.message : String(e)),
  });
  const update = (f: string, rules: Rule[]) => setPrefs({ ...prefs, [f]: rules });
  return (
    <section>
      <h2>Channel source preferences</h2>
      <p className="small muted">Rules only prefill the confirmation form for a duplicate ride, in order. They are never applied without your confirmation.</p>
      <table aria-label="Preferences">
        <thead><tr><th>Field</th><th>Rules, first match wins</th></tr></thead>
        <tbody>{FIELDS.map((f) => {
          const rules = prefs[f] ?? [];
          return (
            <tr key={f} data-field={f}><td>{CHANNEL_NAMES[f]}</td><td>
              {rules.map((r, i) => {
                const [k, v] = Object.entries(r)[0] ?? ["source_format", ""];
                return (
                  <div className="row" key={i} style={{ marginBottom: 4 }}>
                    <span className="small muted">{i + 1}.</span>
                    <select aria-label="Match on" value={k} onChange={(e) => update(f, rules.map((x, j) => (j === i ? { [e.target.value]: v } : x)))}>
                      {RULE_KEYS.map((key) => <option key={key} value={key}>{key.replace(/_/g, " ")}</option>)}</select>
                    <input aria-label="Value" value={v} onChange={(e) => update(f, rules.map((x, j) => (j === i ? { [k]: e.target.value } : x)))} />
                    <button type="button" disabled={i === 0} onClick={() => { const r2 = [...rules]; [r2[i - 1], r2[i]] = [r2[i], r2[i - 1]]; update(f, r2); }}>Up</button>
                    <button type="button" onClick={() => update(f, rules.filter((_, j) => j !== i))}>Remove</button>
                  </div>);
              })}
              <button type="button" onClick={() => update(f, [...rules, { source_format: "" }])}>Add rule</button>
            </td></tr>);
        })}</tbody>
      </table>
      <p><button className="primary" onClick={() => save.mutate()} disabled={save.isPending}>Save preferences</button> <span className="small">{msg}</span></p>
    </section>
  );
}

const mb = (b: number) => `${(b / 1024 / 1024).toFixed(1)} MB`;
const err = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

const KINDS: { kind: ExportKind; title: string; what: string; gps: boolean }[] = [
  { kind: "archive", title: "Full archive", gps: true,
    what: "Original files, all derived data and a manifest with the SHA256 of every file. Restores into an empty install." },
  { kind: "derived", title: "Derived data", gps: false,
    what: "One CSV per table and the same rows as JSON Lines: activities, samples with validity, timer events, duplicate groups and decisions, ride sources, metric definitions, runs and values. No location." },
  { kind: "originals", title: "Original files", gps: true, what: "Every imported file, byte identical, under its original name." },
];

function Exports() {
  const qc = useQueryClient();
  const zone = useZone();
  const { data: list } = useQuery({ queryKey: ["exports"], queryFn: api.exports });
  const [msg, setMsg] = useState<string | null>(null);
  const make = useMutation({
    mutationFn: (k: ExportKind) => api.makeExport(k),
    onSuccess: (e) => { setMsg(`Saved ${e.name}.`); qc.invalidateQueries({ queryKey: ["exports"] }); },
    onError: (e) => setMsg(err(e)),
  });
  const remove = useMutation({ mutationFn: api.removeExport, onSuccess: () => qc.invalidateQueries({ queryKey: ["exports"] }) });
  return (
    <>
      <h3>Export</h3>
      <p className="notice small" role="note">Original files are unchanged and may contain GPS positions, including where your rides start and end, such as home. Derived data contains no location.</p>
      <table aria-label="Export kinds"><tbody>{KINDS.map((k) => (
        <tr key={k.kind}><td style={{ width: 160 }}><b>{k.title}</b>{k.gps && <div className="flag">contains GPS</div>}</td>
          <td className="small">{k.what}</td>
          <td style={{ width: 120 }}><button onClick={() => make.mutate(k.kind)} disabled={make.isPending}>Export</button></td></tr>))}</tbody></table>
      {make.isPending && <p className="small muted">Writing the export…</p>}
      {msg && <p className="small" role="status">{msg}</p>}
      {list && list.length > 0 && (
        <table aria-label="Saved exports">
          <thead><tr><th>Saved export</th><th>Kind</th><th>Made</th><th>Recordings</th><th>Size</th><th /></tr></thead>
          <tbody>{list.map((e) => (
            <tr key={e.name} data-export={e.name}><td><a href={api.exportUrl(e.name)} download>{e.name}</a></td><td>{e.kind}</td>
              <td>{e.created_at_utc ? dateTime(e.created_at_utc, zone) : ""}</td><td className="num">{e.recordings}</td>
              <td className="num">{mb(e.bytes)}</td>
              <td><button className="small" onClick={() => remove.mutate(e.name)}>Remove</button></td></tr>))}</tbody>
        </table>)}
      <p className="small muted">Exports are kept in the data folder's exports folder until you remove them. Deleting a recording also removes every export here that contains it. A copy you download is yours to manage.</p>
    </>
  );
}

function Restore({ empty }: { empty: boolean }) {
  const qc = useQueryClient();
  const [report, setReport] = useState<S["RestoreReport"] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const send = async (f: File) => {
    setBusy(true); setProblem(null); setReport(null);
    try { setReport(await api.restore(f)); qc.invalidateQueries(); } catch (e) { setProblem(err(e)); }
    setBusy(false);
  };
  return (
    <>
      <h3>Restore a full archive</h3>
      {empty
        ? <label>Archive (.zip){" "}<input type="file" accept=".zip" aria-label="Archive to restore" disabled={busy}
            onChange={(e) => e.target.files?.[0] && send(e.target.files[0])} /></label>
        : <p className="small muted">Restoring needs an empty library, so nothing is merged or overwritten. Use Delete everything first if you mean to replace this library.</p>}
      {busy && <p className="small muted">Checking every file against the manifest and recomputing from the originals…</p>}
      {problem && <p className="error" role="alert">Not restored, nothing changed: {problem}</p>}
      {report && <p role="status" data-testid="restore-report">Restored {report.vault_objects} original files, {report.restored_rows.activities} activities and {report.restored_rows.samples} samples.
        Recomputing every activity from its original {report.recompute_check.status === "passed" ? "reproduced the archived values exactly" : `was skipped: ${String(report.recompute_check.reason)}`}.</p>}
    </>
  );
}

function DeleteEverything() {
  const qc = useQueryClient();
  const [plan, setPlan] = useState<S["DeleteAllPreview"] | null>(null);
  const [done, setDone] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const go = useMutation({
    mutationFn: () => api.deleteAll(plan!.token),
    onSuccess: () => { setPlan(null); setDone(true); qc.resetQueries(); },
    onError: (e) => setProblem(err(e)),
  });
  return (
    <>
      <h3>Delete everything</h3>
      {done && <p role="status">Everything was deleted. The library is empty.</p>}
      {!plan && <button className="danger" onClick={() => api.deleteAllPreview().then(setPlan, (e) => setProblem(err(e)))}>Delete everything…</button>}
      {plan && (
        <div className="card confirm" role="alertdialog" aria-label="Confirm delete everything">
          <b>Delete everything in {plan.data_root}?</b>
          <ul className="small">
            <li>{plan.counts.recordings} original files, {plan.counts.activities} activities and {plan.counts.duplicate_groups} duplicate groups, with every derived value and decision.</li>
            {plan.entries.map((e) => <li key={e.path}><code>{e.path}</code> ({mb(e.bytes)})</li>)}
            {plan.exports.length > 0 && <li>Saved exports: {plan.exports.join(", ")}</li>}
            {plan.kept_not_ours.length > 0 && <li>Kept, because the app did not create them: {plan.kept_not_ours.join(", ")}</li>}
          </ul>
          <div className="row">
            <button className="danger" onClick={() => go.mutate()} disabled={go.isPending}>Delete everything</button>
            <button onClick={() => setPlan(null)}>Cancel</button>
          </div>
        </div>)}
      {problem && <p className="error" role="alert">{problem}</p>}
    </>
  );
}

const CANNOT_DELETE = [
  "Copies outside the data folder: exports you downloaded or moved, and anything you copied yourself.",
  "Time Machine backups and APFS local snapshots that already hold the data.",
  "Physical blocks on the SSD. Deleted files are removed and database pages overwritten, but the drive may keep old blocks until it reuses them; FileVault encryption protects them.",
  "Recordings in vendor accounts such as Garmin Connect, Wattbike or MyWhoosh.",
];

function DataSection({ sys }: { sys?: S["System"] }) {
  const { data: page } = useQuery({ queryKey: ["activities", 0], queryFn: () => api.activities(0, 1) });
  const empty = !!sys && sys.vault_objects === 0 && page?.total === 0;
  return (
    <section>
      <h2>Data</h2>
      {sys && <dl className="small" style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "4px 12px" }}>
        <dt>Location</dt><dd><code>{sys.data_root}</code></dd>
        <dt>Database</dt><dd>{mb(sys.database_bytes)}</dd>
        <dt>Original files</dt><dd>{sys.vault_objects} files, {mb(sys.vault_bytes)}</dd>
      </dl>}
      <Exports />
      <Restore empty={empty} />
      <DeleteEverything />
      <h3>What the app cannot delete</h3>
      <ul className="small">{CANNOT_DELETE.map((x) => <li key={x}>{x}</li>)}</ul>
      <p className="small muted">To delete one recording, open it and use Delete at the bottom of the page.</p>
    </section>
  );
}

export function SettingsScreen() {
  const qc = useQueryClient();
  const { data: settings } = useSettings();
  const { data: sys } = useQuery({ queryKey: ["system"], queryFn: api.system });
  const zones = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone") ?? ["UTC"];
  const save = useMutation({
    mutationFn: (tz: string | null) => api.saveSettings({ display_time_zone: tz, week_start: "monday" }),
    onSuccess: (s) => { qc.setQueryData(["settings"], s); qc.invalidateQueries({ queryKey: ["weekly"] }); },
  });
  return (
    <>
      <h1>Settings</h1>
      <section>
        <h2>Display</h2>
        <label>Time zone{" "}
          <select aria-label="Display time zone" value={settings?.display_time_zone ?? ""} onChange={(e) => save.mutate(e.target.value || null)}>
            <option value="">This Mac ({systemZone()})</option>
            {zones.map((z) => <option key={z} value={z}>{z}</option>)}
          </select></label>
        <p className="small muted">Weeks start on Monday (ISO). The time zone changes labels and week grouping only, never a computed value.</p>
      </section>
      <Preferences />
      <DataSection sys={sys} />
      <section>
        <h2>About</h2>
        {sys && <dl className="small" style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "4px 12px" }}>
          <dt>Version</dt><dd>{sys.app_version} (computation {sys.computation_version})</dd>
          <dt>Metric register</dt><dd>{sys.registry.map((r) => `${r.metric_id} v${r.version}`).join(", ")}</dd>
          <dt>Network</dt><dd>Runs on {sys.host} only. No account, cloud service or outbound connection.</dd>
          <dt>Licence</dt><dd>MIT. Dependency licences are listed in DEPENDENCIES.md.</dd>
        </dl>}
      </section>
    </>
  );
}
