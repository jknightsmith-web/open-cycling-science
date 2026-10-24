import { useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Deletion } from "../api/client";
import { CHANNEL_NAMES } from "../format/format";

/** What a deletion will do, in words, from the server's dry run (spec 8.4). */
function Consequences({ d }: { d: Deletion }) {
  return (
    <ul className="small">
      <li>The original file{d.original_filename ? ` ${d.original_filename}` : ""}, and every sample, timer event and metric result made from it.</li>
      {d.groups.map((g) => g.effect === "dissolved"
        ? <li key={g.group_id}>Duplicate group {g.group_id} ({g.status}) is left with one recording, so it dissolves: that recording counts as its own ride again{g.status === "confirmed" ? ", and the confirmed ride and its history go" : ""}.</li>
        : <li key={g.group_id}>It leaves duplicate group {g.group_id} ({g.status}).
          {g.fields_unselected.length > 0 && <> In the confirmed ride, {g.fields_unselected.map((f) => CHANNEL_NAMES[f] ?? f).join(", ")} will have no source and the ride is flagged for you to choose again{g.fields_unselected.includes("timer") ? "; until then it is not counted in totals" : ""}.</>}
          {" "}No other recording changes.</li>)}
      {d.exports_removed.length > 0 && <li>Exports in the data folder that contain it: {d.exports_removed.join(", ")}.</li>}
      <li>Totals are recalculated without it. Nothing keeps its name, hash or times.</li>
    </ul>
  );
}

/**
 * Delete one recording after a confirmation listing exactly what goes. `activityId` for an
 * imported activity, `sourceFileId` for a file that failed to import.
 */
export function DeleteRecording({ activityId, sourceFileId, compact }: { activityId?: number; sourceFileId?: number; compact?: boolean }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [plan, setPlan] = useState<Deletion | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const run = async (fn: () => Promise<Deletion>, after?: (d: Deletion) => void) => {
    setBusy(true);
    setProblem(null);
    try { const d = await fn(); after?.(d); } catch (e) { setProblem(e instanceof ApiError ? e.message : String(e)); }
    setBusy(false);
  };
  const preview = () => run(() => (activityId !== undefined ? api.previewDeleteActivity(activityId) : api.previewDeleteFile(sourceFileId!)), setPlan);
  // The navigation state carries no filename: browser history must not keep one (spec 8.4, no tombstone).
  const confirm = () => run(() => (activityId !== undefined ? api.deleteActivity(activityId) : api.deleteFile(sourceFileId!)), () => {
    setPlan(null);
    if (activityId === undefined) { qc.invalidateQueries(); return; }
    // Nothing may ask for the deleted activity again: drop it from cached lists, then drop its own queries.
    const ours = (q: { queryKey: readonly unknown[] }) => ["activity", "samples", "series"].includes(q.queryKey[0] as string) && q.queryKey[1] === activityId;
    qc.setQueriesData<{ items: { activity_id?: number; id?: number }[]; total: number }>({ queryKey: ["activities"] }, (old) =>
      old && { ...old, items: old.items.filter((m) => (m.activity_id ?? m.id) !== activityId), total: old.total - 1 });
    qc.removeQueries({ predicate: ours });
    nav("/library", { replace: true, state: { deleted: true } });
    qc.invalidateQueries({ predicate: (q) => !ours(q) });
  });
  if (!plan) {
    return <>
      <button className={compact ? "small" : "danger"} onClick={preview} disabled={busy}>{compact ? "Delete" : "Delete this recording"}</button>
      {problem && <span className="error small" role="alert"> {problem}</span>}
    </>;
  }
  return (
    <div className="card confirm" role="alertdialog" aria-label="Confirm deletion">
      <b>Delete permanently? This removes:</b>
      <Consequences d={plan} />
      <p className="small muted">Copies outside the data folder, Time Machine backups and vendor accounts are not affected (Settings, Data).</p>
      <div className="row">
        <button className="danger" onClick={confirm} disabled={busy}>Delete permanently</button>
        <button onClick={() => setPlan(null)} disabled={busy}>Cancel</button>
      </div>
      {problem && <p className="error" role="alert">{problem}</p>}
    </div>
  );
}
