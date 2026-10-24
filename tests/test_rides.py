"""WP6 duplicate proposals, rider decisions, per channel selection and aggregates.

Acceptance 4 and 4a; Jimmy's WP6 requirements of 2026-10-24.
"""
import pytest
from sqlalchemy import select

from backend.library import Library, aggregates, rides
from backend.library.ingest import import_bytes
from backend.library.metric_store import find, latest
from backend.storage.schema import SELECTABLE_FIELDS, duplicate_group_events, ride_selection_history
from fit_encoder import activity_file
from library_fixtures import T0, fenix, hub, vault_digest, whoosh

RANGE = (T0 - 3600, T0 + 86400)


@pytest.fixture
def lib(tmp_path):
    clock = iter(range(1_800_000_000, 1_900_000_000))
    return Library(tmp_path / "data", now=lambda: float(next(clock)))


def imp(lib, data, name):
    out = import_bytes(lib, data, name)[0]
    assert out.status == "imported", out
    return out


def totals(lib):
    with lib.engine.connect() as c:
        return aggregates.totals(c, *RANGE)


def act(lib, fn, *a, **k):
    with lib.engine.begin() as c:
        return fn(c, *a, **k)


def full(sel_activity_id_by_field):
    return {f: sel_activity_id_by_field.get(f) for f in SELECTABLE_FIELDS}


def ride_metric(lib, ride_id, metric_id, **params):
    with lib.engine.connect() as c:
        return find(latest(c, "ride", [ride_id])[ride_id], metric_id, **params)


def activity_metric(lib, aid, metric_id, **params):
    with lib.engine.connect() as c:
        return find(latest(c, "activity", [aid])[aid], metric_id, **params)


# ---------------------------------------------------------------- proposals

def test_overlapping_sources_are_proposed_with_evidence_not_merged(lib):
    a, b = imp(lib, fenix(), "fenix.fit"), imp(lib, hub(), "hub.tcx")
    assert a.group_id is None and b.group_id is not None
    with lib.engine.connect() as c:
        g = rides.group(c, b.group_id)
        assert g["status"] == "proposed" and g["rule_version"] == "1.1"
        assert rides.members(c, b.group_id) == [a.activity_id, b.activity_id]
    import json
    pair = json.loads(g["overlap_json"])["pairs"][0]
    assert pair["overlap_fraction"] == pytest.approx(1.0)
    assert pair["start_offset_s"] == pytest.approx(-1.0) and pair["same_recording_identity"] is False
    t = totals(lib)
    assert t["ride_count"] == 2 and t["state"] == "unconfirmed_duplicates_included"


def test_three_sources_join_one_proposed_group(lib):
    a, b, w = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx"), imp(lib, whoosh(), "w.fit")
    assert b.group_id == w.group_id
    with lib.engine.connect() as c:
        assert rides.members(c, b.group_id) == [a.activity_id, b.activity_id, w.activity_id]


def test_low_overlap_is_not_proposed(lib):
    imp(lib, fenix(600), "a.fit")
    later = imp(lib, fenix(600, start=T0 + 400, serial=9), "b.fit")   # 200 s of 600 overlap = 33%
    assert later.group_id is None
    assert totals(lib)["state"] == "valid"


def test_same_recording_identity_is_proposed_without_overlap(lib):
    imp(lib, fenix(300), "original.fit")
    # Same device serial and creation time, different bytes and times: a re-export, not a second ride.
    data = activity_file([{"t": T0 + 5000 + i, "power": 180} for i in range(300)],
                         file_id={"manufacturer": 1, "product": 4536, "serial_number": 3_400_001, "time_created": T0 - 631065600})
    out = imp(lib, data, "reexport.fit")
    assert out.group_id is not None
    import json
    with lib.engine.connect() as c:
        pair = json.loads(rides.group(c, out.group_id)["overlap_json"])["pairs"][0]
    assert pair["overlap_fraction"] == 0 and pair["same_recording_identity"] and pair["same_device"]


# ---------------------------------------------------------------- acceptance 4

