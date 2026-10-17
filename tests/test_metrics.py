"""Spec 7 metric tests and Phase One acceptance items 7 to 11."""
import pytest

from backend.canonical.timeline import build_timeline
from backend.metrics import m001_duration, m004_mmp
from backend.metrics.m002_m003_power import mean_power, mechanical_work
from backend.metrics.result import INSUFFICIENT_COVERAGE, LOWER_BOUND, NO_POWER, VALID
from helpers import ride


def test_acceptance_7_steady_200w():
    tl = build_timeline(ride([200] * 10))
    assert mean_power(tl).value == 200
    assert mechanical_work(tl).value == 2
    assert m004_mmp.compute(tl, 5).value == 200


def test_acceptance_7_split_100_300():
    tl = build_timeline(ride([100] * 5 + [300] * 5))
    assert mean_power(tl).value == 200
    assert mechanical_work(tl).value == 2
    assert m004_mmp.compute(tl, 5).value == 300


def test_m003_one_hour_250w():
    assert mechanical_work(build_timeline(ride([250] * 3600))).value == pytest.approx(900)


def test_acceptance_8_gap_invalidates_crossing_windows():
    # 10 s observation with a 3 s missing gap at 4..6 (records absent)
    tl = build_timeline(_gap_ride())
    assert m004_mmp.compute(tl, 5).state == INSUFFICIENT_COVERAGE
    assert m004_mmp.compute(tl, 4).value == 200     # only the 4 s run before the gap qualifies
    assert m004_mmp.compute(tl, 3).value == 300


def _gap_ride():
    from backend.canonical.model import RawActivity, RawRecord
    from helpers import T0
    pts = [(0, 200), (1, 200), (2, 200), (3, 200), (7, 300), (8, 300), (9, 300)]
    return RawActivity("fit", [RawRecord(T0 + t, {"power": p}) for t, p in pts])


def test_mmp_needs_t_contiguous_valid_seconds():
    tl = build_timeline(ride([200] * 9))
    assert m004_mmp.compute(tl, 10).state == INSUFFICIENT_COVERAGE
    assert m004_mmp.compute(tl, 9).value == 200


def test_mmp_does_not_cross_timer_stop():
    tl = build_timeline(ride([200] * 15, events=[(0, "start"), (5, "stop"), (10, "start")]))
    assert m004_mmp.compute(tl, 6).state == INSUFFICIENT_COVERAGE
    assert m004_mmp.compute(tl, 5).value == 200


def test_mmp_fractional_window_on_step_function():
    tl = build_timeline(ride([100, 300, 100]))
    assert m004_mmp.compute(tl, 1.5).value == pytest.approx((300 + 0.5 * 100) / 1.5)


def test_acceptance_9_timer_stop():
    r = m001_duration.compute(build_timeline(ride([200] * 15, events=[(0, "start"), (5, "stop"), (10, "start")])))
    assert r.details["timer_s"] == 10 and r.details["elapsed_s"] == 15


def test_m001_without_events_is_labelled_assumed_continuous():
    r = m001_duration.compute(build_timeline(ride([200] * 10, fmt="tcx", device_timer_s=10)))
    assert r.details["timer_source"] == "assumed_continuous"
    assert r.details["device_timer_s"] == 10 and r.value == 10


def test_acceptance_10_time_zone_does_not_change_values():
    a = build_timeline(ride([120, 260] * 50, utc_offset_s=0))
    b = build_timeline(ride([120, 260] * 50, utc_offset_s=-7 * 3600))
    for f in (mean_power, mechanical_work):
        assert f(a).value == f(b).value
    assert m004_mmp.compute(a, 5).value == m004_mmp.compute(b, 5).value


def test_acceptance_11_low_coverage():
    # 7 of 10 s observed: mean withheld, work reported as lower bound (D1)
    tl = build_timeline(ride([200] * 4 + [None] * 3 + [200] * 3))
    mp, w = mean_power(tl), mechanical_work(tl)
    assert mp.state == INSUFFICIENT_COVERAGE and mp.value is None
    assert w.state == LOWER_BOUND and w.value == pytest.approx(1.4)
    assert mp.details["coverage"] == pytest.approx(0.7)


def test_missing_gap_is_not_counted_as_zero():
    tl = build_timeline(ride([200] * 38 + [None] * 2 + [200] * 60))
    mp = mean_power(tl)
    assert mp.state == VALID and mp.value == 200


def test_zero_watts_are_included():
    tl = build_timeline(ride([0] * 5 + [200] * 5))
    assert mean_power(tl).value == 100 and mechanical_work(tl).value == 1


def test_no_power_channel():
    tl = build_timeline(ride([None] * 10, fields=[{"heart_rate": 120}] * 10))
    assert mean_power(tl).state == NO_POWER and mechanical_work(tl).state == NO_POWER
    assert m004_mmp.compute(tl, 5).state == NO_POWER
