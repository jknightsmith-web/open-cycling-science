import { useState } from "react";
import type { MetricValue } from "../api/client";
import { metricLabel, metricText } from "../format/format";
import { InfoDrawer } from "./InfoDrawer";

export function ClassLabel({ value }: { value?: string | null }) {
  return <span className="class-label" title="Metric class (spec 6.1)">{(value ?? "unclassified").toLowerCase()}</span>;
}

export function InfoButton({ label, onClick }: { label: string; onClick: () => void }) {
  return <button className="info" aria-label={`About ${label}`} title="Definition, assumptions, limitations and provenance" onClick={onClick}>i</button>;
}

/** Primary layer: plain name, large value, class label, and any state that changes the meaning (design 06, 4.1). */
export function MetricCard({ metric, source, title }: { metric: MetricValue; source?: string; title?: string }) {
  const [open, setOpen] = useState(false);
  const label = metricLabel(metric);
  const t = metricText(metric);
  return (
    <div className="card" data-testid={`metric-${metric.metric_id}${metric.parameters.duration_s ? `-${metric.parameters.duration_s}` : ""}`}
         data-state={metric.state}>
      <div className="label"><span>{title ?? label}</span><InfoButton label={label} onClick={() => setOpen(true)} /></div>
      <div className={`value${t.available ? "" : " unavailable"}`}>{t.main}</div>
      <div className="meta"><ClassLabel value={metric.classification} />{t.note && <> · {t.note}</>}{source && <> · {source}</>}</div>
      {open && <InfoDrawer metric={metric} metricId={metric.metric_id} onClose={() => setOpen(false)} />}
    </div>
  );
}
