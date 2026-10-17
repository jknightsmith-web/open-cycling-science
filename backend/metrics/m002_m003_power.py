"""M002 recorded mean power and M003 recorded mechanical work (spec 7, D1).

Only observed power inside timer running segments enters the sums. Measured
zero is included; missing and invalid are excluded and never counted as 0 W.
"""
from __future__ import annotations

from ..canonical.model import State
from ..canonical.timeline import Timeline
from .result import (INSUFFICIENT_COVERAGE, LOWER_BOUND, NO_POWER, NOT_APPLICABLE, VALID,
                     MetricResult)

MIN_COVERAGE = 0.95


def _sums(tl: Timeline) -> tuple[float, float, float]:
    eligible = tl.timer_s
    observed = energy = 0.0
    for iv in tl.intervals:
        r = iv.reading("power")
        if r.state is State.OBSERVED:
            observed += iv.duration_s
            energy += iv.duration_s * r.value
    return eligible, observed, energy


def mean_power(tl: Timeline, min_coverage: float = MIN_COVERAGE) -> MetricResult:
    eligible, observed, energy = _sums(tl)
    coverage = observed / eligible if eligible > 0 else 0.0
    details = {"coverage": coverage, "observed_power_s": observed, "eligible_s": eligible}
    params = {"min_coverage": min_coverage}
    if eligible <= 0:
        state, value = NOT_APPLICABLE, None
    elif observed <= 0:
        state, value = NO_POWER, None
    elif coverage < min_coverage:
        state, value = INSUFFICIENT_COVERAGE, None
    else:
        state, value = VALID, energy / observed
    return MetricResult("M002", "1.0", "DERIVED", "W", value, state, params, details)


def mechanical_work(tl: Timeline, lower_bound_below: float = MIN_COVERAGE) -> MetricResult:
    eligible, observed, energy = _sums(tl)
    coverage = observed / eligible if eligible > 0 else 0.0
    details = {"coverage": coverage, "observed_power_s": observed, "eligible_s": eligible}
    params = {"lower_bound_label_below": lower_bound_below}
    if eligible <= 0:
        state, value = NOT_APPLICABLE, None
    elif observed <= 0:
        state, value = NO_POWER, None
    else:
        state = VALID if coverage >= lower_bound_below else LOWER_BOUND
        value = energy / 1000.0
    return MetricResult("M003", "1.0", "DERIVED", "kJ", value, state, params, details)
