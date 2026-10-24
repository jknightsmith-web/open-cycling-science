import { useState } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, CHANNELS, type ActivityRow, type DuplicateGroup, type S } from "../api/client";
import { useZone } from "../api/hooks";
import { CHANNEL_NAMES, dateTime, duration, pct } from "../format/format";
import { Pager } from "../components/Pager";
import { SelectionForm, memberName } from "../components/SelectionForm";
import { DeleteRecording } from "../components/DeleteRecording";

const PAGE = 50;

export function Library() {
  const deleted = (useLocation().state as { deleted?: boolean } | null)?.deleted;
  return (
    <>
      <h1>Library</h1>
      {deleted && <p className="notice" role="status">The recording was deleted.</p>}
      <Importer />
      <div className="tabs" role="tablist">
        <NavLink to="/library" end>Activities</NavLink>
        <NavLink to="/library/imports">Imports</NavLink>
        <NavLink to="/library/duplicates">Duplicates</NavLink>
      </div>
      <Routes>
        <Route index element={<Activities />} />
        <Route path="imports" element={<Imports />} />
        <Route path="duplicates" element={<Duplicates />} />
        <Route path="duplicates/:groupId" element={<GroupDetail />} />
      </Routes>
    </>
  );
}

function Importer() {
  const qc = useQueryClient();
  const [over, setOver] = useState(false);
  const [results, setResults] = useState<S["ImportOutcome"][]>([]);
  const [busy, setBusy] = useState(false);
  async function send(files: FileList | File[]) {
    setBusy(true);
    const out: S["ImportOutcome"][] = [];
    for (const f of Array.from(files)) {
      try { out.push(...(await api.upload(f)).outcomes); }
      catch (e) { out.push({ filename: f.name, status: "failed", error_code: "upload", message: (e as Error).message }); }
    }
    setResults(out);
    setBusy(false);
    qc.invalidateQueries();
  }
  return (
    <>
      <div className={`drop${over ? " over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }}
           onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); send(e.dataTransfer.files); }}>
        Drop FIT, TCX or ZIP files here, or{" "}
        <label className="row" style={{ display: "inline-flex" }}>
          <input type="file" multiple accept=".fit,.tcx,.zip" aria-label="Choose files" disabled={busy}
                 onChange={(e) => e.target.files && send(e.target.files)} />
        </label>
        <div className="small muted">Files stay on this Mac. Originals are stored unchanged.</div>
      </div>
      {results.length > 0 && (
        <table aria-label="Import results" style={{ marginBottom: 16 }}>
          <tbody>{results.map((r, i) => <tr key={i} data-status={r.status}><td>{r.filename}</td><td><Outcome r={r} /></td></tr>)}</tbody>
        </table>
      )}
    </>
  );
}

function Outcome({ r }: { r: S["ImportOutcome"] }) {
  if (r.status === "imported") return <>Imported. <Link to={`/activities/${r.activity_id}`}>Open</Link>
    {r.group_id && <> · possible duplicate, <Link to={`/library/duplicates/${r.group_id}`}>review</Link></>}</>;
  if (r.status === "duplicate_bytes") return <>Identical file already imported{r.activity_id ? <>, <Link to={`/activities/${r.activity_id}`}>open it</Link></> : null}. Nothing added.</>;
  return <span className="error">Failed ({r.error_code}): {r.message}</span>;
}

function channelMark(a: ActivityRow, ch: string) {
  const c = a.channels[ch];
  if (!c?.present) return <span className="state-word" title="Not in this file">none</span>;
  return c.origin === "simulated" ? <span className="flag" title="Simulated by the source, not measured">simulated</span> : <span title="Recorded">✓</span>;
}

export function ActivityTable({ rows }: { rows: ActivityRow[] }) {
  const zone = useZone();
  return (
    <table aria-label="Activities">
      <thead><tr><th>Date ({zone})</th><th>Source</th><th>Timer</th>
        {CHANNELS.slice(0, 4).map((c) => <th key={c}>{CHANNEL_NAMES[c]}</th>)}<th>Flags</th><th>Ride</th></tr></thead>
      <tbody>
        {rows.map((a) => (
          <tr key={a.id} data-activity={a.id}>
            <td><Link to={`/activities/${a.id}`}>{dateTime(a.start_utc, zone)}</Link></td>
            <td>{a.source_platform || "unknown"} <span className="muted small">{a.media_format.toUpperCase()}</span></td>
            <td className="num">{duration(a.timer_s)}{a.timer_source === "assumed_continuous" && <span className="muted small" title="No timer events in the file; timer assumed to run throughout"> assumed</span>}</td>
            {CHANNELS.slice(0, 4).map((c) => <td key={c}>{channelMark(a, c)}</td>)}
            <td>{a.flags.map((f) => <span key={f} className="flag" title="Descriptive flag, not a quality verdict">{f.replace(/_/g, " ")}</span>)}</td>
            <td>{a.group && a.group.status !== "rejected"
              ? <Link to={`/library/duplicates/${a.group.id}`}>{a.group.status === "confirmed" && a.group.membership === "member" ? "confirmed group" : a.group.membership === "pending" ? "pending" : "possible duplicate"}</Link>
              : "single"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Activities() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error } = useQuery({ queryKey: ["activities", offset], queryFn: () => api.activities(offset, PAGE), placeholderData: (prev) => prev });
  if (isLoading) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!data?.total) return <p className="muted">No activities yet. Import a FIT, TCX or ZIP file above.</p>;
  return <><ActivityTable rows={data.items} /><Pager offset={offset} limit={PAGE} total={data.total} onChange={setOffset} /></>;
}

function Imports() {
  const zone = useZone();
  const [offset, setOffset] = useState(0);
  const { data } = useQuery({ queryKey: ["imports", offset], queryFn: () => api.imports(offset, PAGE), placeholderData: (prev) => prev });
  if (!data) return <p className="muted">Loading…</p>;
  return (
    <>
      <table aria-label="Import log">
        <thead><tr><th>Imported</th><th>File</th><th>Format</th><th>Result</th><th>SHA256</th></tr></thead>
        <tbody>{data.items.map((r) => (
          <tr key={r.source_file_id} data-status={r.validation_status}>
            <td>{dateTime(r.imported_at_utc, zone)}</td><td>{r.original_filename}</td><td>{r.media_format.toUpperCase()}</td>
            <td>{r.validation_status === "ok" ? <Link to={`/activities/${r.activity_id}`}>imported</Link>
              : <><span className="error">failed ({String(r.error?.code)}): {String(r.error?.message)}</span>{" "}
                <DeleteRecording sourceFileId={r.source_file_id} compact /></>}</td>
            <td><code className="small" title={r.sha256}>{r.sha256.slice(0, 12)}…</code></td>
          </tr>))}</tbody>
      </table>
      <Pager offset={offset} limit={PAGE} total={data.total} onChange={setOffset} />
      <p className="small muted">Re-importing identical bytes adds nothing, and a file that is not FIT, TCX or ZIP is not stored. Both are reported at import time only, so they do not appear here.</p>
    </>
  );
}

function Duplicates() {
  const zone = useZone();
  const { data } = useQuery({ queryKey: ["groups"], queryFn: () => api.groups() });
  if (!data) return <p className="muted">Loading…</p>;
  if (!data.length) return <p className="muted">No possible duplicate rides.</p>;
  const order = ["proposed", "confirmed", "rejected"];
  const sorted = [...data].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status) || b.id - a.id);
  return (
    <table aria-label="Duplicate groups">
      <thead><tr><th>Group</th><th>Status</th><th>Recordings</th><th>Proposed</th></tr></thead>
      <tbody>{sorted.map((g) => {
        const pending = g.members.filter((m) => m.membership === "pending").length;
        return (
          <tr key={g.id} data-group={g.id} data-status={g.status}>
            <td><Link to={`/library/duplicates/${g.id}`}>Group {g.id}</Link></td>
            <td>{g.status}{pending > 0 && <span className="badge">{pending} pending</span>}</td>
            <td>{g.members.filter((m) => m.membership !== "excluded").length}</td>
            <td>{dateTime(g.proposed_at_utc, zone)}</td>
          </tr>);
      })}</tbody>
    </table>
  );
}

function Evidence({ g }: { g: DuplicateGroup }) {
  const pairs = (g.evidence.pairs ?? []) as Record<string, unknown>[];
  const rule = g.evidence.rule as { overlap_threshold?: number } | undefined;
  return (
    <table aria-label="Evidence">
      <thead><tr><th>Pair</th><th>Timer overlap</th><th>Start offset</th><th>Timer durations</th><th>Same recording identity</th><th>Same device</th></tr></thead>
      <tbody>{pairs.map((p, i) => {
        const ids = p.activity_ids as number[], t = p.timer_s as number[];
        return (
          <tr key={i}>
            <td>#{ids[0]} and #{ids[1]}</td><td>{pct(p.overlap_fraction as number)}</td>
            <td>{p.start_offset_s === null ? "" : `${Number(p.start_offset_s) >= 0 ? "+" : ""}${Number(p.start_offset_s).toFixed(0)} s`}</td>
            <td>{duration(t[0])} / {duration(t[1])}</td><td>{p.same_recording_identity ? "yes" : "no"}</td><td>{p.same_device ? "yes" : "no"}</td>
          </tr>);
      })}</tbody>
      <caption className="small muted" style={{ captionSide: "bottom", textAlign: "left", paddingTop: 6 }}>
        Rule {g.rule_version}: proposed when timer overlap is at least {pct(rule?.overlap_threshold ?? 0.8)} of the shorter recording, or the recording identity matches. A proposal changes nothing until you decide.</caption>
    </table>
  );
}

function GroupDetail() {
  const id = Number(useParams().groupId);
  const zone = useZone();
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data: g, error } = useQuery({ queryKey: ["group", id], queryFn: () => api.group(id) });
  const visible = g ? g.members.filter((m) => m.membership !== "excluded") : [];
  const details = useQueries({ queries: visible.map((m) => ({ queryKey: ["activity", m.activity_id], queryFn: () => api.activity(m.activity_id) })) });
  const [excluded, setExcluded] = useState<number[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => { setProblem(null); qc.invalidateQueries(); },
    onError: (e) => setProblem(e instanceof ApiError ? e.message : String(e)),
  });
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!g || details.some((d) => !d.data)) return <p className="muted">Loading…</p>;
  const acts = details.map((d) => d.data!);
  const membersOnly = acts.filter((a) => g.members.find((m) => m.activity_id === a.id)?.membership === "member");
  const pending = acts.filter((a) => g.members.find((m) => m.activity_id === a.id)?.membership === "pending");
  const included = membersOnly.filter((a) => !excluded.includes(a.id));

  return (
    <section aria-label={`Group ${g.id}`}>
      <h2>Possible duplicate ride, group {g.id} <span className="flag">{g.status}</span></h2>
      <p className="small muted">Proposed {dateTime(g.proposed_at_utc, zone)}. Original files are never changed, merged or deleted.</p>
      <Evidence g={g} />
      <h2>Recordings</h2>
      <ul>{acts.map((a) => (
        <li key={a.id}>
          {g.status === "proposed" && <input type="checkbox" aria-label={`Include ${memberName(a)}`} checked={!excluded.includes(a.id)}
            onChange={(e) => setExcluded(e.target.checked ? excluded.filter((x) => x !== a.id) : [...excluded, a.id])} />}{" "}
          <Link to={`/activities/${a.id}`}>{memberName(a)}</Link> · {dateTime(a.start_utc, zone)} · timer {duration(a.timer_s)}
          {pending.includes(a) && <span className="badge">pending</span>}
        </li>))}</ul>
      {problem && <p className="error" role="alert">{problem}</p>}

      {g.status === "proposed" && (
        <>
          <h2>Choose the source for each field</h2>
          <SelectionForm key={included.map((a) => a.id).join(",")} members={included} prefill={g.selection_prefill}
            submitLabel="Confirm as one ride" busy={act.isPending}
            onSubmit={(sel) => act.mutate(() => api.confirm(g.id, sel, excluded).then((r) => nav(`/rides/${r.ride_id}`)))} />
          <p><button onClick={() => act.mutate(() => api.reject(g.id))}>Not the same ride</button></p>
        </>
      )}
      {g.status === "confirmed" && (
        <>
          <p>Counted as one ride. <Link to={`/rides/${g.ride_id}`}>Open the ride</Link> to change sources.</p>
          {pending.map((p) => (
            <div key={p.id} className="card" style={{ marginBottom: 12 }}>
              <h2 style={{ marginTop: 0 }}>Pending: {memberName(p)}</h2>
              <p className="small muted">This recording matches the confirmed ride. It counts as its own ride until you accept or exclude it.</p>
              <SelectionForm members={[...membersOnly, p]} prefill={g.selection_prefill} submitLabel="Add to this ride" busy={act.isPending}
                onSubmit={(sel) => act.mutate(() => api.acceptPending(g.id, p.id, sel))} />
              <p><button onClick={() => act.mutate(() => api.excludePending(g.id, p.id))}>Keep separate</button></p>
            </div>))}
          <p><button onClick={() => act.mutate(() => api.reopen(g.id))}>Reopen (count recordings separately until decided)</button></p>
        </>
      )}
      {g.status === "rejected" && <p>Kept as separate rides. <button onClick={() => act.mutate(() => api.reopen(g.id))}>Reopen</button></p>}

      <h2>History</h2>
      <table aria-label="Decision history"><tbody>{g.events.map((e) => (
        <tr key={e.id}><td>{dateTime(e.at_utc, zone)}</td><td>{e.action.replace(/_/g, " ")}</td><td>{e.actor}</td>
          <td className="small muted">{e.activity_id ? `#${e.activity_id}` : ""}</td></tr>))}</tbody></table>
    </section>
  );
}
