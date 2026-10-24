"""WP9 exports and archive restoration (spec 8.3, acceptance 14 and 16). Synthetic data only."""
import csv
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from backend.library import exports, restore
from backend.library.exports import TABLES
from backend.storage.maintenance import PARTIAL_PREFIX
from backend.storage.vault import sha256_bytes
from ownership_helpers import LAT, LONG, MARKER, build, dump, new_library


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp("source") / "data"
    lib = new_library(root)
    ids = build(lib)
    arch = exports.build(lib, "archive")
    return lib, ids, Path(arch["path"])


def fresh(tmp_path, name="restored"):
    return new_library(tmp_path / name)


def rewrite(src: Path, dst: Path, edit) -> Path:
    """Copy a ZIP, letting `edit(name, bytes)` change or drop members (return None to drop)."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = edit(info.filename, zin.read(info))
            if data is not None:
                zout.writestr(info.filename, data)
    return dst


def manifest_edit(fn):
    def edit(name, data):
        if name == "manifest.json":
            m = json.loads(data)
            fn(m)
            return json.dumps(m).encode()
        return data
    return edit


def assert_empty(lib):
    d = dump(lib)
    for t in ("source_files", "activities", "samples", "rides", "duplicate_groups", "metric_runs"):
        assert d[t] == [], t
    assert lib.vault.objects() == []


# ---------------------------------------------------------------- acceptance 14

def test_full_archive_round_trip_reproduces_every_row_hash_and_value(source, tmp_path):
    lib, ids, arch = source
    target = fresh(tmp_path)
    report = restore.restore(target, arch)
    assert report["recompute_check"]["status"] == "passed"
    assert report["recompute_check"]["activities"] == 9
    before, after = dump(lib), dump(target)
    for t in before:
        assert after[t] == before[t], f"{t} differs after restore"
    # Vault: identical objects, identical bytes.
    assert target.vault.objects() == lib.vault.objects()
    for digest in lib.vault.objects():
        assert sha256_bytes(target.vault.path_for(digest).read_bytes()) == digest
    # Row counts and metric values as the manifest recorded them.
    man = exports.read_manifest(arch)
    assert report["restored_rows"] == man["row_counts"]
    assert {t: len(rows) for t, rows in after.items()} == man["row_counts"]


def test_exporting_the_restored_library_gives_identical_data_files(source, tmp_path):
    lib, _, arch = source
    target = fresh(tmp_path)
    restore.restore(target, arch)
    again = exports.read_manifest(Path(exports.build(target, "archive")["path"]))
    first = exports.read_manifest(arch)
    assert again["files"] == first["files"]          # every CSV, JSON Lines and original, byte for byte
    assert again["row_counts"] == first["row_counts"]


def test_restored_library_keeps_rides_decisions_and_selections(source, tmp_path):
    lib, ids, arch = source
    target = fresh(tmp_path)
    restore.restore(target, arch)
    from backend.library import aggregates, rides
    with lib.engine.connect() as c, target.engine.connect() as d:
        assert rides.sources(d, ids["ride_a"]) == rides.sources(c, ids["ride_a"])
        assert rides.sources(d, ids["ride_a"])["power"] == ids["hub"]
        assert aggregates.totals(d, 0, 4e9) == aggregates.totals(c, 0, 4e9)
        assert rides.get_preferences(d) == rides.get_preferences(c)


# ---------------------------------------------------------------- export contents (spec 8.3, 8.2)

def test_manifest_lists_the_sha256_of_every_file_and_the_required_fields(source):
    _, _, arch = source
    man = exports.read_manifest(arch)
    for key in ("app_version", "schema_version", "created_at_utc", "row_counts", "files", "metric_versions"):
        assert key in man
    with zipfile.ZipFile(arch) as z:
        names = {n for n in z.namelist() if n != "manifest.json"}
        assert names == set(man["files"])
        for n in names:
            assert hashlib.sha256(z.read(n)).hexdigest() == man["files"][n]["sha256"]
    assert {v["metric_id"] for v in man["metric_versions"]} == {"M001", "M002", "M003", "M004"}
    assert {t.name for t in TABLES} == set(man["row_counts"])


def test_originals_export_is_byte_identical_with_original_filenames(source):
    lib, _, _ = source
    e = exports.build(lib, "originals")
    with zipfile.ZipFile(e["path"]) as z:
        man = json.loads(z.read("manifest.json"))
        names = sorted(n for n in z.namelist() if n.startswith("originals/"))
        assert "originals/export.zip_rides_zipped ride.fit" in names   # ZIP member path kept, flattened
        assert f"originals/{MARKER}.fit" in names
        assert not any(n.startswith("data/") for n in z.namelist())
        for o in man["originals"]:
            data = z.read(o["path"])
            assert sha256_bytes(data) == o["sha256"]
            assert data == lib.vault.read(o["sha256"])
    assert "GPS" in man["location"]


def test_originals_keep_gps_but_derived_data_holds_no_location(source):
    lib, ids, arch = source
    with zipfile.ZipFile(arch) as z:
        gps_original = z.read(f"originals/{MARKER}.fit")
        assert LAT.to_bytes(4, "little", signed=True) in gps_original       # D5: originals byte identical
        for n in z.namelist():
            if n.startswith("data/"):
                text = z.read(n).decode()
                assert "position" not in text and str(LAT) not in text and str(LONG) not in text, n


def test_derived_csv_follows_rfc4180_with_empty_for_missing_and_no_rounding(source):
    lib, ids, _ = source
    e = exports.build(lib, "derived")
    with zipfile.ZipFile(e["path"]) as z:
        assert not any(n.startswith("originals/") for n in z.namelist())
        raw = z.read("data/csv/samples.csv")
        jsonl = [json.loads(line) for line in z.read("data/json/samples.jsonl").splitlines()]
    assert raw.count(b"\r\n") == len(jsonl) + 1
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))
    header = rows[0].keys()
    assert {"power_w", "power_validity", "heart_rate_bpm", "speed_mps", "distance_m", "temp_c", "timestamp_utc"} <= set(header)
    states = {}
    for r, j in zip(rows, jsonl):
        assert (r["power_w"] == "") == (r["power_validity"] != "observed")      # empty means missing or invalid
        if r["power_w"]:
            assert float(r["power_w"]) == j["power_w"]                           # exact round trip
        states.setdefault(r["power_validity"], set()).add(r["power_w"])
    assert {"observed", "missing", "invalid"} <= set(states)
    assert "0.0" in states["observed"]                                          # observed zero is 0, written
    assert states["missing"] == {""} and states["invalid"] == {""}
    # A float with many digits survives as written.
    act_rows = list(csv.DictReader(io.StringIO(zipfile.ZipFile(e["path"]).read("data/csv/activities.csv").decode(), newline="")))
    for a in act_rows:
        if a["timer_s"]:
            assert repr(float(a["timer_s"])) == a["timer_s"]


def test_export_rehashes_vault_objects_and_stops_on_corruption(tmp_path):
    lib = new_library(tmp_path / "data")
    build(lib)
    digest = lib.vault.objects()[0]
    p = lib.vault.path_for(digest)
    p.chmod(0o600)
    p.write_bytes(p.read_bytes()[:-1] + b"\x00")
    with pytest.raises(Exception, match="rehashes"):
        exports.build(lib, "archive")
    assert exports.list_exports(lib) == []
    assert not list(lib.paths["exports"].glob(PARTIAL_PREFIX + "*"))


def test_an_interrupted_export_leaves_no_archive(tmp_path, monkeypatch):
    lib = new_library(tmp_path / "data")
    build(lib)
    real = exports._write_jsonl

    def failing(c, table):
        if table.name == "samples":
            raise OSError("disk full (simulated)")
        return real(c, table)
    monkeypatch.setattr(exports, "_write_jsonl", failing)
    with pytest.raises(OSError):
        exports.build(lib, "archive")
    assert exports.list_exports(lib) == []
    assert list(lib.paths["exports"].iterdir()) == []


# ---------------------------------------------------------------- restore refusals: nothing changes

def test_restore_refuses_a_library_that_is_not_empty(source):
    lib, _, arch = source
    before = dump(lib)
    with pytest.raises(restore.RestoreError, match="empty library"):
        restore.restore(lib, arch)
    assert dump(lib) == before


@pytest.mark.parametrize("case", ["flipped byte in samples", "flipped byte in an original", "missing manifest",
                                  "unlisted file", "missing file", "schema mismatch", "derived export",
                                  "row count", "recompute", "truncated", "not a zip"])
def test_restore_refuses_damaged_or_mismatched_archives_and_leaves_the_install_empty(source, tmp_path, case):
    _, _, arch = source
    bad = tmp_path / "bad.zip"

    def flip(target):
        def edit(name, data):
            return data[:-5] + bytes([data[-5] ^ 0x01]) + data[-4:] if name == target else data
        return edit

    if case == "flipped byte in samples":
        rewrite(arch, bad, flip("data/json/samples.jsonl"))
    elif case == "flipped byte in an original":
        rewrite(arch, bad, flip("originals/fenix8.fit"))
    elif case == "missing manifest":
        rewrite(arch, bad, lambda n, d: None if n == "manifest.json" else d)
    elif case == "unlisted file":
        rewrite(arch, bad, lambda n, d: d)
        with zipfile.ZipFile(bad, "a") as z:
            z.writestr("extra.txt", b"x")
    elif case == "missing file":
        rewrite(arch, bad, lambda n, d: None if n == "data/csv/rides.csv" else d)
    elif case == "schema mismatch":
        rewrite(arch, bad, manifest_edit(lambda m: m.update(schema_version="0003")))
    elif case == "derived export":
        rewrite(arch, bad, manifest_edit(lambda m: m.update(kind="derived")))
    elif case == "row count":
        rewrite(arch, bad, manifest_edit(lambda m: m["row_counts"].update(samples=m["row_counts"]["samples"] + 1)))
    elif case == "recompute":
        # A metric value changed and the manifest hash updated to match: only recomputation can catch it.
        state = {}

        def edit(name, data):
            if name == "data/json/metric_values.jsonl":
                lines = data.decode().splitlines()
                for i, line in enumerate(lines):
                    v = json.loads(line)
                    if v["state"] == "valid":
                        v["numeric_value"] += 1.0
                        lines[i] = json.dumps(v)
                        break
                data = ("\n".join(lines) + "\n").encode()
                state["sha"], state["n"] = hashlib.sha256(data).hexdigest(), len(data)
                return data
            return data
        rewrite(arch, bad, edit)
        rewrite(bad, tmp_path / "bad2.zip", manifest_edit(
            lambda m: m["files"]["data/json/metric_values.jsonl"].update(sha256=state["sha"], bytes=state["n"])))
        bad = tmp_path / "bad2.zip"
    elif case == "truncated":
        bad.write_bytes(arch.read_bytes()[: arch.stat().st_size // 2])
    elif case == "not a zip":
        bad.write_bytes(b"not a zip at all")
    target = fresh(tmp_path)
    with pytest.raises(restore.RestoreError):
        restore.restore(target, bad)
    assert_empty(target)
    # The same install then restores the good archive.
    restore.restore(target, arch)
    assert len(dump(target)["activities"]) == 9


def test_a_failure_after_vault_writes_removes_the_written_objects(source, tmp_path, monkeypatch):
    _, _, arch = source
    target = fresh(tmp_path)

    def power_cut(lib, zf, man):
        assert lib.vault.objects()                       # objects were written before the database step
        raise OSError("power cut (simulated)")
    monkeypatch.setattr(restore, "_insert_all", power_cut)
    with pytest.raises(OSError):
        restore.restore(target, arch)
    assert_empty(target)


def test_restore_refuses_a_conflicting_metric_definition(source, tmp_path):
    _, _, arch = source
    bad = rewrite(arch, tmp_path / "bad.zip", lambda n, d: d)
    target = fresh(tmp_path)
    from sqlalchemy import update
    from backend.storage.schema import metric_definitions
    with target.engine.begin() as c:
        c.execute(update(metric_definitions).where(metric_definitions.c.metric_id == "M002").values(units="kW"))
    with pytest.raises(restore.RestoreError, match="M002"):
        restore.restore(target, bad)
    assert_empty(target)


def test_export_and_restore_run_with_networking_blocked(source, tmp_path):
    # conftest blocks every non loopback connection for the whole suite (acceptance 16); this test
    # exists so the evidence names export and restore explicitly.
    lib, _, arch = source
    import socket
    with pytest.raises(RuntimeError, match="outbound"):
        socket.create_connection(("192.0.2.1", 80), timeout=0.1)
    restore.restore(fresh(tmp_path), arch)
