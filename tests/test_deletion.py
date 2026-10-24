"""WP9 deletion (spec 8.4, acceptance 15, C26). Synthetic data only.

Every test that deletes a recording ends with the marker scan: no file under
the data root (database, WAL and SHM included) and no path may contain the
deleted file's SHA256 (hex, upper case hex or raw bytes) or its filename.
"""
import json

import pytest
from sqlalchemy import select

from backend.library import aggregates, deletion, exports, rides
from backend.library.metric_store import latest
from backend.storage.schema import (activities, duplicate_group_events, duplicate_groups, metric_runs,
                                    ride_selection_history, rides as rides_t, source_files)
from ownership_helpers import LAT, MARKER, build, dump, needles_for, new_library, scan


@pytest.fixture
def lib(tmp_path):
    lib = new_library(tmp_path / "data")
    lib.ids = build(lib)
    return lib


def sha_of(lib, aid=None, sf_id=None):
    with lib.engine.connect() as c:
        if sf_id is None:
            sf_id = c.execute(select(activities.c.source_file_id).where(activities.c.id == aid)).scalar_one()
        row = c.execute(select(source_files).where(source_files.c.id == sf_id)).mappings().one()
    return row["sha256"], row["original_filename"]


def totals(lib):
    with lib.engine.connect() as c:
        return aggregates.totals(c, 0, 4e9)


def assert_gone(lib, sha, filename):
    assert scan(lib.root, needles_for(sha, filename)) == []
    wal = lib.paths["db"].with_name("cycling.db-wal")
    assert not wal.exists() or wal.stat().st_size == 0          # WAL truncated, no old page copies


def rows_about(d, aids):
    """Rows of the per recording tables that belong to the given activities."""
    keep = set(aids)
    out = {}
    for t in ("activities", "activity_channels", "samples", "timer_events", "timer_segments"):
        key = "id" if t == "activities" else "activity_id"
        out[t] = [r for r in d[t] if r[key] in keep]
    out["activity_runs"] = [r for r in d["metric_runs"] if r["scope_type"] == "activity" and r["scope_id"] in keep]
    return out


# ---------------------------------------------------------------- single recordings

def test_deleting_a_solo_recording_removes_everything_about_it(lib):
    aid = lib.ids["gps"]
    sha, name = sha_of(lib, aid)
    others = [a for a in range(1, 10) if a != aid]
    before = dump(lib)
    t0 = totals(lib)
    rep = deletion.delete_activity(lib, aid)
    after = dump(lib)
    assert rep.committed and rep.vault_object_removed and rep.groups == []
    assert rows_about(after, [aid]) == {k: [] for k in rows_about(before, [aid])}
    assert rows_about(after, others) == rows_about(before, others)                  # nothing else altered
    assert sha not in lib.vault.objects()
    assert totals(lib)["ride_count"] == t0["ride_count"] - 1                        # aggregates recomputed
    assert_gone(lib, sha, name)
    assert_gone(lib, sha, MARKER)


def test_scan_finds_the_hash_and_marker_before_deletion(lib):
    # Guards against a vacuous scan.
    sha, name = sha_of(lib, lib.ids["gps"])
    hits = scan(lib.root, needles_for(sha, MARKER))
    assert any("vault" in h for h in hits) and any("cycling.db" in h for h in hits)
    assert scan(lib.root, [str(LAT).encode()]) == []        # positions were never copied into the database


def test_deleting_a_failed_file_removes_its_row_and_original(lib):
    sf = lib.ids["failed_sf"]
    sha, name = sha_of(lib, sf_id=sf)
    rep = deletion.delete_source_file(lib, sf)
    assert rep.activity_id is None and rep.committed
    assert_gone(lib, sha, name)


# ---------------------------------------------------------------- duplicate groups (C26)

