"""Restore a full archive into an empty install (spec 8.3, acceptance 14).

Checks before anything is written, any failure stops with nothing changed:

1. The ZIP is an `archive` export with a readable manifest, and its member
   list is exactly the manifest's file list.
2. Every member's size and SHA256 match the manifest.
3. The archive's schema revision equals this install's.
4. This install is empty: no recordings, activities, groups or rides, and no
   vault objects.
5. Every original's SHA256 equals its `source_files` row, and the originals
   and the rows describe the same set of files.
6. Metric definitions present in both the archive and this install agree.
7. Each activity is recomputed from its original bytes with this install's
   parser and metric code, and must reproduce the archived input revision and
   latest activity metric values and states exactly. If the archive was made by
   a different computation version, this check is reported as skipped.

Then the vault objects are written and every table is inserted with its
original ids in one transaction, with row counts checked against the
manifest before commit. If anything fails, the transaction rolls back and
the objects written are removed, so the install stays empty; an interrupted
process leaves only unreferenced objects, which `maintenance.recover` removes
on the next open.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from sqlalchemy import func, insert, select

from ..canonical.digest import timeline_digest
from ..canonical.timeline import build_timeline
from ..importers.errors import ImportFailure
from ..storage.maintenance import checkpoint, schema_revision
from ..storage.schema import (activities, app_settings, channel_preferences, duplicate_groups, metric_definitions,
                              rides, source_files)
from ..storage.vault import CHUNK, sha256_bytes
from . import Library
from .exports import FORMAT, FORMAT_VERSION, TABLES
from .ingest import PARSERS
from .metric_store import COMPUTATION_VERSION, compute_activity_metrics

BATCH = 5000
CONFIG_TABLES = (metric_definitions, app_settings, channel_preferences)   # present in a new install; replaced


class RestoreError(ValueError):
    pass


def _jsonl(zf: zipfile.ZipFile, name: str) -> Iterator[dict]:
    with zf.open(name) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _manifest(zf: zipfile.ZipFile) -> dict:
    try:
        man = json.loads(zf.read("manifest.json"))
    except KeyError:
        raise RestoreError("not an export: manifest.json is missing") from None
    except json.JSONDecodeError as exc:
        raise RestoreError(f"manifest.json is not valid JSON: {exc}") from None
    if man.get("format") != FORMAT or man.get("format_version") != FORMAT_VERSION:
        raise RestoreError("not an Open Cycling Science export of a supported format version")
    if man.get("kind") != "archive":
        raise RestoreError(f"this is a {man.get('kind')} export; only a full archive can be restored")
    return man


def _check_members(zf: zipfile.ZipFile, man: dict) -> None:
    listed = set(man["files"])
    present = {i.filename for i in zf.infolist() if not i.is_dir()} - {"manifest.json"}
    if present != listed:
        extra, missing = sorted(present - listed), sorted(listed - present)
        raise RestoreError(f"archive contents differ from its manifest (unlisted {extra[:5]}, missing {missing[:5]})")
    for name, meta in man["files"].items():
        info = zf.getinfo(name)
        if info.file_size != meta["bytes"]:      # also bounds what is decompressed
            raise RestoreError(f"{name}: size {info.file_size} differs from the manifest's {meta['bytes']}")
        h = hashlib.sha256()
        with zf.open(info) as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                h.update(chunk)
        if h.hexdigest() != meta["sha256"]:
            raise RestoreError(f"{name}: SHA256 does not match the manifest; the archive is damaged")


def _check_empty(lib: Library) -> None:
    with lib.engine.connect() as c:
        used = {t.name: c.execute(select(func.count()).select_from(t)).scalar()
                for t in (source_files, activities, duplicate_groups, rides)}
    if any(used.values()) or lib.vault.objects():
        raise RestoreError("an archive can only be restored into an empty library; this one holds "
                           + ", ".join(f"{n} {k}" for k, n in used.items() if n) + " (use Delete everything first)")


def _recompute(zf: zipfile.ZipFile, man: dict, sf_rows: dict[int, dict], originals: dict[str, str]) -> dict:
    if man["computation_version"] != COMPUTATION_VERSION:
        return {"status": "skipped", "reason": f"archive computed by {man['computation_version']}, "
                                               f"this install is {COMPUTATION_VERSION}"}
    acts = {a["id"]: a for a in _jsonl(zf, "data/json/activities.jsonl")}
    values = {v["run_id"]: v for v in _jsonl(zf, "data/json/metric_values.jsonl")}
    newest: dict[int, dict[tuple, dict]] = defaultdict(dict)
    for r in _jsonl(zf, "data/json/metric_runs.jsonl"):
        if r["scope_type"] != "activity":
            continue
        key = (r["metric_id"], r["parameter_json"])
        if key not in newest[r["scope_id"]] or r["id"] > newest[r["scope_id"]][key]["id"]:
            newest[r["scope_id"]][key] = r
    mismatches = []
    for aid, a in acts.items():
        sf = sf_rows[a["source_file_id"]]
        data = zf.read(originals[sf["sha256"]])
        try:
            tl = build_timeline(PARSERS[sf["media_format"]][0](data))
        except ImportFailure as exc:
            mismatches.append({"activity_id": aid, "problem": f"original no longer parses: {exc.code}"})
            continue
        digest = timeline_digest(tl)
        for res in compute_activity_metrics(tl):
            run = newest[aid].get((res.metric_id, json.dumps(res.parameters, sort_keys=True, default=str)))
            v = values.get(run["id"]) if run else None
            if run is None or v is None:
                mismatches.append({"activity_id": aid, "metric_id": res.metric_id, "problem": "no archived run"})
            elif run["input_revision"] != digest or v["numeric_value"] != res.value or v["state"] != res.state:
                mismatches.append({"activity_id": aid, "metric_id": res.metric_id, "parameters": res.parameters,
                                   "archived": [v["numeric_value"], v["state"]], "recomputed": [res.value, res.state]})
    if mismatches:
        raise RestoreError(f"recomputing from the originals does not reproduce the archive: {mismatches[:3]}")
    return {"status": "passed", "activities": len(acts)}


def restore(lib: Library, archive: Path) -> dict:
    try:
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        raise RestoreError(f"not a readable ZIP: {exc}") from None
    with zf:
        man = _manifest(zf)
        _check_members(zf, man)
        here = schema_revision(lib.engine)
        if man["schema_version"] != here:
            raise RestoreError(f"archive schema revision {man['schema_version']} differs from this install's {here}")
        _check_empty(lib)
        sf_rows = {r["id"]: r for r in _jsonl(zf, "data/json/source_files.jsonl")}
        originals = {o["sha256"]: o["path"] for o in man["originals"]}
        for o in man["originals"]:
            if man["files"][o["path"]]["sha256"] != o["sha256"]:
                raise RestoreError(f"{o['path']}: content does not match its recorded SHA256")
        if set(originals) != {r["sha256"] for r in sf_rows.values()}:
            raise RestoreError("originals and source file rows describe different files")
        with lib.engine.connect() as c:
            ours = {(r.metric_id, r.version): dict(r._mapping) for r in c.execute(select(metric_definitions))}
        for d in _jsonl(zf, "data/json/metric_definitions.jsonl"):
            mine = ours.get((d["metric_id"], d["version"]))
            if mine is not None and mine != d:
                raise RestoreError(f"metric definition {d['metric_id']} v{d['version']} differs from this install's register")
        recompute = _recompute(zf, man, sf_rows, originals)

        written: list[str] = []
        try:
            for sha, path in originals.items():
                data = zf.read(path)
                if sha256_bytes(data) != sha:
                    raise RestoreError(f"{path}: content changed while restoring")
                digest, created = lib.vault.put(data)
                if created:
                    written.append(digest)
            counts = _insert_all(lib, zf, man)
        except BaseException:
            for digest in written:
                lib.vault.delete(digest)
            raise
    return {"restored_rows": counts, "vault_objects": len(originals), "recompute_check": recompute,
            "archive_created_at_utc": man["created_at_utc"], "app_version": man["app_version"],
            "checkpoint": checkpoint(lib.engine)}


def _insert_all(lib: Library, zf: zipfile.ZipFile, man: dict) -> dict:
    counts = {}
    with lib.engine.begin() as c:
        for t in CONFIG_TABLES:
            c.execute(t.delete())
        for t in TABLES:
            n, batch = 0, []
            for row in _jsonl(zf, f"data/json/{t.name}.jsonl"):
                batch.append(row)
                n += 1
                if len(batch) >= BATCH:
                    c.execute(insert(t), batch)
                    batch = []
            if batch:
                c.execute(insert(t), batch)
            in_db = c.execute(select(func.count()).select_from(t)).scalar()
            if n != man["row_counts"][t.name] or in_db != n:
                raise RestoreError(f"{t.name}: manifest says {man['row_counts'][t.name]} rows, archive holds {n}, "
                                   f"database has {in_db}")
            counts[t.name] = n
    return counts
