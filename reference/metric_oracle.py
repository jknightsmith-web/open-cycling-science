"""Independent arithmetic reference for synthetic acceptance checks.

This is not a full application, parser or physiological validation.
All times are SI seconds, half-open intervals [start, end).

Design choice: Power is assumed constant within each recorded interval; this
should be recorded as an assumption for actual device telemetry.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class Interval:
    start_s: float
    end_s: float
    power_w: Optional[float]
    timer_running: bool = True


def _check(intervals: Sequence[Interval]):
    for i, record in enumerate(intervals):
        if record.end_s <= record.start_s:
            raise ValueError('Each interval must have positive duration')
        if record.power_w is not None and record.power_w < 0:
            raise ValueError('Negative mechanical power is unsupported in this reference')
        if i and intervals[i-1].end_s > record.start_s:
            raise ValueError('Overlapping intervals are not allowed')


def aggregate(intervals: Sequence[Interval], min_coverage: float = 0.95) -> dict:
    """Compute observed mean power and mechanical work under a coverage policy.

    Mean power is withheld below min_coverage; work is reported with a
    lower_bound state instead (decision D1).

    Timer-stopped intervals are ineligible. Gaps and missing watts do not count
    as observed power. Explicit 0 W readings are valid observations.
    """
    _check(intervals)
    if not 0 <= min_coverage <= 1:
        raise ValueError('min_coverage must lie between 0 and 1')
    eligible = sum(r.end_s-r.start_s for r in intervals if r.timer_running)
    observed = sum(r.end_s-r.start_s for r in intervals
                   if r.timer_running and r.power_w is not None)
    energy_j = sum((r.end_s-r.start_s)*r.power_w for r in intervals
                   if r.timer_running and r.power_w is not None)
    coverage = observed / eligible if eligible else 0.0
    is_valid = eligible > 0 and observed > 0 and coverage >= min_coverage
    # Decision D1 (spec v1.0): recorded work is reported at any coverage above
    # zero. Power is non negative, so it is a lower bound below min_coverage.
    has_work = eligible > 0 and observed > 0
    return {'eligible_s': eligible, 'observed_s': observed, 'coverage': coverage,
            'mean_power_w': energy_j/observed if is_valid else None,
            'mechanical_work_kj': energy_j/1000 if has_work else None,
            'work_state': (None if not has_work
                           else 'valid' if coverage >= min_coverage
                           else 'lower_bound')}


def mmp(intervals: Sequence[Interval], window_s: float) -> Optional[float]:
    """Max rolling mean of complete, uninterrupted observed power windows.

    Step-function samples; candidate extrema occur at sample boundaries or
    boundaries minus the window duration. Invalid gaps/pause windows ignored.
    """
    _check(intervals)
    if window_s <= 0:
        raise ValueError('window_s must be positive')
    valid = [r for r in intervals if r.timer_running and r.power_w is not None]
    if not valid:
        return None
    boundaries = {point for r in valid for point in (r.start_s, r.end_s)}
    candidates = boundaries | {x-window_s for x in boundaries}
    highest = None
    for a in sorted(candidates):
        b = a+window_s
        cursor = a
        energy_j = 0.0
        for r in valid:
            if r.end_s <= cursor:
                continue
            if r.start_s > cursor + 1e-9:
                break
            right = min(r.end_s, b)
            if right > cursor:
                energy_j += (right-cursor)*r.power_w
                cursor = right
            if cursor >= b - 1e-9:
                break
        if cursor >= b - 1e-9:
            value = energy_j/window_s
            highest = value if highest is None else max(highest, value)
    return highest


def cp_two_parameter_fit(efforts: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Mathematical fit of P=CP+Wprime/t for synthetic examples ONLY.

    No protocol validation or uncertainty quantification. NOT suitable for
    treating historical training peaks as exhaustive physiological tests.
    """
    if len(efforts) < 3 or len({t for t,p in efforts}) < 3:
        raise ValueError('Need at least three distinct durations')
    if any(t <= 0 or p <= 0 for t,p in efforts):
        raise ValueError('Durations and powers must be positive')
    xs = [1/t for t,p in efforts]
    ys = [p for t,p in efforts]
    mx = sum(xs)/len(xs)
    my = sum(ys)/len(ys)
    denom = sum((x-mx)**2 for x in xs)
    if not denom:
        raise ValueError('Singular fit')
    wp_j = sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denom
    cp_w = my-wp_j*mx
    if cp_w <= 0 or wp_j <= 0:
        raise ValueError('Physically invalid fitted parameters')
    return cp_w, wp_j
