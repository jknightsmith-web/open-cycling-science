import { channelText } from "../format/format";

const REASONS: Record<string, string> = {
  invalid: "Present in the file but unusable: an invalid sentinel, a value outside the physical range, or a repeated timestamp",
  missing: "Not in the record, or no record covers this time",
};

/** A channel value in a table: the value, or its validity word. Never 0 for an absent value (P6). */
export function ValidityCell({ channel, value, validity, suspect }: {
  channel: string; value: number | null | undefined; validity: string; suspect?: boolean;
}) {
  if (validity === "observed" && value !== null && value !== undefined) {
    return <td className="num" data-validity="observed">{channelText(channel, value)}
      {suspect && <span className="flag suspect" title="0 W for at least 3 s while cadence is above 0. Value kept">suspect zero</span>}</td>;
  }
  return <td data-validity={validity}><span className={`state-word ${validity}`} title={REASONS[validity]}>{validity}</span></td>;
}
