"""Housekeeping that keeps the data root consistent after an interruption (spec 8.4).

Every multi step operation commits the database first and touches files
after, so the only possible leftovers are files nothing references: vault
objects without a source file row, temporary vault writes, partial exports and
staged restore uploads. `recover` removes them and truncates the WAL, and runs
whenever a library is opened.
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, select, text

from .schema import source_files
from .vault import Vault

PARTIAL_PREFIX = ".partial-"


@dataclass
class Recovery:
    orphan_objects: int = 0
    temporary_files: int = 0
    stale_exports: list[str] = field(default_factory=list)
    checkpoint: tuple = ()
    removed: list[str] = field(default_factory=list)


def checkpoint(engine: Engine) -> tuple:
    """Copy the WAL into the database and truncate it, so deleted rows leave no copy there.

    Returns SQLite's (busy, wal_frames, checkpointed_frames); busy 0 means complete.
    """
    with engine.connect() as c:
        row = c.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)").one()
        return tuple(row)


def vacuum(engine: Engine) -> None:
    with engine.connect() as c:
        c.exec_driver_sql("VACUUM")


def recover(engine: Engine, vault: Vault, temp_dirs: list[Path], exports_dir: Path | None = None) -> Recovery:
    r = Recovery()
    r.temporary_files += vault.remove_incomplete()
    for d in temp_dirs:
        for f in d.glob(PARTIAL_PREFIX + "*") if d.exists() else []:
            f.unlink()
            r.temporary_files += 1
    with engine.connect() as c:
        known = {row[0] for row in c.execute(select(source_files.c.sha256))}
    for digest in vault.objects():
        if digest not in known:
            vault.delete(digest)
            r.orphan_objects += 1
    # An export may only hold files the library still has: one left by a deletion that stopped
    # before removing it still contains the deleted file.
    for z in sorted(exports_dir.glob("ocs-*.zip")) if exports_dir and exports_dir.exists() else []:
        try:
            with zipfile.ZipFile(z) as zf:
                held = set(json.loads(zf.read("manifest.json")).get("source_sha256", []))
        except (zipfile.BadZipFile, KeyError, ValueError, OSError):
            continue
        if held - known:
            z.unlink()
            r.stale_exports.append(z.name)
    r.checkpoint = checkpoint(engine)
    return r


def schema_revision(engine: Engine) -> str:
    with engine.connect() as c:
        return c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
