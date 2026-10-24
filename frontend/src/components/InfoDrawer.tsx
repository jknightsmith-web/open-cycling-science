import { useEffect } from "react";
import { Link } from "react-router";
import type { MetricValue } from "../api/client";
import { useEntry, useStates } from "../api/hooks";
import { pct, shortHash } from "../format/format";

/** The second layer (design 06, 4.1 and 4.4): class, state, provenance and the full register entry. */
export function InfoDrawer({ metric, metricId, onClose }: { metric?: MetricValue; metricId: string; onClose: () => void }) {
  const { data: e, error } = useEntry(metricId);
  const { data: states } = useStates();
  useEffect(() => {
    const k = (ev: KeyboardEvent) => ev.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`About ${metricId}`}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>{metricId} {e?.display_name}</h2>
          <button onClick={onClose} aria-label="Close">Close</button>
        </div>
        {error && <p className="error">Register entry could not be loaded.</p>}
        {metric && (
          <section>
            <h2>This value</h2>
            <dl>
              <dt>Class</dt><dd><b>{metric.classification}</b>{states && metric.classification &&
                <div className="small muted">{states.classes[metric.classification]}</div>}</dd>
              <dt>State</dt><dd>{metric.state.replace(/_/g, " ")}{states?.value_states[metric.state] &&
                <div className="small muted">{states.value_states[metric.state]}</div>}</dd>
              {metric.coverage !== null && metric.coverage !== undefined && <><dt>Power coverage</dt><dd>{pct(metric.coverage)}</dd></>}
              <dt>Parameters</dt><dd>{Object.entries(metric.parameters).map(([k, v]) => `${k} = ${JSON.stringify(v)}`).join(", ") || "none"}</dd>
              <dt>Uncertainty</dt><dd>{String(metric.uncertainty)}</dd>
              <dt>Source file</dt><dd>{metric.source_sha256.length ? metric.source_sha256.map((h, i) => (
                <div key={h}><Link to={`/activities/${metric.source_activity_ids[i]}`} onClick={onClose}>activity {metric.source_activity_ids[i]}</Link>{" "}
                  <code title={h}>SHA256 {shortHash(h)}</code></div>)) : "none"}</dd>
              <dt>Input revision</dt><dd><code title={metric.input_revision}>{shortHash(metric.input_revision)}</code></dd>
              <dt>Computed by</dt><dd>{metric.computation_version}, metric version {metric.version}</dd>
            </dl>
          </section>
        )}
        {e && (
          <section>
            <h2>Definition</h2>
            <dl>
              <dt>Evidence</dt><dd>{e.evidence_label}</dd>
              <dt>Equation</dt><dd><pre className="eq">{e.equation}</pre></dd>
              <dt>Variables</dt><dd>{Object.entries(e.variable_definitions).map(([k, v]) => <div key={k}><b>{k}</b>: {v}</div>)}</dd>
              <dt>Assumptions</dt><dd><ul>{e.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></dd>
              <dt>Limitations</dt><dd><ul>{e.known_limitations.map((a) => <li key={a}>{a}</li>)}</ul></dd>
              <dt>Data quality</dt><dd>{e.data_quality_rules}</dd>
              <dt>Validation</dt><dd>{e.scientific_validation_status}</dd>
              <dt>Uncertainty</dt><dd>{e.uncertainty_statement}</dd>
              <dt>Sources</dt><dd><ul>{e.source_refs.map((r) => (
                <li key={r.id + r.role}>{r.role}{r.citation ? `: ${r.citation}` : ""}{r.doi && <> DOI <a href={`https://doi.org/${r.doi}`} rel="noreferrer" target="_blank">{r.doi}</a></>} <span className="flag">{r.status}</span></li>))}</ul></dd>
            </dl>
            <p><Link to={`/science/${metricId}`} onClick={onClose}>Full register entry</Link></p>
          </section>
        )}
      </aside>
    </>
  );
}
