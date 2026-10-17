"""Canonical timeline builder: spec v1.0 sections 5.2 to 5.5.

Turns a RawActivity into half open intervals inside timer running segments.
Every second of timer time is covered either by a sample interval or by a gap
interval in which every channel is missing. No value is held across a gap
longer than the gap tolerance (decision D2) and nothing is interpolated.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from .model import CHANNELS, MISSING, Interval, RawActivity, RawRecord, Reading, State
from .validity import classify

EPS = 1e-6  # 1 microsecond: far below any recording resolution, above float64 error at epoch magnitude
GAP_TOLERANCE_FACTOR = 1.5          # D2
IRREGULAR_DEVIATION_S = 0.1         # spec 5.3 item 7
IRREGULAR_FRACTION = 0.10           # spec 5.3 item 7
SUSPECT_ZERO_MIN_S = 3.0            # spec 5.2
INTERVAL_BINS_S = (1.0, 2.0, 5.0, 10.0, 30.0)

TIMER_DEVICE_EVENTS = "device_events"
TIMER_ASSUMED_CONTINUOUS = "assumed_continuous"   # D3


@dataclass(frozen=True)
class RecordingStats:
    """Evidence about how a file was recorded (spec 5.3 item 7).

    `irregular_recording` is descriptive. Adequacy for a metric is decided
    only by that metric's own data quality rules.
    """
    record_count: int
    nominal_interval_s: Optional[float]
    interval_histogram: dict[str, int]
    max_interval_s: Optional[float]
    gap_count: int
    gap_s: float
    covered_s: float
    channel_observed_s: dict[str, float]
    irregular_recording: bool


@dataclass
class Timeline:
    intervals: list[Interval]
    segments: list[tuple[float, float]]
    timer_source: str
    nominal_interval_s: Optional[float]
    t_start: Optional[float]
    t_end: Optional[float]
    stats: RecordingStats
    duplicate_timestamp_count: int = 0
    suspect_zero_runs: list[tuple[float, float]] = field(default_factory=list)
    device_timer_s: Optional[float] = None
    simulated_channels: frozenset[str] = frozenset()
    flags: set[str] = field(default_factory=set)

    @property
    def timer_s(self) -> float:
        return sum(b - a for a, b in self.segments)


def _dedupe(records: list[RawRecord]) -> tuple[list[RawRecord], int]:
    ordered = sorted(records, key=lambda r: r.timestamp_s)
    kept: list[RawRecord] = []
    dropped = 0
    for r in ordered:
        if kept and abs(r.timestamp_s - kept[-1].timestamp_s) < EPS:
            dropped += 1  # spec 5.3 item 1: keep the first, the rest are invalid
            continue
        kept.append(r)
    return kept, dropped


def _nominal_interval(records: list[RawRecord]) -> Optional[float]:
    diffs = [b.timestamp_s - a.timestamp_s for a, b in zip(records, records[1:])]
    diffs = [d for d in diffs if d > EPS]
    return statistics.median(diffs) if diffs else None


def _segments(raw: RawActivity, records: list[RawRecord], dnom: float) -> tuple[list[tuple[float, float]], str]:
    first = records[0].timestamp_s
    last_end = records[-1].timestamp_s + dnom
    if not raw.timer_events:
        return [(first, last_end)], TIMER_ASSUMED_CONTINUOUS
    events = sorted(raw.timer_events, key=lambda e: e.timestamp_s)
    segments: list[tuple[float, float]] = []
    running = events[0].kind == "stop"   # a leading stop implies the timer ran from the first record
    seg_start = first if running else None
    for e in events:
        if e.kind == "start" and not running:
            running, seg_start = True, e.timestamp_s
        elif e.kind == "stop" and running:
            segments.append((seg_start, e.timestamp_s))
            running = False
    if running:
        segments.append((seg_start, max(last_end, seg_start)))
    return [(a, b) for a, b in segments if b - a > EPS], TIMER_DEVICE_EVENTS


def _readings(raw: RawActivity, record: RawRecord) -> dict[str, Reading]:
    return {ch: classify(ch, ch in record.fields, record.fields.get(ch)) for ch in CHANNELS}


def _gap(start: float, end: float) -> Interval:
    return Interval(start, end, {ch: MISSING for ch in CHANNELS}, is_gap=True)


def _segment_intervals(raw: RawActivity, recs: list[RawRecord], seg: tuple[float, float],
                       dnom: float, g: float) -> list[Interval]:
    s0, s1 = seg
    out: list[Interval] = []
    cursor = s0
    for i, r in enumerate(recs):
        t = r.timestamp_s
        if t > cursor + EPS:
            out.append(_gap(cursor, t))
        nxt = recs[i + 1].timestamp_s if i + 1 < len(recs) else None
        if nxt is not None and nxt - t <= g + EPS:
            end = nxt
        else:
            end = min(t + dnom, s1)
        out.append(Interval(t, end, _readings(raw, r)))
        cursor = end
    if cursor < s1 - EPS:
        out.append(_gap(cursor, s1))
    return out


def _histogram(diffs: list[float]) -> dict[str, int]:
    labels = [f"<={b:g}s" for b in INTERVAL_BINS_S] + [f">{INTERVAL_BINS_S[-1]:g}s"]
    counts = dict.fromkeys(labels, 0)
    for d in diffs:
        for b, label in zip(INTERVAL_BINS_S, labels):
            if d <= b + EPS:
                counts[label] += 1
                break
        else:
            counts[labels[-1]] += 1
    return counts


def _suspect_zero_runs(intervals: list[Interval]) -> list[tuple[float, float]]:
    runs: list[tuple[float, float]] = []
    start = end = None
    for iv in intervals:
        p, c = iv.reading("power"), iv.reading("cadence")
        hit = (not iv.is_gap and p.state is State.OBSERVED and p.value == 0
               and c.state is State.OBSERVED and c.value > 0)
        if hit and start is not None and abs(iv.start_s - end) < EPS:
            end = iv.end_s
            continue
        if start is not None and end - start >= SUSPECT_ZERO_MIN_S - EPS:
            runs.append((start, end))
        start, end = (iv.start_s, iv.end_s) if hit else (None, None)
    if start is not None and end - start >= SUSPECT_ZERO_MIN_S - EPS:
        runs.append((start, end))
    return runs


def build_timeline(raw: RawActivity) -> Timeline:
    records, dropped = _dedupe(raw.records)
    dnom = _nominal_interval(records)
    if dnom is None:
        stats = RecordingStats(len(records), None, _histogram([]), None, 0, 0.0, 0.0,
                               dict.fromkeys(CHANNELS, 0.0), False)
        return Timeline([], [], TIMER_ASSUMED_CONTINUOUS, None,
                        records[0].timestamp_s if records else None, None, stats,
                        duplicate_timestamp_count=dropped, device_timer_s=raw.device_timer_s,
                        simulated_channels=raw.simulated_channels,
                        flags={"insufficient_samples"})

    g = GAP_TOLERANCE_FACTOR * dnom
    segments, timer_source = _segments(raw, records, dnom)
    intervals: list[Interval] = []
    for seg in segments:
        in_seg = [r for r in records if seg[0] - EPS <= r.timestamp_s < seg[1] - EPS]
        intervals.extend(_segment_intervals(raw, in_seg, seg, dnom, g))

    last = records[-1].timestamp_s
    last_iv = next((iv for iv in reversed(intervals) if not iv.is_gap and abs(iv.start_s - last) < EPS), None)
    t_end = last_iv.end_s if last_iv else last + dnom

    diffs = [b.timestamp_s - a.timestamp_s for a, b in zip(records, records[1:])]
    gaps = [iv for iv in intervals if iv.is_gap]
    observed = {ch: sum(iv.duration_s for iv in intervals if iv.reading(ch).state is State.OBSERVED)
                for ch in CHANNELS}
    irregular = sum(1 for d in diffs if abs(d - dnom) > IRREGULAR_DEVIATION_S) > IRREGULAR_FRACTION * len(diffs)
    stats = RecordingStats(
        record_count=len(records),
        nominal_interval_s=dnom,
        interval_histogram=_histogram(diffs),
        max_interval_s=max(diffs),
        gap_count=len(gaps),
        gap_s=sum(iv.duration_s for iv in gaps),
        covered_s=sum(iv.duration_s for iv in intervals if not iv.is_gap),
        channel_observed_s=observed,
        irregular_recording=irregular,
    )
    tl = Timeline(intervals, segments, timer_source, dnom, records[0].timestamp_s, t_end, stats,
                  duplicate_timestamp_count=dropped,
                  suspect_zero_runs=_suspect_zero_runs(intervals),
                  device_timer_s=raw.device_timer_s,
                  simulated_channels=raw.simulated_channels)
    if irregular:
        tl.flags.add("irregular_recording")
    if dropped:
        tl.flags.add("duplicate_timestamps")
    if tl.suspect_zero_runs:
        tl.flags.add("suspect_zero")
    if raw.device_timer_s is not None and abs(tl.timer_s - raw.device_timer_s) > max(2.0, 0.01 * tl.timer_s):
        tl.flags.add("device_timer_mismatch")
    return tl
