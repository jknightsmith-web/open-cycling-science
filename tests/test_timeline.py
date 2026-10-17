"""Spec 5.2 to 5.5: validity, sample duration rule (D2), timer (D3), recording statistics."""
import pytest

from backend.canonical.model import RawActivity, RawRecord, State
from backend.canonical.timeline import TIMER_ASSUMED_CONTINUOUS, TIMER_DEVICE_EVENTS, build_timeline
from helpers import T0, ride


def spans(tl):
    return [(iv.start_s - T0, iv.end_s - T0, iv.is_gap) for iv in tl.intervals]


def test_regular_1hz_covers_every_second():
    tl = build_timeline(ride([200] * 10))
    assert tl.nominal_interval_s == 1.0
    assert tl.timer_s == 10
    assert all(not gap for *_, gap in spans(tl))
    assert tl.timer_source == TIMER_ASSUMED_CONTINUOUS


def test_strict_gap_rule_does_not_hold_values_across_gap():
    # records at 0..3 and 7..9: sample 3 covers [3,4), [4,7) is a gap (D2)
    tl = build_timeline(RawActivity("fit", [RawRecord(T0 + t, {"power": 200}) for t in (0, 1, 2, 3, 7, 8, 9)]))
    assert (3.0, 4.0, False) in spans(tl)
    assert (4.0, 7.0, True) in spans(tl)
    gap = next(iv for iv in tl.intervals if iv.is_gap)
    assert all(r.state is State.MISSING for r in gap.readings.values())


def test_interval_within_tolerance_is_held():
    # 1.4 s <= 1.5 x 1 s, so the sample covers it
    recs = [RawRecord(T0 + t, {"power": 100}) for t in (0, 1, 2, 3.4, 4.4, 5.4)]
    tl = build_timeline(RawActivity("fit", recs))
    assert (2.0, 3.4, False) in [(round(a, 6), round(b, 6), g) for a, b, g in spans(tl)]
    assert tl.stats.gap_count == 0


def test_duplicate_timestamps_keep_first_and_are_reported():
    recs = [RawRecord(T0, {"power": 100}), RawRecord(T0, {"power": 999}), RawRecord(T0 + 1, {"power": 100}),
            RawRecord(T0 + 2, {"power": 100})]
    tl = build_timeline(RawActivity("fit", recs))
    assert tl.duplicate_timestamp_count == 1
    assert "duplicate_timestamps" in tl.flags
    assert tl.intervals[0].reading("power").value == 100


def test_timer_pause_changes_timer_not_elapsed():
    # 15 records; timer stopped from 5 to 10 s by device events
    tl = build_timeline(ride([200] * 15, events=[(0, "start"), (5, "stop"), (10, "start")]))
    assert tl.timer_source == TIMER_DEVICE_EVENTS
    assert tl.timer_s == 10
    assert tl.t_end - tl.t_start == 15


def test_leading_stop_implies_running_from_first_record():
    tl = build_timeline(ride([200] * 10, events=[(5, "stop")]))
    assert tl.segments == [(T0, T0 + 5)]


def test_timer_start_before_first_record_is_a_gap_not_a_hold():
    # helper event times are relative to the first record; the timer starts 2 s earlier
    tl = build_timeline(ride([200] * 5, start=T0 + 2, events=[(-2, "start")]))
    assert spans(tl)[0] == (0.0, 2.0, True)


def test_device_timer_reported_separately_and_mismatch_flagged():
    assert "device_timer_mismatch" not in build_timeline(ride([200] * 100, device_timer_s=101)).flags
    assert "device_timer_mismatch" in build_timeline(ride([200] * 100, device_timer_s=110)).flags


def test_utc_offset_changes_nothing():
    a = build_timeline(ride([150, 250] * 30, utc_offset_s=0))
    b = build_timeline(ride([150, 250] * 30, utc_offset_s=10 * 3600))
    assert spans(a) == spans(b) and a.timer_s == b.timer_s


@pytest.mark.parametrize("channel,value,state", [
    ("power", 0, State.OBSERVED),
    ("cadence", 0, State.OBSERVED),
    ("heart_rate", 0, State.INVALID),
    ("power", None, State.INVALID),        # FIT invalid sentinel arrives as None
    ("power", 3500, State.INVALID),
    ("heart_rate", 140, State.OBSERVED),
])
def test_validity_states(channel, value, state):
    tl = build_timeline(RawActivity("fit", [RawRecord(T0 + i, {channel: value}) for i in range(3)]))
    assert tl.intervals[0].reading(channel).state is state


def test_absent_field_is_missing_not_zero():
    tl = build_timeline(ride([None, 200, 200]))
    r = tl.intervals[0].reading("power")
    assert r.state is State.MISSING and r.value is None


def test_suspect_zero_flags_without_changing_values():
    fields = [{"cadence": 85}] * 10
    tl = build_timeline(ride([200, 200, 0, 0, 0, 0, 200, 0, 200, 200], fields=fields))
    assert tl.suspect_zero_runs == [(T0 + 2, T0 + 6)]   # the 1 s zero at t=7 is below 3 s
    assert tl.intervals[2].reading("power") .value == 0
    assert tl.intervals[2].reading("power").state is State.OBSERVED


def test_zero_power_while_coasting_is_not_suspect():
    tl = build_timeline(ride([0] * 10, fields=[{"cadence": 0}] * 10))
    assert tl.suspect_zero_runs == []


def test_irregular_file_gets_statistics_not_rejection():
    # Smart Recording style intervals (spec 5.3 item 7, acceptance 17a)
    times = [0, 1, 2, 5, 6, 10, 11, 12, 20, 21, 22]
    tl = build_timeline(RawActivity("fit", [RawRecord(T0 + t, {"power": 180}) for t in times]))
    s = tl.stats
    assert s.irregular_recording and "irregular_recording" in tl.flags
    assert s.record_count == 11 and s.max_interval_s == 8
    assert s.gap_count == 3 and s.gap_s == pytest.approx(2 + 3 + 7)
    assert sum(s.interval_histogram.values()) == 10
    assert tl.intervals  # imported and assessed, not rejected


def test_single_record_is_flagged_insufficient():
    tl = build_timeline(ride([200]))
    assert "insufficient_samples" in tl.flags and tl.intervals == []
