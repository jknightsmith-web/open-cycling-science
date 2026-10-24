import { useState } from "react";
import { Link, useParams } from "react-router";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, CHANNELS, FIELDS, type ActivityDetail, type Channel, type MetricValue, type Ride } from "../api/client";
import { useZone } from "../api/hooks";
import { CHANNEL_NAMES, dateTime, duration, pct, shortHash, timeOfDay, windowLabel } from "../format/format";
import { ClassLabel, InfoButton, MetricCard } from "../components/MetricCard";
import { TimeSeriesChart } from "../components/TimeSeriesChart";
import { ValidityCell } from "../components/Validity";
import { Pager } from "../components/Pager";
import { SelectionForm, memberName } from "../components/SelectionForm";
import { InfoDrawer } from "../components/InfoDrawer";
import { DeleteRecording } from "../components/DeleteRecording";

const ORDER = ["M001", "M002", "M003", "M004"];
const sortMetrics = (ms: MetricValue[]) => [...ms].sort((a, b) => ORDER.indexOf(a.metric_id) - ORDER.indexOf(b.metric_id)
  || Number(a.parameters.duration_s ?? 0) - Number(b.parameters.duration_s ?? 0));

function Metrics({ metrics, sourceOf }: { metrics: MetricValue[]; sourceOf?: (m: MetricValue) => string | undefined }) {
  const sorted = sortMetrics(metrics);
  const main = sorted.filter((m) => m.metric_id !== "M004");
  const mmp = sorted.filter((m) => m.metric_id === "M004");
  return (
    <>
      <div className="cards">{main.map((m) => <MetricCard key={m.metric_id} metric={m} source={sourceOf?.(m)} />)}</div>
      <h2>Highest observed power</h2>
      <div className="cards">{mmp.map((m) => <MetricCard key={String(m.parameters.duration_s)} metric={m} source={sourceOf?.(m)}
        title={windowLabel(Number(m.parameters.duration_s))} />)}</div>
    </>
  );
}

function Chart({ activityId, channels }: { activityId: number; channels: Channel[] }) {
  const zone = useZone();
  const [channel, setChannel] = useState<Channel>(channels.includes("power") ? "power" : channels[0]);
  const { data, error } = useQuery({ queryKey: ["series", activityId, channel], queryFn: () => api.series(activityId, channel),
    enabled: channels.length > 0 });
  if (!channels.length) return <p className="muted">No channel to plot.</p>;
  return (
    <section>
      <div className="tabs" role="tablist" aria-label="Chart channel">
        {channels.map((c) => <button key={c} role="tab" aria-selected={c === channel} className={c === channel ? "active" : ""}
          onClick={() => setChannel(c)}>{CHANNEL_NAMES[c]}</button>)}
      </div>
      {error && <p className="error">{(error as Error).message}</p>}
      {data && <TimeSeriesChart series={data} zone={zone} />}
    </section>
  );
}

function Samples({ a }: { a: ActivityDetail }) {
  const zone = useZone();
  const [offset, setOffset] = useState(0);
  const limit = 60;
  const { data, isPlaceholderData } = useQuery({ queryKey: ["samples", a.id, offset], queryFn: () => api.samples(a.id, offset, limit), placeholderData: (prev) => prev });
  if (!data) return null;
  return (
    <details data-testid="samples">
      <summary>{data.total} samples, {limit} per page</summary>
      <table aria-label="Samples" aria-busy={isPlaceholderData}>
        <thead><tr><th>Time</th>{CHANNELS.map((c) => <th key={c}>{CHANNEL_NAMES[c]}</th>)}</tr></thead>
        <tbody>{data.items.map((s) => (
          <tr key={s.sample_index}><td className="num">{timeOfDay(s.timestamp_utc, zone)}</td>
            {CHANNELS.map((c) => <ValidityCell key={c} channel={c} value={s.channels[c].value} validity={s.channels[c].validity}
              suspect={c === "power" && s.suspect_zero} />)}</tr>))}</tbody>
      </table>
      <Pager offset={offset} limit={limit} total={data.total} onChange={setOffset} />
    </details>
  );
}

