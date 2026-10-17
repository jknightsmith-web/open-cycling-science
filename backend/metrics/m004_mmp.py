"""M004 maximal mean power over duration T (spec 7).

Windows lie entirely inside one contiguous run of observed power within one
timer running segment. Within a run, power is a step function, so cumulative
energy E(x) is piecewise linear and the maximum of E(a+T) - E(a) occurs where
a or a+T is a breakpoint. Both candidate sets are sorted, so two monotone
pointers evaluate every candidate in O(n) per run.
"""
from __future__ import annotations

from ..canonical.model import State
from ..canonical.timeline import EPS, Timeline
from .result import INSUFFICIENT_COVERAGE, NO_POWER, NOT_APPLICABLE, VALID, MetricResult

DEFAULT_DURATIONS_S = (5, 60, 300, 1200, 3600)


def contiguous_runs(tl: Timeline) -> list[list[tuple[float, float, float]]]:
    runs: list[list[tuple[float, float, float]]] = []
    current: list[tuple[float, float, float]] = []
    for iv in tl.intervals:
        r = iv.reading("power")
        if iv.is_gap or r.state is not State.OBSERVED:
            if current:
                runs.append(current)
            current = []
            continue
        if current and abs(iv.start_s - current[-1][1]) > EPS:
            runs.append(current)
            current = []
        current.append((iv.start_s, iv.end_s, r.value))
    if current:
        runs.append(current)
    return runs


class _Energy:
    """Cumulative energy over one run, evaluated at non decreasing x."""

    def __init__(self, run):
        self.run = run
        self.cum = [0.0]
        for a, b, p in run:
            self.cum.append(self.cum[-1] + (b - a) * p)
        self.i = 0

    def at(self, x: float) -> float:
        run = self.run
        while self.i < len(run) - 1 and x >= run[self.i][1] - EPS:
            self.i += 1
        a, b, p = run[self.i]
        x = min(max(x, a), b)
        return self.cum[self.i] + (x - a) * p


def _best_in_run(run, T: float):
    lo, hi = run[0][0], run[-1][1]
    if hi - lo < T - EPS:
        return None
    bps = [run[0][0]] + [b for _, b, _ in run]
    last_start = hi - T
    starts_a = [x for x in bps if x <= last_start + EPS]
    starts_b = [x - T for x in bps if x - T >= lo - EPS]
    cands, i, j = [], 0, 0
    while i < len(starts_a) or j < len(starts_b):
        if j >= len(starts_b) or (i < len(starts_a) and starts_a[i] <= starts_b[j]):
            cands.append(starts_a[i]); i += 1
        else:
            cands.append(starts_b[j]); j += 1
    left, right = _Energy(run), _Energy(run)
    best = None
    for a in cands:
        a = min(max(a, lo), last_start)
        value = (right.at(a + T) - left.at(a)) / T
        if best is None or value > best[0] + 1e-12:
            best = (value, a)
    return best


def compute(tl: Timeline, duration_s: float) -> MetricResult:
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    params = {"duration_s": duration_s}
    runs = contiguous_runs(tl)
    if not tl.intervals:
        return MetricResult("M004", "1.0", "DERIVED", "W", None, NOT_APPLICABLE, params)
    if not runs:
        return MetricResult("M004", "1.0", "DERIVED", "W", None, NO_POWER, params)
    best = None
    for run in runs:
        found = _best_in_run(run, duration_s)
        if found and (best is None or found[0] > best[0] + 1e-12):
            best = found
    details = {"longest_run_s": max(r[-1][1] - r[0][0] for r in runs),
               "recording_interval_s": tl.nominal_interval_s}
    if best is None:
        return MetricResult("M004", "1.0", "DERIVED", "W", None, INSUFFICIENT_COVERAGE,
                            params, details)
    details["window_start_s"] = best[1]
    return MetricResult("M004", "1.0", "DERIVED", "W", best[0], VALID, params, details)
