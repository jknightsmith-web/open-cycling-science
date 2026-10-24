import { useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api, type WeekTotals } from "../api/client";
import { useZone } from "../api/hooks";
import { duration, number, weekRange, windowLabel } from "../format/format";
import { ActivityTable } from "./Library";
import { InfoButton, ClassLabel } from "../components/MetricCard";
import { InfoDrawer } from "../components/InfoDrawer";

const RANGES = [4, 12, 26, 52];

function WeekBars({ weeks, kind }: { weeks: WeekTotals[]; kind: "duration" | "work" }) {
  const value = (w: WeekTotals) => (kind === "duration" ? w.duration_s : w.work_kj);
  const over = (w: WeekTotals) => (kind === "duration" ? w.potential_overcount.duration_s : w.potential_overcount.work_kj);
  const top = Math.max(1, ...weeks.map(value));
  return (
    <div className="weeks" role="table" aria-label={kind === "duration" ? "Weekly duration" : "Weekly work"}>
      {weeks.map((w) => {
        const v = value(w), o = Math.min(over(w), v);
        const noPower = w.rides_by_work_state.no_power ?? 0;
        const lower = w.rides_by_work_state.lower_bound ?? 0;
        return (
          <div key={w.week} role="row" style={{ display: "contents" }}>
            <span role="cell" className="small">{w.week}</span>
            <span role="cell" className="barrow" title={o > 0 ? "Hatched part: possible duplicates not yet confirmed" : undefined}>
              <span className="bar" style={{ width: `${((v - o) / top) * 100}%` }} />
              {o > 0 && <span className="bar over" style={{ width: `${(o / top) * 100}%` }} />}
            </span>
            <span role="cell" className="small num">
              {kind === "duration" ? duration(v) || "0:00" : `${lower ? "at least " : ""}${number("kJ", v)}`}
              {kind === "work" && noPower > 0 && <span className="muted"> · {noPower} without power</span>}
              <span className="muted"> · {w.ride_count} rides</span>
            </span>
          </div>);
      })}
    </div>
  );
}

export function Overview() {
  const zone = useZone();
  const [weeks, setWeeks] = useState(12);
  const [first, last] = weekRange(Date.now() / 1000, zone, weeks);
  const weekly = useQuery({ queryKey: ["weekly", zone, first, last], queryFn: () => api.weekly(zone, first, last) });
  const span = weekly.data?.length ? [weekly.data[0].start_utc, weekly.data[weekly.data.length - 1].end_utc] : null;
  const totals = useQuery({ queryKey: ["totals", span], queryFn: () => api.totals(span![0], span![1]), enabled: !!span });
  const recent = useQuery({ queryKey: ["activities", "recent"], queryFn: () => api.activities(0, 10) });
  const [info, setInfo] = useState<string | null>(null);
  const t = totals.data;
  const over = t?.potential_overcount;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1>Overview</h1>
        <label className="small">Range{" "}
          <select value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}>
            {RANGES.map((r) => <option key={r} value={r}>last {r} weeks</option>)}
          </select></label>
      </div>
      {t && t.state === "unconfirmed_duplicates_included" && over && (
        <div className="notice" role="status" data-testid="overcount">
          <span>{over.unconfirmed_group_count + over.pending_recording_count} possible duplicate {over.unconfirmed_group_count + over.pending_recording_count === 1 ? "ride is" : "rides are"} unconfirmed.
            Totals may be overcounted by up to {duration(over.duration_s)} and {number("kJ", over.work_kj)}.</span>
          <Link to="/library/duplicates">Review duplicates</Link>
        </div>
      )}
      {t && (
        <div className="cards" style={{ marginBottom: 8 }}>
          <div className="card"><div className="label"><span>Duration</span><InfoButton label="Duration" onClick={() => setInfo("M001")} /></div>
            <div className="value" data-testid="total-duration">{duration(t.duration_s) || "0:00"}</div>
            <div className="meta"><ClassLabel value="DERIVED" /> · {t.ride_count} rides</div></div>
          <div className="card"><div className="label"><span>Work</span><InfoButton label="Work" onClick={() => setInfo("M003")} /></div>
            <div className="value" data-testid="total-work">{t.work_state === "lower_bound" ? "at least " : ""}{number("kJ", t.work_kj)}</div>
            <div className="meta"><ClassLabel value="DERIVED" />{(t.rides_by_work_state.no_power ?? 0) > 0 && <> · {t.rides_by_work_state.no_power} rides without power</>}</div></div>
        </div>
      )}
      <div className="grid2">
        <section><h2>Weekly duration (timer)</h2>{weekly.data && <WeekBars weeks={weekly.data} kind="duration" />}</section>
        <section><h2>Weekly work</h2>{weekly.data && <WeekBars weeks={weekly.data} kind="work" />}</section>
      </div>
      <h2>Highest observed power <InfoButton label="Highest observed power" onClick={() => setInfo("M004")} /></h2>
      {t && (
        <div className="cards">
          {Object.entries(t.best_mmp_w).map(([T, b]) => (
            <div className="card" key={T} data-testid={`best-${T}`}>
              <div className="label"><span>{windowLabel(Number(T))}</span></div>
              {b ? <><div className="value">{number("W", b.value)}</div>
                <div className="meta"><ClassLabel value="DERIVED" /> · <Link to={`/rides/${b.ride_id}`}>ride</Link></div></>
                : <><div className="value unavailable">Not available</div><div className="meta">no unbroken stretch of power this long</div></>}
            </div>))}
        </div>
      )}
      <h2>Recent activities</h2>
      {recent.data && (recent.data.items.length ? <ActivityTable rows={recent.data.items} /> : <p className="muted">No activities yet. <Link to="/library">Import files</Link>.</p>)}
      {info && <InfoDrawer metricId={info} onClose={() => setInfo(null)} />}
    </>
  );
}
