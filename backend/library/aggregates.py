"""Aggregates over rides (spec 5.7, architecture 6).

Totals are computed over active rides, so a confirmed duplicate group counts
once and every member of a proposed group counts as its own ride. Because
unconfirmed duplicates can inflate totals, the potential overcount is reported
beside them: for each proposed group, the duration and work of every member
except the earliest, plus every recording pending for an already confirmed
ride. This is the amount that confirmation would remove if the earliest member
stayed the timer and power source; the rider's selection can change it.

Aggregates are computed on request from the stored ride runs, never cached,
so a decision is reflected immediately and nothing can be stale.
A ride falls in a range by the start of its selected timer source.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Connection, select

from ..metrics.m004_mmp import DEFAULT_DURATIONS_S
from ..storage.schema import activities, duplicate_group_members, duplicate_groups, ride_channel_sources, rides
from .metric_store import find, latest

WORK_STATES = ("valid", "lower_bound")


def _ride_rows(c: Connection, start_utc: float, end_utc: float, active_only: bool = True):
    q = (select(rides.c.id, rides.c.kind, rides.c.activity_id, rides.c.group_id, activities.c.start_utc)
         .join(ride_channel_sources, (ride_channel_sources.c.ride_id == rides.c.id)
               & (ride_channel_sources.c.channel == "timer"))
         .join(activities, activities.c.id == ride_channel_sources.c.activity_id)
         .where(activities.c.start_utc >= start_utc, activities.c.start_utc < end_utc))
    if active_only:
        q = q.where(rides.c.active)
    return c.execute(q.order_by(activities.c.start_utc, rides.c.id)).mappings().all()


def _contribution(runs: list[dict]) -> dict:
    m001, m003 = find(runs, "M001"), find(runs, "M003")
    work = m003["value"] if m003 and m003["state"] in WORK_STATES else None
    return {"duration_s": m001["value"] if m001 and m001["value"] is not None else 0.0,
            "work_kj": work, "work_state": m003["state"] if m003 else "not_applicable"}


def totals(c: Connection, start_utc: float, end_utc: float) -> dict:
    ride_rows = _ride_rows(c, start_utc, end_utc)
    runs = latest(c, "ride", [r["id"] for r in ride_rows])
    duration = work = 0.0
    work_states: dict[str, int] = {}
    best: dict[int, Optional[dict]] = dict.fromkeys(DEFAULT_DURATIONS_S)
    for r in ride_rows:
        con = _contribution(runs[r["id"]])
        duration += con["duration_s"]
        work_states[con["work_state"]] = work_states.get(con["work_state"], 0) + 1
        if con["work_kj"] is not None:
            work += con["work_kj"]
        for T in DEFAULT_DURATIONS_S:
            m = find(runs[r["id"]], "M004", duration_s=T)
            if m and m["state"] == "valid" and (best[T] is None or m["value"] > best[T]["value"]):
                best[T] = {"value": m["value"], "ride_id": r["id"], "activity_ids": m["provenance"].get("activity_ids"),
                           "source_sha256": m["provenance"].get("source_sha256"),
                           "window_start_s": m["details"].get("window_start_s")}

    over = _overcount(c, start_utc, end_utc)
    unconfirmed = over["unconfirmed_group_count"] + over["pending_recording_count"]
    return {
        "range_utc": [start_utc, end_utc],
        "ride_count": len(ride_rows),
        "duration_s": duration,
        "work_kj": work,
        # A sum that includes any lower bound is itself a lower bound (spec M003, D1).
        "work_state": "lower_bound" if work_states.get("lower_bound") else "valid",
        "rides_by_work_state": work_states,
        "best_mmp_w": {str(T): v for T, v in best.items()},
        "state": "unconfirmed_duplicates_included" if unconfirmed else "valid",
        "potential_overcount": over,
    }


def _overcount(c: Connection, start_utc: float, end_utc: float) -> dict:
    singles = {r["activity_id"]: r for r in _ride_rows(c, start_utc, end_utc) if r["kind"] == "single"}
    rows = c.execute(select(duplicate_group_members.c.group_id, duplicate_group_members.c.activity_id,
                            duplicate_group_members.c.membership, duplicate_groups.c.status)
                     .join(duplicate_groups, duplicate_groups.c.id == duplicate_group_members.c.group_id)
                     .where(duplicate_groups.c.status.in_(("proposed", "confirmed")),
                            duplicate_group_members.c.membership.in_(("member", "pending")))).mappings().all()
    surplus: list[int] = []      # activity ids whose single ride is the potential overcount
    proposed: dict[int, list[int]] = {}
    pending = 0
    for r in rows:
        if r["status"] == "proposed" and r["membership"] == "member":
            proposed.setdefault(r["group_id"], []).append(r["activity_id"])
        elif r["status"] == "confirmed" and r["membership"] == "pending" and r["activity_id"] in singles:
            surplus.append(r["activity_id"])
            pending += 1
    groups_in_range = 0
    for aids in proposed.values():
        here = sorted((a for a in aids if a in singles), key=lambda a: (singles[a]["start_utc"], a))
        if len(here) >= 2:
            groups_in_range += 1
            surplus.extend(here[1:])
    runs = latest(c, "ride", [singles[a]["id"] for a in surplus])
    duration = work = 0.0
    for a in surplus:
        con = _contribution(runs[singles[a]["id"]])
        duration += con["duration_s"]
        work += con["work_kj"] or 0.0
    return {"unconfirmed_group_count": groups_in_range, "pending_recording_count": pending,
            "ride_count": len(surplus), "duration_s": duration, "work_kj": work,
            "activity_ids": sorted(surplus)}