def test_deleting_the_power_source_of_a_confirmed_ride_unselects_it_and_flags_review(lib):
    ids = lib.ids
    sha, name = sha_of(lib, ids["hub"])
    before = dump(lib)
    rep = deletion.delete_activity(lib, ids["hub"])
    [g] = rep.groups
    assert (g.effect, g.fields_unselected, g.remaining_members) == ("member removed", ["power"], [ids["fenix"], ids["whoosh"]])
    assert rep.rides_needing_review == [ids["ride_a"]]
    with lib.engine.connect() as c:
        src = rides.sources(c, ids["ride_a"])
        ride = c.execute(select(rides_t).where(rides_t.c.id == ids["ride_a"])).mappings().one()
        runs = latest(c, "ride", [ids["ride_a"]])[ids["ride_a"]]
        hist = c.execute(select(ride_selection_history).where(ride_selection_history.c.ride_id == ids["ride_a"])).mappings().all()
    assert src["power"] is None and src["heart_rate"] == ids["fenix"] and src["cadence"] == ids["whoosh"]
    assert ride["needs_review"] and ride["active"]
    power_runs = [r for r in runs if r["metric_id"] in ("M002", "M003", "M004")]
    assert power_runs and all(r["state"] == "no_power" and r["value"] is None for r in power_runs)   # never 0
    assert [r for r in runs if r["metric_id"] == "M001"][0]["value"] == 1800.0
    assert any(h["source_deleted"] and h["channel"] == "power" and h["activity_id"] is None for h in hist)
    assert not any(h["activity_id"] == ids["hub"] for h in hist)
    others = [ids["fenix"], ids["whoosh"]]
    assert rows_about(dump(lib), others) == rows_about(before, others)                # other members untouched
    assert_gone(lib, sha, name)


def test_deleting_the_timer_source_leaves_the_ride_uncounted_until_reviewed(lib):
    ids = lib.ids
    t0 = totals(lib)
    deletion.delete_activity(lib, ids["fenix"])
    with lib.engine.connect() as c:
        src = rides.sources(c, ids["ride_a"])
        assert src["timer"] is None and src["heart_rate"] is None
        assert latest(c, "ride", [ids["ride_a"]])[ids["ride_a"]] == []           # no value until a timer is chosen
    t1 = totals(lib)
    assert t1["ride_count"] == t0["ride_count"] - 1
    # The rider chooses again; the ride counts again and the flag clears.
    with lib.engine.begin() as c:
        rides.change_selection(c, ids["ride_a"], {**{f: None for f in src}, "timer": ids["whoosh"],
                                                   "power": ids["hub"]}, lib.now())
    with lib.engine.connect() as c:
        assert not c.execute(select(rides_t.c.needs_review).where(rides_t.c.id == ids["ride_a"])).scalar()
    assert totals(lib)["ride_count"] == t0["ride_count"]


def test_a_confirmed_group_left_with_one_member_dissolves_into_a_single_ride(lib):
    ids = lib.ids
    deletion.delete_activity(lib, ids["pending"])
    deletion.delete_activity(lib, ids["hub"])
    rep = deletion.delete_activity(lib, ids["whoosh"])
    assert rep.groups[0].effect == "dissolved"
    with lib.engine.connect() as c:
        assert c.execute(select(duplicate_groups).where(duplicate_groups.c.id == ids["group_a"])).first() is None
        assert c.execute(select(rides_t).where(rides_t.c.id == ids["ride_a"])).first() is None
        assert c.execute(select(metric_runs).where(metric_runs.c.scope_type == "ride",
                                                   metric_runs.c.scope_id == ids["ride_a"])).first() is None
        single = c.execute(select(rides_t).where(rides_t.c.activity_id == ids["fenix"])).mappings().one()
    assert single["active"] and single["kind"] == "single"


def test_a_proposed_pair_dissolves_and_the_remaining_recording_is_untouched(lib):
    ids = lib.ids
    before = dump(lib)
    sha, name = sha_of(lib, ids["b1"])
    rep = deletion.delete_activity(lib, ids["b1"])
    assert rep.groups[0].effect == "dissolved" and rep.groups[0].status == "proposed"
    with lib.engine.connect() as c:
        assert c.execute(select(duplicate_group_events).where(duplicate_group_events.c.group_id == ids["group_b"])).first() is None
    assert rows_about(dump(lib), [ids["b2"]]) == rows_about(before, [ids["b2"]])
    assert_gone(lib, sha, name)


def test_deleting_a_pending_recording_changes_nothing_in_the_confirmed_ride(lib):
    ids = lib.ids
    with lib.engine.connect() as c:
        src = rides.sources(c, ids["ride_a"])
        vals = [(r["metric_id"], r["parameters"], r["value"], r["state"])
                for r in latest(c, "ride", [ids["ride_a"]])[ids["ride_a"]]]
    rep = deletion.delete_activity(lib, ids["pending"])
    assert rep.groups[0].fields_unselected == [] and rep.rides_needing_review == []
    with lib.engine.connect() as c:
        assert rides.sources(c, ids["ride_a"]) == src
        assert [(r["metric_id"], r["parameters"], r["value"], r["state"])
                for r in latest(c, "ride", [ids["ride_a"]])[ids["ride_a"]]] == vals
        events = c.execute(select(duplicate_group_events.c.activity_id, duplicate_group_events.c.detail_json)
                           .where(duplicate_group_events.c.group_id == ids["group_a"])).all()
    assert all(e.activity_id != ids["pending"] for e in events)


