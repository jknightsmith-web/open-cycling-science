"""Possible duplicate rides (spec 5.7, decision D7).

Two activities with different bytes are proposed as recordings of the same
ride when either

* their timer running segments overlap by at least 80% of the shorter
  activity's timer time (spec 5.7, rule 1.0), or
* they carry the same recording identity (FIT file_id manufacturer, product,
  serial number and creation time; TCX creator and activity Id), which a
  re-export of one recording keeps even when its bytes change (rule 1.1, added
  at Jimmy's request on 2026-10-24).

The evidence for every pair (overlap, start offset, timer durations, recording
identity, device identity) is stored with the group so the rider can judge it.
A proposal changes no ride, no aggregate and no recording.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import Connection, and_, insert, or_, select, update

from ..storage.schema import activities, duplicate_group_events, duplicate_group_members, duplicate_groups, timer_segments

OVERLAP_THRESHOLD = 0.8   # engineering parameter, spec 5.7
RULE_VERSION = "1.1"
RULE = {"version": RULE_VERSION, "overlap_threshold": OVERLAP_THRESHOLD,
        "criteria": ["timer_overlap_fraction >= overlap_threshold", "same_recording_identity"]}


def _segments(c: Connection, aid: int) -> list[tuple[float, float]]:
    return [tuple(r) for r in c.execute(
        select(timer_segments.c.start_utc, timer_segments.c.end_utc)
        .where(timer_segments.c.activity_id == aid).order_by(timer_segments.c.start_utc))]


def overlap_s(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _device(row) -> Optional[dict]:
    dev = json.loads(row["device_identity_json"] or "{}").get("device") or {}
    return dev if any(v is not None for v in dev.values()) else None


def evidence(c: Connection, a, b) -> dict:
    sa, sb = _segments(c, a["id"]), _segments(c, b["id"])
    ov = overlap_s(sa, sb)
    ta, tb = a["timer_s"] or 0.0, b["timer_s"] or 0.0
    shorter = min(ta, tb)
    da, db = _device(a), _device(b)
    return {
        "activity_ids": [a["id"], b["id"]],
        "overlap_s": ov,
        "overlap_fraction": ov / shorter if shorter > 0 else 0.0,
        "start_offset_s": (b["start_utc"] - a["start_utc"]) if a["start_utc"] is not None and b["start_utc"] is not None else None,
        "timer_s": [ta, tb],
        "duration_ratio": shorter / max(ta, tb) if max(ta, tb) > 0 else None,
        "same_recording_identity": a["original_activity_id"] is not None
        and a["original_activity_id"] == b["original_activity_id"],
        "same_device": da is not None and da == db,
        "source_platforms": [a["source_platform"], b["source_platform"]],
    }


def is_candidate(ev: dict) -> bool:
    return ev["overlap_fraction"] >= OVERLAP_THRESHOLD or ev["same_recording_identity"]


def candidates(c: Connection, aid: int) -> list[dict]:
    a = c.execute(select(activities).where(activities.c.id == aid)).mappings().one()
    conds = []
    if a["start_utc"] is not None and a["end_utc"] is not None:
        conds.append(and_(activities.c.start_utc < a["end_utc"], activities.c.end_utc > a["start_utc"]))
    if a["original_activity_id"] is not None:
        conds.append(activities.c.original_activity_id == a["original_activity_id"])
    if not conds:
        return []
    rows = c.execute(select(activities).where(activities.c.id != aid, or_(*conds))
                     .order_by(activities.c.id)).mappings().all()
    return [ev for ev in (evidence(c, a, b) for b in rows) if is_candidate(ev)]


def log_event(c: Connection, gid: int, action: str, now: float, actor: str = "rider",
              activity_id: Optional[int] = None, detail: Optional[dict] = None) -> None:
    c.execute(insert(duplicate_group_events).values(
        group_id=gid, action=action, activity_id=activity_id, at_utc=now, actor=actor,
        detail_json=json.dumps(detail, sort_keys=True) if detail is not None else None))


def _open_groups(c: Connection, aids: list[int]) -> list[dict]:
    return c.execute(
        select(duplicate_group_members.c.group_id, duplicate_group_members.c.activity_id,
               duplicate_group_members.c.membership, duplicate_groups.c.status)
        .join(duplicate_groups, duplicate_groups.c.id == duplicate_group_members.c.group_id)
        .where(duplicate_group_members.c.activity_id.in_(aids),
               duplicate_groups.c.status.in_(("proposed", "confirmed")),
               duplicate_group_members.c.membership != "excluded")).mappings().all()


def _add_evidence(c: Connection, gid: int, pairs: list[dict]) -> None:
    row = c.execute(select(duplicate_groups.c.overlap_json).where(duplicate_groups.c.id == gid)).scalar()
    doc = json.loads(row) if row else {"rule": RULE, "pairs": []}
    doc["pairs"].extend(pairs)
    c.execute(update(duplicate_groups).where(duplicate_groups.c.id == gid).values(overlap_json=json.dumps(doc, sort_keys=True)))


def propose_for(c: Connection, aid: int, now: float) -> Optional[int]:
    """Propose a group for a newly imported activity. Returns the group id, or None.

    * A candidate already in a confirmed group: the new activity joins that
      group as `pending`; the confirmed ride is unchanged until the rider accepts it.
    * Else a candidate already in a proposed group: the new activity joins it.
    * Else a new proposed group holds the activity and all its candidates.
    """
    pairs = candidates(c, aid)
    if not pairs:
        return None
    cand_ids = [p["activity_ids"][1] for p in pairs]
    memberships = _open_groups(c, cand_ids)
    confirmed = sorted({m["group_id"] for m in memberships if m["status"] == "confirmed" and m["membership"] == "member"})
    proposed = sorted({m["group_id"] for m in memberships if m["status"] == "proposed"})
    if confirmed:
        gid, membership = confirmed[0], "pending"
    elif proposed:
        gid, membership = proposed[0], "member"
    else:
        gid = c.execute(insert(duplicate_groups).values(
            proposed_at_utc=now, rule_version=RULE_VERSION, status="proposed",
            overlap_json=json.dumps({"rule": RULE, "pairs": []}))).inserted_primary_key[0]
        membership = "member"
        c.execute(insert(duplicate_group_members), [
            {"group_id": gid, "activity_id": b, "membership": "member", "added_at_utc": now} for b in cand_ids])
    c.execute(insert(duplicate_group_members).values(group_id=gid, activity_id=aid, membership=membership,
                                                      added_at_utc=now))
    _add_evidence(c, gid, pairs)
    log_event(c, gid, "proposed" if membership == "member" else "pending_added", now, actor="system",
              activity_id=aid, detail={"candidates": cand_ids})
    return gid
