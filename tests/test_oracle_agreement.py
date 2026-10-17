"""Acceptance 13: production metrics agree with the independent oracle.

Hypothesis generates step series with missing power, gaps longer than the
tolerance, fractional intervals and timer pauses. The timeline is converted
to oracle intervals and every result must match within 1e-9 relative.
"""
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.canonical.model import RawActivity, RawRecord, State, TimerEvent
from backend.canonical.timeline import build_timeline
from backend.metrics import m004_mmp
from backend.metrics.m002_m003_power import mean_power, mechanical_work

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference"))
import metric_oracle as oracle  # noqa: E402

T0 = 1_700_000_000.0

step = st.tuples(
    st.sampled_from([1.0, 1.0, 1.0, 1.0, 0.5, 1.3, 2.0, 4.0]),           # time to next record
    st.one_of(st.none(), st.integers(0, 1200).map(float)),               # None = field absent
)


@st.composite
def activities(draw):
    steps = draw(st.lists(step, min_size=2, max_size=60))
    t, records = 0.0, []
    for dt, p in steps:
        records.append(RawRecord(T0 + t, {} if p is None else {"power": p}))
        t += dt
    events = []
    if draw(st.booleans()):
        a = draw(st.floats(0, t)); b = draw(st.floats(a, t))
        events = [TimerEvent(T0, "start"), TimerEvent(T0 + a, "stop"), TimerEvent(T0 + b, "start")]
    return RawActivity("fit", records, events)


def to_oracle(tl):
    out = []
    for iv in tl.intervals:
        r = iv.reading("power")
        out.append(oracle.Interval(iv.start_s - T0, iv.end_s - T0,
                                   r.value if r.state is State.OBSERVED else None))
    return out


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return b == pytest.approx(a, rel=1e-9, abs=1e-9)


@settings(max_examples=300, deadline=None)
@given(activities(), st.sampled_from([0.5, 1.0, 2.5, 5.0, 10.0, 20.0]))
def test_agreement(raw, window):
    tl = build_timeline(raw)
    if not tl.intervals:
        return
    ref = oracle.aggregate(to_oracle(tl))
    assert ref["eligible_s"] == pytest.approx(tl.timer_s)
    assert close(ref["mean_power_w"], mean_power(tl).value)
    assert close(ref["mechanical_work_kj"], mechanical_work(tl).value)
    assert close(oracle.mmp(to_oracle(tl), window), m004_mmp.compute(tl, window).value)