def test_acceptance_4_count_before_confirm_after_and_undo(lib):
    a, b = imp(lib, fenix(600, power=200), "fenix.fit"), imp(lib, hub(595, power=210), "hub.tcx")
    before_vault = vault_digest(lib.root)
    t0 = totals(lib)
    assert t0["ride_count"] == 2 and t0["duration_s"] == pytest.approx(1195)
    assert t0["work_kj"] == pytest.approx(120 + 124.95)
    over = t0["potential_overcount"]
    assert over["unconfirmed_group_count"] == 1 and over["duration_s"] == pytest.approx(595)
    assert over["work_kj"] == pytest.approx(124.95) and over["activity_ids"] == [b.activity_id]

    ride_id = act(lib, rides.confirm, b.group_id, full({"timer": a.activity_id, "power": a.activity_id,
                                                         "heart_rate": a.activity_id, "cadence": b.activity_id}),
                  lib.now())
    t1 = totals(lib)
    assert t1["ride_count"] == 1 and t1["duration_s"] == pytest.approx(600) and t1["work_kj"] == pytest.approx(120)
    assert t1["state"] == "valid" and t1["potential_overcount"]["ride_count"] == 0
    assert ride_metric(lib, ride_id, "M002")["value"] == pytest.approx(200)

    act(lib, rides.reopen, b.group_id, lib.now())
    assert totals(lib) == t0                                     # undo restores the previous totals
    act(lib, rides.reject, b.group_id, lib.now())
    t3 = totals(lib)
    assert t3["ride_count"] == 2 and t3["state"] == "valid"      # rejected: separate rides, nothing to warn about
    assert t3["duration_s"] == t0["duration_s"] and t3["work_kj"] == t0["work_kj"]
    act(lib, rides.reopen, b.group_id, lib.now())
    assert totals(lib) == t0
    assert vault_digest(lib.root) == before_vault               # no original file changed in any step
    with lib.engine.connect() as c:
        actions = [r[0] for r in c.execute(select(duplicate_group_events.c.action).order_by(duplicate_group_events.c.id))]
    assert actions == ["proposed", "confirmed", "reopened", "rejected", "reopened"]


# ---------------------------------------------------------------- acceptance 4a

def test_acceptance_4a_each_channel_from_a_different_member(lib):
    f = imp(lib, fenix(600, power=200), "fenix.fit")
    h = imp(lib, hub(595, power=210, cadence=91), "hub.tcx")
    w = imp(lib, whoosh(590, power=205), "whoosh.fit")
    sel = full({"timer": f.activity_id, "power": h.activity_id, "heart_rate": f.activity_id,
                "cadence": w.activity_id, "speed": w.activity_id, "distance": w.activity_id})
    ride_id = act(lib, rides.confirm, h.group_id, sel, lib.now())
    with lib.engine.connect() as c:
        src = rides.sources(c, ride_id)
    assert src == sel and src["temperature"] is None             # no member recorded it: missing, not zero
    # Power metrics come from the Hub file with its own timer and coverage (spec 5.8, C25).
    for metric_id, params in (("M002", {}), ("M003", {}), ("M004", {"duration_s": 60})):
        r, a = ride_metric(lib, ride_id, metric_id, **params), activity_metric(lib, h.activity_id, metric_id, **params)
        assert (r["value"], r["state"]) == (a["value"], a["state"])
        assert r["provenance"]["activity_ids"] == [h.activity_id] and r["provenance"]["source_sha256"] == [h.sha256]
    assert ride_metric(lib, ride_id, "M002")["value"] == pytest.approx(210)
    # Duration comes from the selected timer source.
    assert ride_metric(lib, ride_id, "M001")["value"] == pytest.approx(600)
    assert totals(lib)["duration_s"] == pytest.approx(600)
    assert totals(lib)["work_kj"] == pytest.approx(210 * 595 / 1000)


