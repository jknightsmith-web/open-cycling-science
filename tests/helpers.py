"""Synthetic activity builders for tests. No rider data."""
from __future__ import annotations

from backend.canonical.model import RawActivity, RawRecord, TimerEvent

T0 = 1_760_000_000.0  # arbitrary UTC epoch seconds


def ride(powers, start=T0, dt=1.0, fields=None, events=None, fmt="fit", **kw):
    """One record per value; None means the power field is absent (missing)."""
    records = []
    for i, p in enumerate(powers):
        f = dict(fields[i]) if fields else {}
        if p is not None:
            f["power"] = p
        records.append(RawRecord(start + i * dt, f))
    ev = [TimerEvent(start + t, k) for t, k in (events or [])]
    return RawActivity(fmt, records, ev, **kw)
