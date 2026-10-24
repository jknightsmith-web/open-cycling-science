"""WP9 interrupted operations. Each case kills a real process at a chosen point with
os._exit (no cleanup runs), then opens the library again and checks that it is
consistent, that nothing of a deleted file survives, and that the operation can
be repeated. Synthetic data only.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from backend.library import Library, deletion, exports, restore
from backend.storage.maintenance import PARTIAL_PREFIX
from crash_runner import CRASH
from fit_encoder import activity_file
from ownership_helpers import MARKER, build, dump, needles_for, new_library, scan

RUNNER = Path(__file__).with_name("crash_runner.py")


def crash(op: str, root: Path, arg=None) -> None:
    cmd = [sys.executable, str(RUNNER), op, str(root)] + ([str(arg)] if arg is not None else [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert p.returncode == CRASH, p.stdout + p.stderr


@pytest.fixture
def built(tmp_path):
    lib = new_library(tmp_path / "data")
    ids = build(lib)
    lib.engine.dispose()
    return tmp_path / "data", ids


def test_deletion_interrupted_after_commit_is_finished_on_the_next_open(built):
    root, ids = built
    lib = Library(root)
    sha = next(r["sha256"] for r in dump(lib)["source_files"] if r["original_filename"].startswith(MARKER))
    old = exports.build(lib, "archive")["name"]
    lib.engine.dispose()
    crash("delete-after-commit", root, ids["gps"])
    assert any(sha in str(p) for p in (root / "vault").rglob("*"))      # the orphan is still there
    assert (root / "exports" / old).exists()                            # and the export holding it
    lib = Library(root)                                                  # opening recovers
    assert lib.recovery.orphan_objects == 1 and lib.recovery.stale_exports == [old]
    assert scan(root, needles_for(sha, MARKER)) == []
    assert len(dump(lib)["activities"]) == 8


def test_export_interrupted_mid_write_leaves_only_a_partial_file_that_is_removed(built):
    root, _ = built
    crash("export-mid-write", root)
    partials = list((root / "exports").glob(PARTIAL_PREFIX + "*"))
    assert len(partials) == 1
    lib = Library(root)
    assert exports.list_exports(lib) == []
    assert not list((root / "exports").glob(PARTIAL_PREFIX + "*"))
    assert exports.build(lib, "archive")["readable"]


@pytest.mark.parametrize("point", ["restore-before-commit", "restore-mid-insert"])
def test_restore_interrupted_leaves_an_empty_install_that_restores_on_retry(built, tmp_path, point):
    root, _ = built
    arch = Path(exports.build(Library(root), "archive")["path"])
    target = tmp_path / "target"
    Library(target).engine.dispose()
    crash(point, target, arch)
    lib = Library(target)
    d = dump(lib)
    assert d["source_files"] == [] and d["activities"] == [] and d["samples"] == []
    assert lib.vault.objects() == []
    report = restore.restore(lib, arch)
    assert report["recompute_check"]["status"] == "passed"
    assert dump(lib) == dump(Library(root))


def test_import_interrupted_after_the_vault_write_leaves_no_orphan(built, tmp_path):
    root, _ = built
    f = tmp_path / "new.fit"
    f.write_bytes(activity_file([{"t": 1_770_000_000 + i, "power": 150} for i in range(120)], file_id={"serial_number": 4}))
    before = Library(root).vault.objects()
    crash("import-after-vault", root, f)
    lib = Library(root)
    assert lib.recovery.orphan_objects == 1 and lib.vault.objects() == before


def test_a_database_left_mid_deletion_by_a_crash_has_all_or_nothing(built):
    # SQLite's transaction is the unit: a crash before commit leaves every row in place.
    root, ids = built
    lib = Library(root)
    before = dump(lib)
    real = deletion._delete_in_db

    def fail(c, sf_id, now):
        real(c, sf_id, now)
        raise KeyboardInterrupt
    deletion._delete_in_db = fail
    try:
        with pytest.raises(KeyboardInterrupt):
            deletion.delete_activity(lib, ids["hub"])
    finally:
        deletion._delete_in_db = real
    assert dump(lib) == before
