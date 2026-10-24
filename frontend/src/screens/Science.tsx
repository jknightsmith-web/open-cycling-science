import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useEntry, useStates } from "../api/hooks";

function Glossary() {
  const { data } = useStates();
  if (!data) return null;
  const block = (title: string, d: Record<string, string>) => (
    <>
      <h2>{title}</h2>
      <table><tbody>{Object.entries(d).map(([k, v]) => <tr key={k}><th style={{ width: 220 }}>{k.replace(/_/g, " ")}</th><td>{v}</td></tr>)}</tbody></table>
    </>
  );
  return <>{block("Classes", data.classes)}{block("Data validity", data.validity)}{block("Value states", data.value_states)}</>;
}

function Entry({ id }: { id: string }) {
  const { data: e, error } = useEntry(id);
  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!e) return <p className="muted">Loading…</p>;
  const rows: [string, React.ReactNode][] = [
    ["Class", e.classification], ["Evidence label", e.evidence_label], ["Version", e.version], ["Units", e.units],
    ["Equation", <pre className="eq">{e.equation}</pre>],
    ["Variables", Object.entries(e.variable_definitions).map(([k, v]) => <div key={k}><b>{k}</b>: {v}</div>)],
    ["Outputs", Object.entries(e.outputs ?? {}).map(([k, v]) => <div key={k}><b>{k}</b>: {v}</div>)],
    ["Population", e.population_scope], ["Input requirements", e.input_requirements], ["Data quality rules", e.data_quality_rules],
    ["Algorithm", e.algorithm], ["Parameters", Object.entries(e.parameter_set).map(([k, v]) => <div key={k}>{k} = {JSON.stringify(v)}</div>)],
    ["Assumptions", <ul>{e.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>],
    ["Known limitations", <ul>{e.known_limitations.map((a) => <li key={a}>{a}</li>)}</ul>],
    ["Validation protocol", e.validation_protocol], ["Software test status", e.software_test_status],
    ["Scientific validation status", e.scientific_validation_status], ["Uncertainty", e.uncertainty_statement],
    ["Sources", <ul>{e.source_refs.map((r) => <li key={r.id + r.role}>{r.role}{r.citation ? `: ${r.citation}` : ""}
      {r.doi && <> DOI <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer">{r.doi}</a></>} <span className="flag">{r.status}</span></li>)}</ul>],
    ["Last reviewed", e.last_reviewed], ["Register file", <code>{e.documentation_path}</code>],
  ];
  return (
    <article data-testid={`entry-${id}`}>
      <p><Link to="/science">Science</Link></p>
      <h1>{e.metric_id} {e.display_name}</h1>
      {e.problems.length > 0 && <p className="error">Entry incomplete, so this metric is not displayed: {e.problems.join("; ")}</p>}
      <table><tbody>{rows.map(([k, v]) => <tr key={k}><th style={{ width: 220 }}>{k}</th><td>{v}</td></tr>)}</tbody></table>
      <p className="small muted">Source status: V confirmed, P from the starter pack and not rechecked, M DOI not confirmed.</p>
    </article>
  );
}

export function Science() {
  const { metricId } = useParams();
  const { data } = useQuery({ queryKey: ["science"], queryFn: api.science, staleTime: Infinity });
  if (metricId) return <Entry id={metricId} />;
  return (
    <>
      <h1>Science</h1>
      <p className="muted">Every metric the application can show, with its full register entry. Phase One approves M001 to M004 only.</p>
      <table aria-label="Register">
        <thead><tr><th>ID</th><th>Metric</th><th>Class</th><th>Units</th><th>Version</th><th>Entry</th></tr></thead>
        <tbody>{(data ?? []).map((r) => (
          <tr key={r.metric_id}><td><Link to={`/science/${r.metric_id}`}>{r.metric_id}</Link></td><td>{r.display_name}</td>
            <td>{r.classification}</td><td>{r.units}</td><td>{r.version}</td><td>{r.complete ? "complete" : "incomplete"}</td></tr>))}</tbody>
      </table>
      <Glossary />
    </>
  );
}
