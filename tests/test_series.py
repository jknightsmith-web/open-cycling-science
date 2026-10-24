"""Design 06 B3 and UI-19: the chart envelope never joins observations across a break."""
import pytest
from hypothesis import given, settings, strategies as st

from backend.canonical.digest import timeline_digest
from backend.canonical.model import State
from backend.canonical.timeline import EPS, build_timeline
from backend.library import Library
from backend.library.ingest import import_bytes
from backend.library.metric_store import find, latest
from backend.library.series import envelope, load_timeline, runs_and_breaks
from fit_encoder import EVENT_START, EVENT_STOP_ALL, INVALID, activity_file
from helpers import T0, ride


def _observed_between(tl, channel, a, b):
    """True when every timeline instant in [a, b) has an observed value, inside one segment, with no gap."""
    covered = a
    for iv in tl.intervals:
        if iv.end_s <= a + EPS or iv.start_s >= b - EPS:
            continue
        if iv.is_gap or iv.reading(channel).state is not State.OBSERVED or iv.start_s > covered + EPS:
            return False
        covered = iv.end_s
    return covered >= b - EPS


def _non_observed_stretches(tl, channel):
    out, prev = [], None
    for iv in tl.intervals:
        if prev is not None and iv.start_s > prev + EPS:
            out.append((prev, iv.start_s))
        if iv.is_gap or iv.reading(channel).state is not State.OBSERVED:
            out.append((iv.start_s, iv.end_s))
        prev = iv.end_s
    return out


values = st.one_of(st.none(), st.just("invalid"), st.floats(0, 1500, allow_nan=False))


@settings(max_examples=300, deadline=None)
@given(st.lists(values, min_size=2, max_size=400),
       st.lists(st.integers(0, 399), max_size=6),        # positions of dropped records (recording gaps)
       st.integers(16, 200),                              # points budget, small to force bucketing
       st.booleans())
def test_envelope_never_bridges_a_break(vals, drops, points, paused):
    fields = [({} if v is None else {"power": None if v == "invalid" else v}) for v in vals]
    keep = [i for i in range(len(vals)) if i not in set(drops)]
    if len(keep) < 2:
        return
    events = [(0, "start"), (len(vals) // 3, "stop"), (len(vals) // 2, "start")] if paused else None
    raw = ride([None] * len(vals), fields=fields, events=events)
    raw.records[:] = [raw.records[i] for i in keep]
    tl = build_timeline(raw)
    env = envelope(tl, "power", points)
    for run in env["runs"]:
        assert run["t"] == sorted(run["t"])
        assert _observed_between(tl, "power", run["t"][0], run["t"][-1]), run
    # Every non observed stretch of the timeline is covered by a reported break.
    for a, b in _non_observed_stretches(tl, "power"):
        assert any(br["start"] <= a + EPS and br["end"] >= b - EPS for br in env["breaks"]), (a, b, env["breaks"])
    # Runs and breaks never overlap.
    for run in env["runs"]:
        for br in env["breaks"]:
            assert run["t"][-1] <= br["start"] + EPS or run["t"][0] >= br["end"] - EPS


def test_break_reasons_are_named():
    fields = [{"power": 200}] * 3 + [{}] + [{"power": None}] + [{"power": 200}] * 3
    raw = ride([None] * 8, fields=fields)
    del raw.records[6]                                    # 2 s hole at t=6: a recording gap
    tl = build_timeline(raw)
    _, breaks = runs_and_breaks(tl, "power")
    assert [b["reason"] for b in breaks] == ["missing", "invalid", "gap"]


def test_paused_time_is_a_break():
    raw = ride([200] * 20, events=[(0, "start"), (8, "stop"), (12, "start")])
    runs, breaks = runs_and_breaks(build_timeline(raw), "power")
    assert len(runs) == 2 and breaks == [{"start": T0 + 8, "end": T0 + 12, "reason": "paused"}]


def test_envelope_keeps_extremes_and_bounds_points():
    powers = [200.0] * 10_000
    powers[5_000] = 1400.0                                # a one second spike must survive reduction
    env = envelope(build_timeline(ride(powers)), "power", 400)
    assert env["points_returned"] <= 420 and max(env["runs"][0]["v"]) == 1400.0 and env["kind"] == "display_envelope"


def test_timeline_rebuilt_from_database_is_the_canonical_timeline(tmp_path):
    lib = Library(tmp_path / "data")
    recs = [{"t": T0 + i, "power": INVALID if i == 7 else (0 if 20 <= i < 25 else 180), "heart_rate": 0 if i == 3 else 140,
             "cadence": 85} for i in range(60) if i not in (40, 41, 42)]
    recs.insert(10, {"t": T0 + 9, "power": 999})          # repeated timestamp
    data = activity_file(recs, events=[(T0, EVENT_START), (T0 + 30, EVENT_STOP_ALL), (T0 + 33, EVENT_START)])
    aid = import_bytes(lib, data, "x.fit")[0].activity_id
    with lib.engine.connect() as c:
        tl = load_timeline(c, aid)
        stored = find(latest(c, "activity", [aid])[aid], "M001")["input_revision"]
    assert timeline_digest(tl) == stored