def test_changing_a_selection_creates_a_new_revision_and_keeps_history(lib):
    f, h = imp(lib, fenix(600, power=200), "f.fit"), imp(lib, hub(595, power=210), "h.tcx")
    base = {"timer": f.activity_id, "power": f.activity_id, "heart_rate": f.activity_id, "cadence": f.activity_id}
    ride_id = act(lib, rides.confirm, h.group_id, full(base), lib.now())
    first = ride_metric(lib, ride_id, "M002")
    rev = act(lib, rides.change_selection, ride_id, full({**base, "power": h.activity_id}), lib.now())
    second = ride_metric(lib, ride_id, "M002")
    assert rev == 2 and first["value"] == pytest.approx(200) and second["value"] == pytest.approx(210)
    assert first["input_revision"] != second["input_revision"]
    with lib.engine.connect() as c:
        hist = c.execute(select(ride_selection_history).where(ride_selection_history.c.ride_id == ride_id,
                                                              ride_selection_history.c.channel == "power")
                         .order_by(ride_selection_history.c.id)).mappings().all()
    assert [(r["selection_revision"], r["activity_id"], r["selected_by"]) for r in hist] == [
        (1, f.activity_id, "rider"), (2, h.activity_id, "rider")]


def test_no_power_source_makes_power_metrics_unavailable(lib):
    f, h = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx")
    ride_id = act(lib, rides.confirm, h.group_id, full({"timer": f.activity_id, "heart_rate": f.activity_id}), lib.now())
    m = ride_metric(lib, ride_id, "M002")
    assert m["value"] is None and m["state"] == "no_power"
    assert totals(lib)["rides_by_work_state"] == {"no_power": 1} and totals(lib)["work_kj"] == 0


# ---------------------------------------------------------------- validation of rider input

@pytest.mark.parametrize("bad,message", [
    ({"timer": "F", "power": "F"}, "every field explicitly"),
    ({**{f: None for f in SELECTABLE_FIELDS}}, "timer source"),
    ({**{f: None for f in SELECTABLE_FIELDS}, "timer": "F", "heart_rate": "H"}, "did not record"),
    ({**{f: None for f in SELECTABLE_FIELDS}, "timer": 999}, "not a member"),
    ({**{f: None for f in SELECTABLE_FIELDS}, "timer": "F", "watts": "F"}, "unknown fields"),
])
def test_invalid_selection_is_refused_and_changes_nothing(lib, bad, message):
    f, h = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx")
    sel = {k: {"F": f.activity_id, "H": h.activity_id}.get(v, v) for k, v in bad.items()}
    before = totals(lib)
    with pytest.raises(rides.DecisionError, match=message):
        act(lib, rides.confirm, h.group_id, sel, lib.now())
    assert totals(lib) == before
    with lib.engine.connect() as c:
        assert rides.group(c, h.group_id)["status"] == "proposed"


def test_decisions_require_the_right_state(lib):
    f, h = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx")
    gid = h.group_id
    with pytest.raises(rides.DecisionError):
        act(lib, rides.reopen, gid, lib.now())
    act(lib, rides.reject, gid, lib.now())
    with pytest.raises(rides.DecisionError):
        act(lib, rides.confirm, gid, full({"timer": f.activity_id}), lib.now())
    with pytest.raises(rides.DecisionError):
        act(lib, rides.change_selection, rides_single(lib, f.activity_id), full({"timer": f.activity_id}), lib.now())


def rides_single(lib, aid):
    with lib.engine.connect() as c:
        return rides.single_ride_id(c, aid)


def test_confirm_can_leave_a_member_out(lib):
    f, h, w = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx"), imp(lib, whoosh(), "w.fit")
    act(lib, rides.confirm, h.group_id, full({"timer": f.activity_id, "power": h.activity_id}), lib.now(),
        exclude=(w.activity_id,))
    t = totals(lib)
    assert t["ride_count"] == 2 and t["state"] == "valid"        # the excluded MyWhoosh file is its own ride
    act(lib, rides.reopen, h.group_id, lib.now())
    with lib.engine.connect() as c:
        assert rides.members(c, h.group_id) == [f.activity_id, h.activity_id, w.activity_id]
    with pytest.raises(rides.DecisionError, match="at least two"):
        act(lib, rides.confirm, h.group_id, full({"timer": f.activity_id}), lib.now(),
            exclude=(h.activity_id, w.activity_id))


