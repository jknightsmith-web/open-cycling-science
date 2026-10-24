"""WP6 idempotent import: acceptance 3, 5 and 6 through the database."""
import io
import json
import zipfile

import pytest
from sqlalchemy import func, select

from backend.canonical.timeline import build_timeline
from backend.importers import fit
from backend.library import Library
from backend.library.ingest import import_bytes
from backend.library.metric_store import compute_activity_metrics, find, latest
from backend.storage.schema import activities, activity_channels, metric_runs, samples, source_files, timer_segments
from backend.storage.vault import sha256_bytes
from fit_encoder import EVENT_START, EVENT_STOP_ALL, INVALID, activity_file
from library_fixtures import T0, fenix, hub


@pytest.fixture
def lib(tmp_path):
    return Library(tmp_path / "data", now=lambda: 1_800_000_000.0)


def count(lib, table):
    with lib.engine.connect() as c:
        return c.execute(select(func.count()).select_from(table)).scalar()


def test_identical_bytes_create_no_activity(lib):
    data = fenix()
    first = import_bytes(lib, data, "ride.fit")[0]
    again = import_bytes(lib, data, "copy of ride.fit")[0]
    assert first.status == "imported" and again.status == "duplicate_bytes"
    assert again.activity_id == first.activity_id and again.sha256 == first.sha256
    assert "ride.fit" in again.message
    assert count(lib, activities) == 1 and count(lib, source_files) == 1


def test_vault_object_hash_equals_original(lib):
    data = hub()
    out = import_bytes(lib, data, "hub.tcx")[0]
    with lib.engine.connect() as c:
        sf = c.execute(select(source_files)).mappings().one()
    stored = (lib.root / sf["relative_storage_path"]).read_bytes()
    assert stored == data and sha256_bytes(stored) == out.sha256 == sf["sha256"]
    assert sf["media_format"] == "tcx" and sf["validation_status"] == "ok"


def test_failed_file_is_kept_and_reported(lib):
    bad = bytearray(fenix(10))
    bad[30] ^= 0xFF
    out = import_bytes(lib, bytes(bad), "broken.fit")[0]
    assert out.status == "failed" and out.error_code == "corrupt" and out.activity_id is None
    with lib.engine.connect() as c:
        sf = c.execute(select(source_files)).mappings().one()
    assert sf["validation_status"] == "failed" and json.loads(sf["validation_details"])["code"] == "corrupt"
    again = import_bytes(lib, bytes(bad), "broken again.fit")[0]
    assert again.status == "duplicate_bytes" and "failed" in again.message
    assert count(lib, activities) == 0


def test_unsupported_bytes_are_reported_not_stored(lib):
    out = import_bytes(lib, b"just text", "notes.txt")[0]
    assert out.status == "failed" and out.error_code == "unsupported"
    assert count(lib, source_files) == 0


def test_zip_members_import_individually_and_dedupe(lib):
    a, b = fenix(), hub()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x/a.fit", a)
        z.writestr("x/b.tcx", b)
        z.writestr("x/again.fit", a)
        z.writestr("readme.txt", b"skip")
    out = import_bytes(lib, buf.getvalue(), "export.zip")
    assert [o.status for o in out] == ["imported", "imported", "duplicate_bytes"]
    assert out[0].filename == "export.zip/x/a.fit"
    assert count(lib, activities) == 2


def test_samples_keep_zero_missing_and_invalid_distinct(lib):
    recs = [{"t": T0, "power": 0, "heart_rate": 0, "cadence": 0},          # observed 0 W, HR 0 invalid, 0 rpm observed
            {"t": T0 + 1, "power": INVALID, "heart_rate": 150},            # sentinel power invalid, cadence absent
            {"t": T0 + 2, "power": 250, "heart_rate": 151, "cadence": 92}]
    aid = import_bytes(lib, activity_file(recs), "z.fit")[0].activity_id
    with lib.engine.connect() as c:
        rows = c.execute(select(samples).where(samples.c.activity_id == aid).order_by(samples.c.sample_index)).mappings().all()
        chans = {r["channel"]: r for r in c.execute(select(activity_channels).where(activity_channels.c.activity_id == aid)).mappings()}
    assert (rows[0]["power_w"], rows[0]["power_validity"]) == (0.0, "observed")
    assert (rows[0]["heart_rate_bpm"], rows[0]["hr_validity"]) == (None, "invalid")
    assert (rows[0]["cadence_rpm"], rows[0]["cadence_validity"]) == (0.0, "observed")
    assert (rows[1]["power_w"], rows[1]["power_validity"]) == (None, "invalid")
    assert (rows[1]["cadence_rpm"], rows[1]["cadence_validity"]) == (None, "missing")
    assert (rows[0]["speed_mps"], rows[0]["speed_validity"]) == (None, "missing")
    assert chans["power"]["invalid_count"] == 1 and chans["heart_rate"]["invalid_count"] == 1
    assert not chans["speed"]["present"]
    assert json.loads(rows[2]["original_field_json"])["power"] == 250


