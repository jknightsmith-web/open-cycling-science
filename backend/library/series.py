"""Canonical timeline from the database, and the chart display envelope (WP8, design 06 B3).

`load_timeline` rebuilds an activity's RawActivity from its stored samples
and timer events and runs the same timeline builder as import, so the result
is the canonical timeline itself; a test asserts its digest equals the stored
input revision.

`envelope` is a display reduction, not a metric. A channel is split into runs
of contiguous observed intervals. Each run is reduced on its own, and no
bucket spans the end of a run. Every non observed stretch between runs is
returned as a break with its reason, so a chart can never draw a line across
missing, invalid, gap or paused time.
"""
from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import Connection, select

from ..canonical.model import RawActivity, RawRecord, State, TimerEvent
from ..canonical.timeline import EPS, Timeline, build_timeline
from ..storage.schema import CHANNEL_COLUMNS, activities, activity_channels, samples, timer_events

MAX_POINTS = 20_000


def load_timeline(c: Connection, aid: int) -> Optional[Timeline]:
    act = c.execute(select(activities.c.device_timer_s, activities.c.utc_offset_s)
                    .where(activities.c.id == aid)).first()
    if act is None:
        return None
    cols = [samples.c.timestamp_utc] + [samples.c[n] for pair in CHANNEL_COLUMNS.values() for n in pair]
    records = []
    for row in c.execute(select(*cols).where(samples.c.activity_id == aid).order_by(samples.c.sample_index)):
        fields: dict[str, Optional[float]] = {}
        for i, ch in enumerate(CHANNEL_COLUMNS):
            value, validity = row[1 + 2 * i], row[2 + 2 * i]
            if validity == "observed":
                fields[ch] = value
            elif validity == "invalid":
                fields[ch] = None        # present but unusable; the builder classifies it invalid again
        records.append(RawRecord(row[0], fields))
    events = [TimerEvent(t, k) for t, k in c.execute(
        select(timer_events.c.timestamp_utc, timer_events.c.event_type)
        .where(timer_events.c.activity_id == aid).order_by(timer_events.c.id))]
    simulated = frozenset(r[0] for r in c.execute(
        select(activity_channels.c.channel).where(activity_channels.c.activity_id == aid,
                                                  activity_channels.c.origin == "simulated")))
    raw = RawActivity("db", records, events, device_timer_s=act.device_timer_s, utc_offset_s=act.utc_offset_s,
                      simulated_channels=simulated)
    return build_timeline(raw)


def _break_reason(iv, channel: str) -> str:
    if iv.is_gap:
        return "gap"
    return "invalid" if iv.reading(channel).state is State.INVALID else "missing"


def runs_and_breaks(tl: Timeline, channel: str):
    """Maximal runs of contiguous observed intervals, and the stretches between them."""
    runs: list[list[tuple[float, float, float]]] = []
    breaks: list[dict] = []
    current: list[tuple[float, float, float]] = []

    def add_break(start: float, end: float, reason: str) -> None:
        if end - start <= EPS:
            return
        if breaks and breaks[-1]["reason"] == reason and abs(breaks[-1]["end"] - start) < EPS:
            breaks[-1]["end"] = end
        else:
            breaks.append({"start": start, "end": end, "reason": reason})

    prev_end = None
    for iv in tl.intervals:
        r = iv.reading(channel)
        if prev_end is not None and iv.start_s - prev_end > EPS:
            if current:
                runs.append(current)
                current = []
            add_break(prev_end, iv.start_s, "paused")      # between timer running segments
        if not iv.is_gap and r.state is State.OBSERVED:
            current.append((iv.start_s, iv.end_s, r.value))
        else:
            if current:
                runs.append(current)
                current = []
            add_break(iv.start_s, iv.end_s, _break_reason(iv, channel))
        prev_end = iv.end_s
    if current:
        runs.append(current)
    return runs, breaks


def _reduce(run: list[tuple[float, float, float]], width: float) -> tuple[list[float], list[float]]:
    """First, min, max and last of each bucket inside one run, in time order, plus the run's end."""
    if width <= 0 or len(run) <= 4:
        ts = [a for a, _, _ in run] + [run[-1][1]]
        vs = [v for _, _, v in run] + [run[-1][2]]
        return ts, vs
    origin = run[0][0]
    ts: list[float] = []
    vs: list[float] = []
    bucket: list[tuple[float, float]] = []
    key = None
    def flush():
        if not bucket:
            return
        picks = {0, len(bucket) - 1,
                 min(range(len(bucket)), key=lambda i: bucket[i][1]),
                 max(range(len(bucket)), key=lambda i: bucket[i][1])}
        for i in sorted(picks):
            ts.append(bucket[i][0]); vs.append(bucket[i][1])
    for a, _, v in run:
        k = math.floor((a - origin) / width)
        if k != key:
            flush()
            bucket, key = [], k
        bucket.append((a, v))
    flush()
    ts.append(run[-1][1]); vs.append(run[-1][2])     # the step function holds to the end of the run
    return ts, vs


def envelope(tl: Timeline, channel: str, points: int = 2000) -> dict:
    points = max(16, min(points, MAX_POINTS))
    runs, breaks = runs_and_breaks(tl, channel)
    span = (tl.t_end - tl.t_start) if tl.t_end is not None and tl.t_start is not None else 0.0
    n_intervals = sum(len(r) for r in runs)
    width = 0.0 if n_intervals + len(runs) <= points else span / (points / 4)
    out_runs = []
    for run in runs:
        ts, vs = _reduce(run, width)
        out_runs.append({"t": ts, "v": vs})
    return {"kind": "display_envelope", "channel": channel, "t_start": tl.t_start, "t_end": tl.t_end,
            "simulated": channel in tl.simulated_channels, "points_requested": points,
            "points_returned": sum(len(r["t"]) for r in out_runs), "bucket_width_s": width or None,
            "runs": out_runs, "breaks": breaks}