function Recording({ a }: { a: ActivityDetail }) {
  const st = a.recording_stats as Record<string, unknown>;
  const hist = (st.interval_histogram ?? {}) as Record<string, number>;
  return (
    <>
      <table aria-label="Channels">
        <thead><tr><th>Channel</th><th>In file</th><th>Origin</th><th>Observed</th><th>Invalid samples</th><th>Suspect zero</th><th>Sensor</th></tr></thead>
        <tbody>{a.channel_info.map((c) => (
          <tr key={c.channel}><td>{CHANNEL_NAMES[c.channel]}</td><td>{c.present ? "yes" : "no"}</td>
            <td>{!c.present ? "" : c.origin === "simulated" ? <span className="flag">simulated</span> : "measured"}</td>
            <td className="num">{c.present && a.timer_s ? pct(c.observed_s / a.timer_s) : ""}</td>
            <td className="num">{c.invalid_count}</td><td className="num">{c.channel === "power" ? duration(c.suspect_zero_s) || "0:00" : ""}</td>
            <td className="small">{sensorText(c.sensor_identity)}</td></tr>))}</tbody>
      </table>
      <p className="small muted">Observed is the share of timer time with an observed value, as reported by the recording statistics.</p>
      <h2>Recording statistics</h2>
      <dl className="small" style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "4px 12px" }}>
        <dt>Nominal recording interval</dt><dd>{a.nominal_interval_s ?? ""} s</dd>
        <dt>Intervals by length</dt><dd>{Object.entries(hist).sort(([a], [b]) => binOrder(a) - binOrder(b)).map(([k, v]) => `${k.replace("<=", "≤ ")}: ${v}`).join(" · ")}</dd>
        <dt>Longest interval</dt><dd>{String(st.max_interval_s ?? "")} s</dd>
        <dt>Gaps</dt><dd>{String(st.gap_count ?? 0)}, {duration(Number(st.gap_s ?? 0)) || "0:00"} in total</dd>
        <dt>Flags</dt><dd>{a.flags.length ? a.flags.map((f) => <span key={f} className="flag">{f.replace(/_/g, " ")}</span>) : "none"}
          <div className="muted">Flags describe how the file was recorded. Whether a metric can use it is decided by that metric's own rules.</div></dd>
      </dl>
    </>
  );
}

/** Histogram labels are "<=1s" to ">60s"; storage sorts them as text, so restore bin order. */
const binOrder = (k: string) => parseFloat(k.replace(/[^0-9.]/g, "")) + (k.startsWith(">") ? 0.5 : 0);

function sensorText(s: unknown): string {
  if (s === "unknown" || !s) return "unknown";
  const o = s as { match?: Record<string, unknown> | null; candidates?: unknown[] };
  if (o.match) return `${o.match.manufacturer ?? ""} ${o.match.product ?? ""} (device type ${o.match.device_type ?? o.match.antplus_device_type ?? "?"})`.trim();
  return o.candidates?.length ? `unknown (${o.candidates.length} candidates)` : "unknown";
}

function Provenance({ a }: { a: ActivityDetail }) {
  const rev = a.metrics[0]?.input_revision;
  return (
    <dl className="small" style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "4px 12px" }}>
      <dt>File</dt><dd>{a.original_filename}</dd>
      <dt>SHA256</dt><dd><code>{a.sha256}</code></dd>
      <dt>Parser</dt><dd>{a.parser_version}</dd>
      <dt>Recording identity</dt><dd>{a.original_activity_id ?? "none in file"}</dd>
      <dt>Input revision</dt><dd><code>{rev ? shortHash(rev) : ""}</code></dd>
      <dt>Computed by</dt><dd>{a.metrics[0]?.computation_version}</dd>
    </dl>
  );
}

function Header({ a }: { a: ActivityDetail }) {
  const zone = useZone();
  const [info, setInfo] = useState(false);
  return (
    <>
      <h1>{dateTime(a.start_utc, zone)}</h1>
      <p className="muted">{a.source_platform || "unknown source"} · {a.media_format.toUpperCase()} · {a.original_filename}
        {a.group && a.group.status !== "rejected" && <> · <Link to={`/library/duplicates/${a.group.id}`}>
          {a.group.status === "confirmed" && a.group.membership === "member" ? "part of a confirmed ride" : "possible duplicate"}</Link></>}
        {a.ride_id && a.group?.status === "confirmed" && a.group.membership === "member" && <> · <Link to={`/rides/${a.ride_id}`}>open ride</Link></>}</p>
      <p className="small">
        Timer {duration(a.timer_s)} ({a.timer_source === "device_events" ? "from device timer events" : "assumed continuous, no pause events in file"})
        {" · "}Elapsed {duration(a.elapsed_s)}
        {a.device_timer_s !== null && <> · Device reported timer {duration(a.device_timer_s)} <ClassLabel value="OBSERVED" /></>}
        {" "}<InfoButton label="Duration" onClick={() => setInfo(true)} />
      </p>
      {info && <InfoDrawer metricId="M001" metric={a.metrics.find((m) => m.metric_id === "M001")} onClose={() => setInfo(false)} />}
    </>
  );
}

export function ActivityScreen() {
  const id = Number(useParams().id);
  const { data: a, error, isLoading } = useQuery({ queryKey: ["activity", id], queryFn: () => api.activity(id) });
  if (isLoading) return <p className="muted">Loading…</p>;
  if (error || !a) return <p className="error">{error ? (error as Error).message : "Not found"}</p>;
  const plotted = CHANNELS.filter((c) => a.channels[c]?.present);
  return (
    <article data-testid="activity">
      <Header a={a} />
      <Metrics metrics={a.metrics} />
      <h2>Recording</h2>
      <Chart activityId={a.id} channels={plotted} />
      <Recording a={a} />
      <h2>Samples</h2>
      <Samples a={a} />
      <h2>Provenance</h2>
      <Provenance a={a} />
      <h2>Delete</h2>
      <p className="small muted">Removes this recording and everything derived from it. Other recordings are not changed.</p>
      <DeleteRecording activityId={a.id} />
    </article>
  );
}

