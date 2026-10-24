"""Deletion (spec 8.4, acceptance 15, conflict C26).

Deleting a recording removes its source file row, activity, samples, channels,
timer events and segments, its activity and single ride metric runs and
values, and its vault object. Any ride or group that referred to it changes as
spec 8.4 says:

* it leaves every duplicate group, and the stored evidence pairs that name it
  go with it;
* in a confirmed ride, each field that used it becomes unselected and the
  ride is flagged for review; the ride's metric runs are recomputed from the
  remaining selection (a ride with no timer source has none until the rider
  chooses one);
* a group left with fewer than two members dissolves: the remaining
  recording is a single activity ride again, and the group, its ride and the
  ride's runs and history are removed;
* selection history rows that named it keep the fact that a source was
  chosen (`source_deleted`) but not which file; decision events that named it
  are removed, and the ids it appears under in other events are replaced by
  "deleted".

No other member is altered. Ride scope runs are deleted rather than kept,
because their input revision was computed over the deleted recording. Nothing
keeps the deleted file's hash, filename or timestamps (no tombstone).

Order: one database transaction, then the vault object and any export that
contains the file, then a WAL truncate. If the process stops after the commit,
`maintenance.recover` removes the orphaned object and partial files on the
next open. A preview runs the same transaction and rolls it back, so what the
rider confirms is exactly what will happen.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy import Connection, delete, func, select, update

from ..storage.maintenance import checkpoint
from ..storage.schema import (activities, duplicate_group_events, duplicate_group_members, duplicate_groups,
                              metric_runs, ride_channel_sources, ride_selection_history, rides, source_files)
from . import Library, exports
from .rides import _apply_selection, group_ride_id, members, single_ride_id, sources, store_ride_metrics

DELETED = "deleted"


class DeletionError(LookupError):
    pass


@dataclass
class GroupEffect:
    group_id: int
    status: str
    effect: str                                  # "member removed" | "dissolved"
    ride_id: Optional[int] = None
    fields_unselected: list[str] = field(default_factory=list)
    remaining_members: list[int] = field(default_factory=list)


@dataclass
class DeletionReport:
    source_file_id: int
    activity_id: Optional[int]
    original_filename: Optional[str]
    groups: list[GroupEffect] = field(default_factory=list)
    rides_needing_review: list[int] = field(default_factory=list)
    exports_removed: list[str] = field(default_factory=list)
    vault_object_removed: bool = False
    checkpoint: tuple = ()
    committed: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- database part

def _delete_ride_runs(c: Connection, ride_id: int) -> None:
    c.execute(delete(metric_runs).where(metric_runs.c.scope_type == "ride", metric_runs.c.scope_id == ride_id))


def _scrub_history(c: Connection, aid: int) -> None:
    c.execute(update(ride_selection_history).where(ride_selection_history.c.activity_id == aid)
              .values(activity_id=None, source_deleted=True))


def _scrub_events(c: Connection, gid: int, aid: int) -> None:
    c.execute(delete(duplicate_group_events).where(duplicate_group_events.c.group_id == gid,
                                                   duplicate_group_events.c.activity_id == aid))
    for eid, doc in c.execute(select(duplicate_group_events.c.id, duplicate_group_events.c.detail_json)
                              .where(duplicate_group_events.c.group_id == gid,
                                     duplicate_group_events.c.detail_json.is_not(None))).all():
        d = json.loads(doc)
        changed = False
        if isinstance(d.get("selection"), dict):
            for k, v in d["selection"].items():
                if v == aid:
                    d["selection"][k], changed = DELETED, True
        for key in ("excluded", "candidates"):
            if isinstance(d.get(key), list) and aid in d[key]:
                d[key], changed = [DELETED if x == aid else x for x in d[key]], True
        if changed:
            c.execute(update(duplicate_group_events).where(duplicate_group_events.c.id == eid)
                      .values(detail_json=json.dumps(d, sort_keys=True)))


def _prune_evidence(c: Connection, gid: int, aid: int) -> None:
    doc = c.execute(select(duplicate_groups.c.overlap_json).where(duplicate_groups.c.id == gid)).scalar()
    if not doc:
        return
    d = json.loads(doc)
    d["pairs"] = [p for p in d.get("pairs", []) if aid not in p.get("activity_ids", [])]
    c.execute(update(duplicate_groups).where(duplicate_groups.c.id == gid).values(overlap_json=json.dumps(d, sort_keys=True)))


def _leave_group(c: Connection, gid: int, aid: int, now: float) -> GroupEffect:
    g = c.execute(select(duplicate_groups).where(duplicate_groups.c.id == gid)).mappings().one()
    ride_id = group_ride_id(c, gid)
    eff = GroupEffect(gid, g["status"], "member removed", ride_id)
    _scrub_events(c, gid, aid)
    _prune_evidence(c, gid, aid)
    c.execute(delete(duplicate_group_members).where(duplicate_group_members.c.group_id == gid,
                                                    duplicate_group_members.c.activity_id == aid))
    remaining = members(c, gid, "member")
    eff.remaining_members = remaining
    if ride_id is not None:
        _delete_ride_runs(c, ride_id)    # computed over a composition that included the deleted recording
    if len(remaining) < 2:
        eff.effect = "dissolved"
        if g["status"] == "confirmed":
            c.execute(update(rides).where(rides.c.activity_id.in_(remaining)).values(active=True))
        if ride_id is not None:
            c.execute(delete(rides).where(rides.c.id == ride_id))      # cascades sources and history
        c.execute(delete(duplicate_groups).where(duplicate_groups.c.id == gid))   # cascades members and events
        return eff
    if ride_id is None:
        return eff
    _scrub_history(c, aid)
    if not c.execute(select(rides.c.active).where(rides.c.id == ride_id)).scalar_one():
        return eff        # a reopened group: its old selection is replaced when it is confirmed again
    src = sources(c, ride_id)
    eff.fields_unselected = [f for f, a in src.items() if a == aid]
    if eff.fields_unselected:
        _apply_selection(c, ride_id, {f: (None if a == aid else a) for f, a in src.items()}, now, "deletion")
        c.execute(update(rides).where(rides.c.id == ride_id).values(needs_review=True))
    else:
        store_ride_metrics(c, ride_id, now)
    return eff


def _delete_in_db(c: Connection, sf_id: int, now: float) -> tuple[DeletionReport, str]:
    sf = c.execute(select(source_files).where(source_files.c.id == sf_id)).mappings().first()
    if sf is None:
        raise DeletionError(f"source file {sf_id} does not exist")
    aid = c.execute(select(activities.c.id).where(activities.c.source_file_id == sf_id)).scalar()
    rep = DeletionReport(sf_id, aid, sf["original_filename"])
    if aid is not None:
        gids = [r[0] for r in c.execute(select(duplicate_group_members.c.group_id)
                                        .where(duplicate_group_members.c.activity_id == aid)
                                        .order_by(duplicate_group_members.c.group_id))]
        for gid in gids:
            rep.groups.append(_leave_group(c, gid, aid, now))
        _delete_ride_runs(c, single_ride_id(c, aid))
        _scrub_history(c, aid)
        c.execute(delete(metric_runs).where(metric_runs.c.scope_type == "activity", metric_runs.c.scope_id == aid))
        # Safety net: no remaining run may name the deleted file.
        stray = c.execute(select(func.count()).select_from(metric_runs)
                          .where(metric_runs.c.provenance_json.contains(sf["sha256"]))).scalar()
        if stray:
            raise RuntimeError(f"{stray} metric runs still reference the deleted file")
        c.execute(update(ride_channel_sources).where(ride_channel_sources.c.activity_id == aid).values(activity_id=None))
        c.execute(delete(activities).where(activities.c.id == aid))   # cascades samples, channels, events, segments, single ride
        rep.rides_needing_review = [e.ride_id for e in rep.groups if e.fields_unselected]
    c.execute(delete(source_files).where(source_files.c.id == sf_id))
    return rep, sf["sha256"]


# ---------------------------------------------------------------- public

def _source_file_for_activity(lib: Library, aid: int) -> int:
    with lib.engine.connect() as c:
        sf = c.execute(select(activities.c.source_file_id).where(activities.c.id == aid)).scalar()
    if sf is None:
        raise DeletionError(f"activity {aid} does not exist")
    return sf


def preview(lib: Library, sf_id: int) -> DeletionReport:
    """What deleting this file would do, computed by the real transaction and rolled back."""
    with lib.engine.connect() as c:
        tx = c.begin()
        try:
            rep, sha = _delete_in_db(c, sf_id, lib.now())
        finally:
            tx.rollback()
    rep.exports_removed = exports.containing(lib, sha)
    rep.vault_object_removed = True
    return rep


def delete_source_file(lib: Library, sf_id: int) -> DeletionReport:
    with lib.engine.begin() as c:
        rep, sha = _delete_in_db(c, sf_id, lib.now())
    rep.committed = True
    _remove_files(lib, sha, rep)
    return rep


def _remove_files(lib: Library, sha: str, rep: DeletionReport) -> None:
    lib.vault.delete(sha)
    rep.vault_object_removed = True
    rep.exports_removed = exports.remove_containing(lib, sha)
    rep.checkpoint = checkpoint(lib.engine)


def preview_activity(lib: Library, aid: int) -> DeletionReport:
    return preview(lib, _source_file_for_activity(lib, aid))


def delete_activity(lib: Library, aid: int) -> DeletionReport:
    return delete_source_file(lib, _source_file_for_activity(lib, aid))


# ---------------------------------------------------------------- delete everything

APP_ENTRIES = ("vault", "db", "exports", "backups", "logs")
CANNOT_DELETE = [   # spec 8.4, last item
    "Copies outside the data root: exports you downloaded or moved, and anything you copied yourself.",
    "Time Machine backups and APFS local snapshots that already hold the data.",
    "Physical blocks on the SSD: deleted files are unlinked and database pages overwritten, but the drive's "
    "wear levelling may keep old blocks until it reuses them. FileVault encryption protects them at rest.",
    "Recordings held by vendor accounts such as Garmin Connect, Wattbike or MyWhoosh.",
]


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def everything_preview(lib: Library) -> dict:
    """What "delete everything" removes, with a token that only matches this exact state."""
    with lib.engine.connect() as c:
        counts = {"recordings": c.execute(select(func.count()).select_from(source_files)).scalar(),
                  "activities": c.execute(select(func.count()).select_from(activities)).scalar(),
                  "duplicate_groups": c.execute(select(func.count()).select_from(duplicate_groups)).scalar()}
    entries = [{"path": str(lib.root / e), "bytes": _size(lib.root / e)} for e in APP_ENTRIES if (lib.root / e).exists()]
    other = sorted(p.name for p in lib.root.iterdir() if p.name not in APP_ENTRIES) if lib.root.exists() else []
    doc = {"data_root": str(lib.root), "counts": counts, "entries": entries,
           "exports": [e["name"] for e in exports.list_exports(lib)], "kept_not_ours": other}
    doc["token"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:20]
    doc["cannot_delete"] = CANNOT_DELETE
    return doc


def _make_writable(func_, path, _exc):
    Path(path).parent.chmod(stat.S_IRWXU)
    Path(path).chmod(stat.S_IRWXU)
    func_(path)


def delete_everything(lib: Library, token: str) -> dict:
    """Remove the database, vault, exports, backups and logs, then start an empty install.

    Only folders the app creates are removed. Anything else the rider put in a
    custom data root is listed in the preview and left alone.
    """
    before = everything_preview(lib)
    if token != before["token"]:
        raise DeletionError("the library changed since the confirmation was shown; review it again")
    lib.engine.dispose()
    for e in APP_ENTRIES:
        p = lib.root / e
        if p.exists():
            shutil.rmtree(p, onexc=_make_writable)
    if lib.root.exists() and not any(lib.root.iterdir()):
        lib.root.rmdir()
    lib.reopen()
    return {"removed": before["entries"], "counts": before["counts"], "kept_not_ours": before["kept_not_ours"]}