# ---------------------------------------------------------------- late arrivals

def test_late_recording_is_pending_until_accepted(lib):
    f, h = imp(lib, fenix(600, power=200), "f.fit"), imp(lib, hub(595, power=210), "h.tcx")
    ride_id = act(lib, rides.confirm, h.group_id, full({"timer": f.activity_id, "power": f.activity_id}), lib.now())
    w = imp(lib, whoosh(590, power=205), "w.fit")
    assert w.group_id == h.group_id
    with lib.engine.connect() as c:
        assert rides.members(c, h.group_id, "pending") == [w.activity_id]
    t = totals(lib)
    assert t["ride_count"] == 2 and t["state"] == "unconfirmed_duplicates_included"
    assert t["potential_overcount"]["pending_recording_count"] == 1
    assert ride_metric(lib, ride_id, "M002")["value"] == pytest.approx(200)   # confirmed ride unchanged

    act(lib, rides.accept_pending, h.group_id, w.activity_id,
        full({"timer": f.activity_id, "power": w.activity_id, "cadence": w.activity_id}), lib.now())
    t = totals(lib)
    assert t["ride_count"] == 1 and t["state"] == "valid"
    assert ride_metric(lib, ride_id, "M002")["value"] == pytest.approx(205)


def test_late_recording_can_be_excluded(lib):
    f, h = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx")
    act(lib, rides.confirm, h.group_id, full({"timer": f.activity_id, "power": f.activity_id}), lib.now())
    w = imp(lib, whoosh(), "w.fit")
    act(lib, rides.exclude_pending, h.group_id, w.activity_id, lib.now())
    t = totals(lib)
    assert t["ride_count"] == 2 and t["state"] == "valid"


# ---------------------------------------------------------------- prefill and preferences

def test_prefill_suggests_but_never_applies(lib):
    f, h, w = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx"), imp(lib, whoosh(), "w.fit")
    act(lib, rides.set_preferences, {"power": [{"source_format": "tcx"}], "cadence": [{"source_platform": "mywhoosh"}]})
    with lib.engine.connect() as c:
        pf = rides.prefill(c, [f.activity_id, h.activity_id, w.activity_id])
        status = rides.group(c, h.group_id)["status"]
    assert pf["power"] == {"activity_id": h.activity_id, "basis": "preference", "rule": {"source_format": "tcx"}}
    assert pf["cadence"]["activity_id"] == w.activity_id and pf["cadence"]["basis"] == "preference"
    assert pf["heart_rate"] == {"activity_id": f.activity_id, "basis": "most observed seconds"}
    assert pf["temperature"]["activity_id"] is None
    assert status == "proposed" and totals(lib)["ride_count"] == 3


def test_preference_rules_are_validated(lib):
    with pytest.raises(rides.DecisionError):
        act(lib, rides.set_preferences, {"power": [{"serial": 1}]})
    with pytest.raises(rides.DecisionError):
        act(lib, rides.set_preferences, {"watts": [{"source_format": "fit"}]})


# ---------------------------------------------------------------- activity values for every member

def test_activity_values_exist_for_every_member_regardless_of_decisions(lib):
    f, h = imp(lib, fenix(), "f.fit"), imp(lib, hub(), "h.tcx")
    act(lib, rides.confirm, h.group_id, full({"timer": f.activity_id, "power": f.activity_id}), lib.now())
    assert activity_metric(lib, h.activity_id, "M002")["value"] == pytest.approx(210)
    assert activity_metric(lib, f.activity_id, "M002")["value"] == pytest.approx(200)


def test_best_mmp_links_its_source(lib):
    f = imp(lib, fenix(600, power=200), "f.fit")
    best = totals(lib)["best_mmp_w"]
    assert best["60"]["value"] == pytest.approx(200) and best["60"]["source_sha256"] == [f.sha256]
    assert best["1200"] is None                                  # no run of 1200 s: unavailable, not zero