function RideSources({ ride, members }: { ride: Ride; members: ActivityDetail[] }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (sel: Parameters<typeof api.changeSources>[1]) => api.changeSources(ride.id, sel),
    onSuccess: () => { setEditing(false); setProblem(null); qc.invalidateQueries(); },
    onError: (e) => setProblem(e instanceof ApiError ? e.message : String(e)),
  });
  const name = (aid: number | null | undefined) => {
    const m = members.find((x) => x.id === aid);
    return m ? memberName(m) : <span className="state-word">none: missing for this ride</span>;
  };
  return (
    <>
      <table aria-label="Sources">
        <thead><tr><th>Field</th><th>Source</th></tr></thead>
        <tbody>{FIELDS.map((f) => <tr key={f} data-field={f}><td>{CHANNEL_NAMES[f]}</td><td>{name(ride.sources[f])}</td></tr>)}</tbody>
      </table>
      {problem && <p className="error" role="alert">{problem}</p>}
      {ride.kind === "group" && ride.active && !editing && <p><button onClick={() => setEditing(true)}>Change sources</button></p>}
      {editing && <SelectionForm members={members} initial={ride.sources} submitLabel="Save sources" busy={save.isPending}
        onSubmit={(sel) => save.mutate(sel)} />}
    </>
  );
}

export function RideScreen() {
  const id = Number(useParams().id);
  const zone = useZone();
  const { data: ride, error } = useQuery({ queryKey: ["ride", id], queryFn: () => api.ride(id) });
  const members = useQueries({ queries: (ride?.members ?? []).map((m) => ({ queryKey: ["activity", m], queryFn: () => api.activity(m) })) });
  const [shown, setShown] = useState<number | null>(null);
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!ride || members.some((m) => !m.data)) return <p className="muted">Loading…</p>;
  const acts = members.map((m) => m.data!);
  const timer = acts.find((a) => a.id === ride.sources.timer) ?? acts[0];
  if (!timer) return <p className="muted">This ride has no recordings left.</p>;
  const chartAct = acts.find((a) => a.id === (shown ?? ride.sources.power ?? timer.id)) ?? timer;
  const sourceOf = (m: MetricValue) => {
    const a = acts.find((x) => x.id === m.source_activity_ids[0]);
    return a ? `from ${memberName(a)}` : undefined;
  };
  return (
    <article data-testid="ride">
      <h1>{dateTime(timer.start_utc, zone)}</h1>
      <p className="muted">{ride.kind === "group" ? `Ride confirmed from ${acts.length} recordings` : "Ride from one recording"}
        {!ride.active && " · not counted: the group was reopened"}
        {ride.group_id && <> · <Link to={`/library/duplicates/${ride.group_id}`}>group {ride.group_id}</Link></>}</p>
      {ride.needs_review && (
        <div className="notice" role="status" data-testid="needs-review">
          <span>A recording this ride used was deleted. {FIELDS.filter((f) => ride.sources[f] === null && acts.some((a) => f === "timer" || a.channels[f]?.present))
            .map((f) => CHANNEL_NAMES[f]).join(", ") || "Some fields"} now have no source.
            {ride.sources.timer === null && " Without a timer source the ride is not counted in totals."} Choose the sources again below.</span>
        </div>)}
      {ride.metrics.length > 0 ? <Metrics metrics={ride.metrics} sourceOf={sourceOf} />
        : <p className="muted">No values until a timer source is chosen.</p>}
      <h2>Sources</h2>
      <RideSources ride={ride} members={acts} />
      <h2>Recordings</h2>
      <ul>{acts.map((a) => <li key={a.id}><Link to={`/activities/${a.id}`}>{memberName(a)}</Link> · timer {duration(a.timer_s)}</li>)}</ul>
      <h2>Chart</h2>
      <p className="small muted">One recording at a time. Clocks of different devices are not aligned in Phase One.</p>
      {acts.length > 1 && <div className="row" role="radiogroup" aria-label="Recording to plot">{acts.map((a) => (
        <label key={a.id}><input type="radio" checked={a.id === chartAct.id} onChange={() => setShown(a.id)} /> {memberName(a)}</label>))}</div>}
      <Chart key={chartAct.id} activityId={chartAct.id} channels={CHANNELS.filter((c) => chartAct.channels[c]?.present)} />
      <h2>Selection history</h2>
      <table aria-label="Selection history"><tbody>{ride.selection_history.filter((h) => h.selected_by === "rider").map((h) => (
        <tr key={h.id}><td>revision {h.selection_revision}</td><td>{dateTime(h.selected_at_utc, zone)}</td><td>{CHANNEL_NAMES[h.channel]}</td>
          <td>{h.activity_id ? `#${h.activity_id}` : "none"}</td></tr>))}</tbody></table>
    </article>
  );
}
