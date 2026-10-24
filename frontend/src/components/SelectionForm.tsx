import { useState } from "react";
import type { ActivityDetail, Field, S } from "../api/client";
import { FIELDS } from "../api/client";
import { CHANNEL_NAMES } from "../format/format";

export const memberName = (a: Pick<ActivityDetail, "id" | "source_platform" | "media_format">) =>
  `${a.source_platform || "unknown source"} (${a.media_format.toUpperCase()}, #${a.id})`;

export function recorded(a: ActivityDetail, f: Field): boolean {
  return f === "timer" || !!a.channels[f]?.present;
}

type Choice = number | "none" | undefined;

/**
 * One explicit source per field (spec 5.8). Prefilled suggestions show their
 * reason; nothing is applied until the rider submits. A field no member
 * recorded is missing for the ride.
 */
export function SelectionForm({ members, prefill, initial, submitLabel, onSubmit, busy }: {
  members: ActivityDetail[];
  prefill?: Record<string, S["Prefill"]>;
  initial?: Record<string, number | null>;
  submitLabel: string;
  busy?: boolean;
  onSubmit: (selection: Record<Field, number | null>) => void;
}) {
  const start: Record<string, Choice> = {};
  for (const f of FIELDS) {
    const v = initial ? initial[f] : prefill?.[f]?.activity_id;
    const able = members.filter((m) => recorded(m, f));
    start[f] = v !== null && v !== undefined && able.some((m) => m.id === v) ? v : able.length === 0 || (initial && v === null) ? "none" : undefined;
  }
  const [choice, setChoice] = useState(start);
  const complete = FIELDS.every((f) => choice[f] !== undefined && !(f === "timer" && choice[f] === "none"));
  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      if (!complete) return;
      onSubmit(Object.fromEntries(FIELDS.map((f) => [f, choice[f] === "none" ? null : (choice[f] as number)])) as Record<Field, number | null>);
    }}>
      <table>
        <thead><tr><th>Field</th><th>Source</th><th>Suggested because</th></tr></thead>
        <tbody>
          {FIELDS.map((f) => {
            const able = members.filter((m) => recorded(m, f));
            return (
              <tr key={f} data-field={f}>
                <td>{CHANNEL_NAMES[f]}</td>
                <td>
                  {able.length === 0 ? <span className="state-word">no member recorded it: missing</span> : (
                    <div className="row" role="radiogroup" aria-label={CHANNEL_NAMES[f]}>
                      {able.map((m) => (
                        <label key={m.id}><input type="radio" name={f} checked={choice[f] === m.id}
                          onChange={() => setChoice({ ...choice, [f]: m.id })} /> {memberName(m)}
                          {m.channels[f]?.origin === "simulated" && <span className="flag">simulated</span>}</label>
                      ))}
                      {f !== "timer" && <label><input type="radio" name={f} checked={choice[f] === "none"}
                        onChange={() => setChoice({ ...choice, [f]: "none" })} /> none</label>}
                    </div>)}
                </td>
                <td className="small muted">{prefill?.[f]?.basis ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="small muted">Ride duration comes from the timer source. Power values come from the power source file with its own timer and coverage.
        Values are never combined across files.</p>
      <button className="primary" type="submit" disabled={!complete || busy}>{submitLabel}</button>
      {!complete && <span className="small muted" style={{ marginLeft: 10 }}>Choose a source for every field.</span>}
    </form>
  );
}