def test_suspect_zero_flag_is_stored_without_changing_values(lib):
    recs = [{"t": T0 + i, "power": 0 if 2 <= i < 6 else 200, "cadence": 85} for i in range(10)]
    aid = import_bytes(lib, activity_file(recs), "sz.fit")[0].activity_id
    with lib.engine.connect() as c:
        rows = c.execute(select(samples.c.power_w, samples.c.power_validity, samples.c.suspect_zero)
                         .where(samples.c.activity_id == aid).order_by(samples.c.sample_index)).all()
        ch = c.execute(select(activity_channels.c.suspect_zero_s).where(activity_channels.c.activity_id == aid,
                                                                         activity_channels.c.channel == "power")).scalar()
    assert [bool(r.suspect_zero) for r in rows] == [False, False, True, True, True, True, False, False, False, False]
    assert all(r.power_validity == "observed" for r in rows) and rows[3].power_w == 0.0
    assert ch == pytest.approx(4.0)


def test_repeated_timestamp_is_stored_invalid(lib):
    recs = [{"t": T0, "power": 100}, {"t": T0, "power": 999}, {"t": T0 + 1, "power": 100}]
    aid = import_bytes(lib, activity_file(recs), "dup.fit")[0].activity_id
    with lib.engine.connect() as c:
        rows = c.execute(select(samples.c.power_w, samples.c.power_validity)
                         .where(samples.c.activity_id == aid).order_by(samples.c.sample_index)).all()
        flags = json.loads(c.execute(select(activities.c.recording_flags_json)).scalar())
    assert [tuple(r) for r in rows] == [(100.0, "observed"), (None, "invalid"), (100.0, "observed")]
    assert "duplicate_timestamps" in flags


def test_activity_metrics_and_provenance_match_direct_computation(lib):
    data = activity_file([{"t": T0 + i, "power": 100 if i < 30 else 300} for i in range(60)],
                         events=[(T0, EVENT_START), (T0 + 40, EVENT_STOP_ALL), (T0 + 45, EVENT_START)])
    out = import_bytes(lib, data, "m.fit")[0]
    expected = compute_activity_metrics(build_timeline(fit.parse(data)))
    with lib.engine.connect() as c:
        runs = latest(c, "activity", [out.activity_id])[out.activity_id]
        segs = c.execute(select(timer_segments.c.start_utc, timer_segments.c.end_utc)).all()
        timer_source = c.execute(select(activities.c.timer_source)).scalar()
    assert len(runs) == len(expected) == 8
    for r in expected:
        got = find(runs, r.metric_id, **r.parameters)
        assert got["value"] == r.value and got["state"] == r.state and got["version"] == r.version
        assert got["provenance"]["source_sha256"] == [out.sha256]
        assert len(got["input_revision"]) == 64 and got["computation_version"].startswith("ocs-")
    assert timer_source == "device_events" and [tuple(s) for s in segs] == [(T0, T0 + 40), (T0 + 45, T0 + 60)]
    assert find(runs, "M001")["value"] == 55


def test_vault_object_removed_if_database_write_fails(lib, monkeypatch):
    from backend.library import ingest

    def boom(*a, **k):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(ingest, "store_activity_metrics", boom)
    with pytest.raises(RuntimeError):
        import_bytes(lib, fenix(), "x.fit")
    assert count(lib, source_files) == 0 and count(lib, metric_runs) == 0
    assert not [p for p in (lib.root / "vault").rglob("*") if p.is_file()]
