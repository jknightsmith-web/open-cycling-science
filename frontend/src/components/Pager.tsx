export function Pager({ offset, limit, total, onChange }: { offset: number; limit: number; total: number; onChange: (o: number) => void }) {
  if (total <= limit) return null;
  return (
    <div className="row" style={{ marginTop: 10 }}>
      <button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</button>
      <span className="muted small">{offset + 1} to {Math.min(total, offset + limit)} of {total}</span>
      <button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</button>
    </div>
  );
}