def test_events_and_evidence_no_longer_name_a_deleted_member(lib):
    ids = lib.ids
    deletion.delete_activity(lib, ids["hub"])
    with lib.engine.connect() as c:
        doc = json.loads(c.execute(select(duplicate_groups.c.overlap_json).where(duplicate_groups.c.id == ids["group_a"])).scalar())
        details = [json.loads(d) for (d,) in c.execute(select(duplicate_group_events.c.detail_json)
                                                        .where(duplicate_group_events.c.group_id == ids["group_a"],
                                                               duplicate_group_events.c.detail_json.is_not(None)))]
    assert all(ids["hub"] not in p["activity_ids"] for p in doc["pairs"]) and doc["pairs"]
    for d in details:
        assert ids["hub"] not in d.get("candidates", []) and ids["hub"] not in (d.get("selection") or {}).values()
    assert any((d.get("selection") or {}).get("power") == "deleted" for d in details)


# ---------------------------------------------------------------- preview and exports

def test_preview_matches_the_deletion_and_changes_nothing(lib):
    ids = lib.ids
    before = dump(lib)
    p = deletion.preview_activity(lib, ids["hub"])
    assert dump(lib) == before
    r = deletion.delete_activity(lib, ids["hub"])
    assert (p.groups, p.rides_needing_review) == (r.groups, r.rides_needing_review)


def test_exports_in_the_data_root_that_contain_the_file_are_removed(lib):
    ids = lib.ids
    old = exports.build(lib, "archive")["name"]
    sha, name = sha_of(lib, ids["gps"])
    assert deletion.preview_activity(lib, ids["gps"]).exports_removed == [old]
    rep = deletion.delete_activity(lib, ids["gps"])
    assert rep.exports_removed == [old] and exports.list_exports(lib) == []
    assert_gone(lib, sha, name)
    new = exports.build(lib, "archive")["name"]
    sha2, _ = sha_of(lib, ids["validity"])
    assert exports.containing(lib, sha2) == [new]


def test_deleting_every_recording_one_by_one_leaves_no_hash_and_an_empty_library(lib):
    with lib.engine.connect() as c:
        files = [(r.id, r.sha256, r.original_filename) for r in c.execute(select(source_files))]
    for sf, _, _ in files:
        deletion.delete_source_file(lib, sf)
    d = dump(lib)
    assert all(d[t] == [] for t in d if t not in ("metric_definitions", "app_settings", "channel_preferences"))
    for _, sha, name in files:
        assert scan(lib.root, needles_for(sha, name)) == [], name
    assert list(lib.paths["vault"].iterdir()) == []                  # fan out folders removed too


# ---------------------------------------------------------------- delete everything

def test_delete_everything_needs_the_current_token_and_keeps_files_it_did_not_create(lib):
    keep = lib.root / "my notes.txt"
    keep.write_text("not the app's")
    exports.build(lib, "derived")
    p = deletion.everything_preview(lib)
    assert p["counts"]["recordings"] == 10 and p["exports"] and p["kept_not_ours"] == ["my notes.txt"]
    assert any("Time Machine" in x for x in p["cannot_delete"])
    with pytest.raises(deletion.DeletionError):
        deletion.delete_everything(lib, "0" * 20)
    shas = lib.vault.objects()
    out = deletion.delete_everything(lib, p["token"])
    assert out["counts"]["recordings"] == 10
    assert keep.read_text() == "not the app's"
    for sha in shas:
        assert scan(lib.root, needles_for(sha)) == []
    assert scan(lib.root, needles_for(shas[0], MARKER, "fenix8.fit")) == []
    # The app carries on with an empty install.
    d = dump(lib)
    assert d["source_files"] == [] and d["metric_definitions"]
    assert sorted(p.name for p in lib.root.iterdir()) == ["db", "my notes.txt"]


def test_a_stale_token_is_refused(lib):
    p = deletion.everything_preview(lib)
    deletion.delete_activity(lib, lib.ids["gps"])
    with pytest.raises(deletion.DeletionError, match="changed"):
        deletion.delete_everything(lib, p["token"])
