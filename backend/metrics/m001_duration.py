"""M001 timer duration, elapsed duration and sample coverage (spec 7, D3)."""
from __future__ import annotations

from ..canonical.timeline import Timeline
from .result import NOT_APPLICABLE, VALID, MetricResult

METRIC_ID, VERSION = "M001", "1.0"


def compute(tl: Timeline) -> MetricResult:
    if tl.t_end is None:
        return MetricResult(METRIC_ID, VERSION, "DERIVED", "s", None, NOT_APPLICABLE,
                            details={"flags": sorted(tl.flags)})
    observed_s = sum(iv.duration_s for iv in tl.intervals if not iv.is_gap)
    return MetricResult(
        METRIC_ID, VERSION, "DERIVED", "s", tl.timer_s, VALID,
        parameters={"gap_tolerance_factor": 1.5},
        details={
            "timer_s": tl.timer_s,
            "elapsed_s": tl.t_end - tl.t_start,
            "observed_s": observed_s,
            "timer_source": tl.timer_source,
            "device_timer_s": tl.device_timer_s,   # OBSERVED, reported separately
            "flags": sorted(tl.flags),
        },
    )
