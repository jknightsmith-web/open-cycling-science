import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, FIELDS } from "../api/client";
import { useSettings } from "../api/hooks";
import { CHANNEL_NAMES, systemZone } from "../format/format";

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

export function SettingsScreen() {
  const qc = useQueryClient();
  const { data: settings } = useSettings();
  const { data: sys } = useQuery({ queryKey: ["system"], queryFn: api.system });
  const zones = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone") ?? ["UTC"];
  const save = useMutation({
    mutationFn: (tz: string | null) => api.saveSettings({ display_time_zone: tz, week_start: "monday" }),
    onSuccess: (s) => { qc.setQueryData(["settings"], s); qc.invalidateQueries({ queryKey: ["weekly"] }); },
  });
  const mb = (b: number) => `${(b / 1024 / 1024).toFixed(1)} MB`;
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
      <section>
        <h2>Data</h2>
        {sys && <dl className="small" style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "4px 12px" }}>
          <dt>Location</dt><dd><code>{sys.data_root}</code></dd>
          <dt>Database</dt><dd>{mb(sys.database_bytes)}</dd>
          <dt>Original files</dt><dd>{sys.vault_objects} files, {mb(sys.vault_bytes)}</dd>
        </dl>}
        <p className="small muted">Export and deletion arrive with WP9.</p>
      </section>
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
