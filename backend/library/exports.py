"""Exports (spec 8.3, decision D6; acceptance 14 and 16).

Three kinds, each one ZIP in the data root's `exports/` folder:

* `originals`: every vault object under its original filename, byte identical,
  GPS included (spec 8.2: the interface warns that originals may reveal home).
* `derived`: one CSV per table (UTF-8, RFC 4180, units in column names, empty
  means NULL, validity columns kept, floats written with Python's shortest
  exact representation so nothing is rounded) and the same rows as JSON Lines,
  one JSON object per line, which keeps types exactly. No location: raw field
  copies in the database hold none (`importers.location`).
* `archive`: both, read from one database snapshot, plus the manifest.

Every ZIP carries `manifest.json`: format and app versions, schema revision,
creation time, row counts, the SHA256 and size of every other file in the
ZIP, metric versions, and the SHA256 of every original it holds or describes.
Vault objects are rehashed before they are copied (spec 8.1).

A ZIP is written under a `.partial-` name and renamed when complete, so an
interrupted export leaves nothing that looks finished; `maintenance.recover`
removes the partial file on the next open.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import metadata as _md
from pathlib import Path
from typing import Any, Iterator, Optional

from sqlalchemy import Connection, Table, func, select

from ..storage.maintenance import PARTIAL_PREFIX, schema_revision
from ..storage.schema import metadata, metric_definitions, source_files
from ..storage.vault import CHUNK, VaultIntegrityError
from . import Library
from .metric_store import COMPUTATION_VERSION

FORMAT = "open-cycling-science-export"
FORMAT_VERSION = 1
KINDS = ("originals", "derived", "archive")
TABLES: list[Table] = list(metadata.sorted_tables)   # parents before children, for restore
LOCATION_NOTE = ("Original files are byte identical and may contain GPS positions, including where rides start "
                 "and end. Derived data contains no location.")
_NAME = re.compile(r"^ocs-(originals|derived|archive)-\d{8}T\d{6}Z(-\d+)?\.zip$")

try:
    APP_VERSION = _md.version("open-cycling-science")
except _md.PackageNotFoundError:
    APP_VERSION = "source"


class ExportError(ValueError):
    pass


# ---------------------------------------------------------------- encoding

def csv_cell(v: Any) -> str:
    if v is None:
        return ""                     # empty means missing (NULL); never 0
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)                # shortest string that reads back as the same float
    return str(v)


def rows(c: Connection, table: Table) -> Iterator[dict]:
    order = list(table.primary_key.columns) or list(table.columns)
    for r in c.execute(select(table).order_by(*order)).mappings():
        yield dict(r)


class _Hashing:
    """Wraps a ZIP member stream and hashes everything written to it."""

    def __init__(self, raw):
        self.raw, self.sha, self.bytes = raw, hashlib.sha256(), 0

    def write(self, b: bytes) -> int:
        self.sha.update(b)
        self.bytes += len(b)
        return self.raw.write(b)


def _member(zf: zipfile.ZipFile, name: str, files: dict, write) -> None:
    with zf.open(name, "w", force_zip64=True) as raw:
        h = _Hashing(raw)
        write(h)
    files[name] = {"sha256": h.sha.hexdigest(), "bytes": h.bytes}


def _write_csv(c: Connection, table: Table):
    def go(h: _Hashing) -> None:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\r\n")     # RFC 4180
        w.writerow([col.name for col in table.columns])
        for i, r in enumerate(rows(c, table)):
            w.writerow([csv_cell(r[col.name]) for col in table.columns])
            if i % 2000 == 1999:
                h.write(buf.getvalue().encode("utf-8"))
                buf.seek(0)
                buf.truncate()
        h.write(buf.getvalue().encode("utf-8"))
    return go


def _write_jsonl(c: Connection, table: Table):
    def go(h: _Hashing) -> None:
        for r in rows(c, table):
            h.write((json.dumps(r, allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8"))
    return go


def _safe_name(name: Optional[str], digest: str) -> str:
    base = (name or digest).replace("\\", "/")
    base = "_".join(p for p in base.split("/") if p not in ("", ".", ".."))
    base = "".join(ch for ch in base if ch.isprintable()) or digest
    return base


# ---------------------------------------------------------------- building

def _now_name(lib: Library, kind: str) -> str:
    stamp = datetime.fromtimestamp(lib.now(), timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name, n = f"ocs-{kind}-{stamp}.zip", 1
    while (lib.paths["exports"] / name).exists():
        n += 1
        name = f"ocs-{kind}-{stamp}-{n}.zip"
    return name


def build(lib: Library, kind: str) -> dict:
    """Write one export into exports/ and return its listing entry."""
    if kind not in KINDS:
        raise ExportError(f"kind must be one of {KINDS}")
    out_dir = lib.paths["exports"]
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _now_name(lib, kind)
    partial = out_dir / f"{PARTIAL_PREFIX}{name}"
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            manifest = _write_contents(lib, zf, kind)
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        with open(partial, "rb") as f:
            os.fsync(f.fileno())
        os.replace(partial, out_dir / name)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return _entry(out_dir / name)


@contextmanager
def snapshot(lib: Library):
    """A read transaction: every query inside sees the database as of its first read (SQLite WAL)."""
    with lib.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.exec_driver_sql("BEGIN")
        try:
            yield c
        finally:
            c.exec_driver_sql("COMMIT")


def _write_contents(lib: Library, zf: zipfile.ZipFile, kind: str) -> dict:
    files: dict[str, dict] = {}
    with snapshot(lib) as c:
        counts = {t.name: c.execute(select(func.count()).select_from(t)).scalar() for t in TABLES}
        originals = []
        if kind in ("originals", "archive"):
            used: set[str] = set()
            for sf in c.execute(select(source_files).order_by(source_files.c.id)).mappings():
                fname = _safe_name(sf["original_filename"], sf["sha256"])
                stem, dot, ext = fname.rpartition(".") if "." in fname else (fname, "", "")
                n, candidate = 1, fname
                while candidate.lower() in used:
                    n += 1
                    candidate = f"{stem} ({n}){dot}{ext}" if dot else f"{fname} ({n})"
                used.add(candidate.lower())
                path = f"originals/{candidate}"
                _copy_vault_object(lib, zf, sf["sha256"], path, files)
                originals.append({"path": path, "sha256": sf["sha256"], "source_file_id": sf["id"],
                                  "original_filename": sf["original_filename"]})
        if kind in ("derived", "archive"):
            for t in TABLES:
                _member(zf, f"data/csv/{t.name}.csv", files, _write_csv(c, t))
                _member(zf, f"data/json/{t.name}.jsonl", files, _write_jsonl(c, t))
        shas = [r[0] for r in c.execute(select(source_files.c.sha256).order_by(source_files.c.id))]
        versions = [{"metric_id": r.metric_id, "version": r.version}
                    for r in c.execute(select(metric_definitions.c.metric_id, metric_definitions.c.version)
                                       .order_by(metric_definitions.c.metric_id, metric_definitions.c.version))]
    return {
        "format": FORMAT, "format_version": FORMAT_VERSION, "kind": kind,
        "app_version": APP_VERSION, "computation_version": COMPUTATION_VERSION,
        "schema_version": schema_revision(lib.engine),
        "created_at_utc": lib.now(),
        "row_counts": counts if kind != "originals" else {"source_files": counts["source_files"]},
        "files": files, "metric_versions": versions, "originals": originals, "source_sha256": shas,
        "location": LOCATION_NOTE if kind != "derived" else "Derived data contains no location.",
    }


def _copy_vault_object(lib: Library, zf: zipfile.ZipFile, digest: str, path: str, files: dict) -> None:
    src = lib.vault.path_for(digest)

    def go(h: _Hashing) -> None:
        with open(src, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                h.write(chunk)
    _member(zf, path, files, go)
    if files[path]["sha256"] != digest:   # rehash before export (spec 8.1)
        raise VaultIntegrityError(f"vault object {digest} rehashes to {files[path]['sha256']}; export stopped")


# ---------------------------------------------------------------- listing

def read_manifest(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        return json.loads(zf.read("manifest.json"))


def _entry(path: Path) -> dict:
    try:
        man = read_manifest(path)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        man = {}
    return {"name": path.name, "kind": man.get("kind"), "bytes": path.stat().st_size,
            "created_at_utc": man.get("created_at_utc"), "recordings": len(man.get("source_sha256", [])),
            "path": str(path), "readable": bool(man)}


def list_exports(lib: Library) -> list[dict]:
    d = lib.paths["exports"]
    if not d.exists():
        return []
    return sorted((_entry(p) for p in d.glob("ocs-*.zip") if _NAME.match(p.name)),
                  key=lambda e: (e["created_at_utc"] or 0, e["name"]), reverse=True)


def export_path(lib: Library, name: str) -> Path:
    if not _NAME.match(name):
        raise ExportError("not an export name")
    p = lib.paths["exports"] / name
    if not p.exists():
        raise ExportError(f"{name} does not exist")
    return p


def remove(lib: Library, name: str) -> None:
    export_path(lib, name).unlink()


def containing(lib: Library, digest: str) -> list[str]:
    """Exports in the data root that hold or describe this original. Unreadable ZIPs count, to be safe."""
    out = []
    for e in list_exports(lib):
        p = lib.paths["exports"] / e["name"]
        try:
            hit = digest in read_manifest(p).get("source_sha256", [])
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
            hit = digest.encode() in p.read_bytes()
        if hit:
            out.append(e["name"])
    return out


def remove_containing(lib: Library, digest: str) -> list[str]:
    names = containing(lib, digest)
    for n in names:
        (lib.paths["exports"] / n).unlink()
    return names
