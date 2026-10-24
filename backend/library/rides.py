"""Rides, rider decisions on duplicate groups and per channel source selection (spec 5.7, 5.8).

A ride is a single activity or a confirmed duplicate group. Every activity has
a single ride row; it is inactive while the activity is a member of a
confirmed group, whose group ride is active instead. Rows are never deleted by
decisions, so ride ids are stable and every decision is reversible.

Ride level metrics follow spec 5.8 and C25: M001 comes from the selected
`timer` source, M002 to M004 from the selected `power` source with that file's
own timer and coverage. Nothing is spliced across files, so ride values are
the selected activities' values, recorded as new ride scope runs whose input
revision covers the ride composition and the selection revision.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from sqlalchemy import Connection, delete, insert, select, update

from ..metrics.result import NO_POWER, MetricResult
from ..storage.schema import (SELECTABLE_FIELDS, activities, activity_channels, channel_preferences,
                              duplicate_group_members, duplicate_groups, ride_channel_sources,
                              ride_selection_history, rides)
from .duplicates import log_event
from .metric_store import insert_run, latest

POWER_METRICS = ("M002", "M003", "M004")


class DecisionError(ValueError):
    """A rider action that the current state does not allow. Nothing was changed."""


# ---------------------------------------------------------------- queries

def single_ride_id(c: Connection, aid: int) -> int:
    return c.execute(select(rides.c.id).where(rides.c.activity_id == aid)).scalar_one()


def group_ride_id(c: Connection, gid: int) -> Optional[int]:
    return c.execute(select(rides.c.id).where(rides.c.group_id == gid)).scalar()


def members(c: Connection, gid: int, membership: Optional[str] = "member") -> list[int]:
    q = select(duplicate_group_members.c.activity_id).where(duplicate_group_members.c.group_id == gid)
    if membership:
        q = q.where(duplicate_group_members.c.membership == membership)
    return [r[0] for r in c.execute(q.order_by(duplicate_group_members.c.activity_id))]


def group(c: Connection, gid: int) -> dict:
    row = c.execute(select(duplicate_groups).where(duplicate_groups.c.id == gid)).mappings().first()
    if row is None:
        raise DecisionError(f"duplicate group {gid} does not exist")
    return dict(row)


def recorded_fields(c: Connection, aid: int) -> set[str]:
    present = {r[0] for r in c.execute(select(activity_channels.c.channel)
                                       .where(activity_channels.c.activity_id == aid, activity_channels.c.present))}
    return present | {"timer"}


def sources(c: Connection, ride_id: int) -> dict[str, Optional[int]]:
    rows = c.execute(select(ride_channel_sources.c.channel, ride_channel_sources.c.activity_id)
                     .where(ride_channel_sources.c.ride_id == ride_id)).all()
    out = dict.fromkeys(SELECTABLE_FIELDS)
    out.update({ch: aid for ch, aid in rows})
    return out


# ---------------------------------------------------------------- selection

def _apply_selection(c: Connection, ride_id: int, selection: dict[str, Optional[int]], now: float,
                     selected_by: str) -> int:
    rev = c.execute(select(rides.c.selection_revision).where(rides.c.id == ride_id)).scalar_one() + 1
    c.execute(update(rides).where(rides.c.id == ride_id).values(selection_revision=rev, needs_review=False))
    c.execute(delete(ride_channel_sources).where(ride_channel_sources.c.ride_id == ride_id))
    rows = [{"ride_id": ride_id, "channel": ch, "activity_id": selection[ch], "selected_at_utc": now,
             "selection_revision": rev, "selected_by": selected_by} for ch in SELECTABLE_FIELDS]
    c.execute(insert(ride_channel_sources), rows)
    c.execute(insert(ride_selection_history), [{k: r[k] for k in ("ride_id", "channel", "activity_id", "selected_at_utc",
                                                                    "selection_revision", "selected_by")} for r in rows])
    store_ride_metrics(c, ride_id, now)
    return rev


def validate_selection(c: Connection, included: list[int], selection: dict) -> dict[str, Optional[int]]:
    """Every selectable field must be stated explicitly; preferences only prefill (spec 5.8)."""
    unknown = set(selection) - set(SELECTABLE_FIELDS)
    if unknown:
        raise DecisionError(f"unknown fields {sorted(unknown)}")
    absent = [f for f in SELECTABLE_FIELDS if f not in selection]
    if absent:
        raise DecisionError(f"selection must state every field explicitly; missing {absent}")
    recorded = {aid: recorded_fields(c, aid) for aid in included}
    out = {}
    for f in SELECTABLE_FIELDS:
        aid = selection[f]
        if aid is None:
            if f == "timer":
                raise DecisionError("a ride needs a timer source")
            out[f] = None   # the rider chose no source: the field is missing for the ride, never zero
            continue
        if aid not in recorded:
            raise DecisionError(f"{f}: activity {aid} is not a member of this ride")
        if f not in recorded[aid]:
            raise DecisionError(f"{f}: activity {aid} did not record this field")
        out[f] = aid
    return out


def create_single(c: Connection, aid: int, now: float) -> int:
    ride_id = c.execute(insert(rides).values(kind="single", activity_id=aid, needs_review=False, active=True,
                                             selection_revision=0)).inserted_primary_key[0]
    have = recorded_fields(c, aid)
    _apply_selection(c, ride_id, {f: (aid if f in have else None) for f in SELECTABLE_FIELDS}, now, "implicit")
    return ride_id


# ---------------------------------------------------------------- prefill

def get_preferences(c: Connection) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for ch, _, rule in c.execute(select(channel_preferences).order_by(channel_preferences.c.channel,
                                                                     channel_preferences.c.rank)):
        out.setdefault(ch, []).append(json.loads(rule))
    return out


def set_preferences(c: Connection, prefs: dict[str, list[dict]]) -> None:
    """Replace saved preferences. A rule matches on `source_platform`, `source_format` and/or `product`."""
    allowed = {"source_platform", "source_format", "product"}
    for ch, rules in prefs.items():
        if ch not in SELECTABLE_FIELDS:
            raise DecisionError(f"unknown field {ch!r}")
        for r in rules:
            if not r or set(r) - allowed:
                raise DecisionError(f"rule keys must be a non empty subset of {sorted(allowed)}")
    c.execute(delete(channel_preferences))
    rows = [{"channel": ch, "rank": i, "rule_json": json.dumps(r, sort_keys=True)}
            for ch, rules in prefs.items() for i, r in enumerate(rules)]
    if rows:
        c.execute(insert(channel_preferences), rows)


def _descriptor(c: Connection, aid: int) -> dict:
    from ..storage.schema import source_files
    row = c.execute(select(activities.c.source_platform, activities.c.device_identity_json, source_files.c.media_format)
                    .join(source_files, source_files.c.id == activities.c.source_file_id)
                    .where(activities.c.id == aid)).one()
    device = json.loads(row.device_identity_json or "{}").get("device") or {}
    return {"source_platform": (row.source_platform or "").lower(), "source_format": row.media_format,
            "product": None if device.get("product") is None else str(device.get("product"))}


def _matches(desc: dict, rule: dict) -> bool:
    return all(str(desc.get(k) or "").lower() == str(v).lower() for k, v in rule.items())


def prefill(c: Connection, included: list[int]) -> dict[str, dict]:
    """Suggested selection for the confirmation form, with the reason for each suggestion.

    Saved preferences first, in rank order. Otherwise the member with the most
    observed seconds for that channel; for `timer`, a member with device timer
    events, then the longest timer. A suggestion is never applied without the
    rider's confirmation.
    """
    prefs = get_preferences(c)
    descs = {aid: _descriptor(c, aid) for aid in included}
    obs = {(r.activity_id, r.channel): r.observed_s for r in c.execute(
        select(activity_channels).where(activity_channels.c.activity_id.in_(included),
                                        activity_channels.c.present))}
    acts = {r.id: r for r in c.execute(select(activities.c.id, activities.c.timer_source, activities.c.timer_s)
                                       .where(activities.c.id.in_(included)))}
    out = {}
    for f in SELECTABLE_FIELDS:
        able = included if f == "timer" else [a for a in included if (a, f) in obs]
        choice = None
        for rule in prefs.get(f, []):
            hit = [a for a in able if _matches(descs[a], rule)]
            if hit:
                choice = {"activity_id": hit[0], "basis": "preference", "rule": rule}
                break
        if choice is None and able:
            if f == "timer":
                best = max(able, key=lambda a: (acts[a].timer_source == "device_events", acts[a].timer_s or 0, -a))
                choice = {"activity_id": best, "basis": "device timer events, then longest timer"}
            else:
                best = max(able, key=lambda a: (obs[(a, f)], -a))
                choice = {"activity_id": best, "basis": "most observed seconds"}
        out[f] = choice or {"activity_id": None, "basis": "no member recorded this field"}
    return out


# ---------------------------------------------------------------- ride metrics

def _input_revision(c: Connection, ride_id: int, src: dict, runs_by_activity: dict) -> str:
    ride = c.execute(select(rides).where(rides.c.id == ride_id)).mappings().one()
    doc = {"ride_id": ride_id, "kind": ride["kind"], "selection_revision": ride["selection_revision"],
           "members": members(c, ride["group_id"]) if ride["group_id"] else [ride["activity_id"]],
           "sources": src,
           "source_input_revisions": {str(a): sorted({r["input_revision"] for r in runs})
                                      for a, runs in runs_by_activity.items()}}
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()


def store_ride_metrics(c: Connection, ride_id: int, now: float) -> None:
    src = sources(c, ride_id)
    used = {a for a in (src["timer"], src["power"]) if a is not None}
    runs = latest(c, "activity", used)
    revision = _input_revision(c, ride_id, src, runs)
    for aid, metric_ids, field in ((src["timer"], ("M001",), "timer"), (src["power"], POWER_METRICS, "power")):
        if aid is None:
            # No power source selected: power metrics are unavailable, never 0 (spec 5.8).
            for run in latest(c, "activity", [src["timer"]]).get(src["timer"], []):
                if run["metric_id"] in metric_ids:
                    r = MetricResult(run["metric_id"], run["version"], "DERIVED", run["units"], None, NO_POWER,
                                     run["parameters"], {"reason": "no power source selected for this ride"})
                    insert_run(c, "ride", ride_id, r, revision, now,
                               {"ride_id": ride_id, "field_sources": src, "activity_ids": [], "source_sha256": []})
            continue
        for run in runs.get(aid, []):
            if run["metric_id"] not in metric_ids:
                continue
            r = MetricResult(run["metric_id"], run["version"], "DERIVED", run["units"], run["value"], run["state"],
                             run["parameters"], {**run["details"], "source_run_id": run["run_id"]})
            insert_run(c, "ride", ride_id, r, revision, now,
                       {"ride_id": ride_id, "field": field, "field_sources": src, "activity_ids": [aid],
                        "source_sha256": run["provenance"].get("source_sha256", [])})


# ---------------------------------------------------------------- decisions

def _set_singles_active(c: Connection, aids: list[int], active: bool) -> None:
    if aids:
        c.execute(update(rides).where(rides.c.activity_id.in_(aids)).values(active=active))


def _in_other_confirmed(c: Connection, gid: int, aids: list[int]) -> list[int]:
    return [r[0] for r in c.execute(
        select(duplicate_group_members.c.activity_id)
        .join(duplicate_groups, duplicate_groups.c.id == duplicate_group_members.c.group_id)
        .where(duplicate_group_members.c.activity_id.in_(aids), duplicate_group_members.c.group_id != gid,
               duplicate_groups.c.status == "confirmed", duplicate_group_members.c.membership == "member"))]


def confirm(c: Connection, gid: int, selection: dict, now: float, exclude: tuple[int, ...] = ()) -> int:
    """Confirm a proposed group as one ride. Returns the group ride id."""
    g = group(c, gid)
    if g["status"] != "proposed":
        raise DecisionError(f"group {gid} is {g['status']}; only a proposed group can be confirmed")
    current = members(c, gid)
    bad = set(exclude) - set(current)
    if bad:
        raise DecisionError(f"activities {sorted(bad)} are not members of group {gid}")
    included = [a for a in current if a not in set(exclude)]
    if len(included) < 2:
        raise DecisionError("a confirmed group needs at least two recordings")
    clash = _in_other_confirmed(c, gid, included)
    if clash:
        raise DecisionError(f"activities {clash} already belong to another confirmed ride")
    chosen = validate_selection(c, included, selection)
    if exclude:
        c.execute(update(duplicate_group_members).where(duplicate_group_members.c.group_id == gid,
                                                        duplicate_group_members.c.activity_id.in_(exclude))
                  .values(membership="excluded"))
    c.execute(update(duplicate_groups).where(duplicate_groups.c.id == gid).values(status="confirmed", decided_at_utc=now))
    _set_singles_active(c, included, False)
    ride_id = group_ride_id(c, gid)
    if ride_id is None:
        ride_id = c.execute(insert(rides).values(kind="group", group_id=gid, needs_review=False, active=True,
                                                 selection_revision=0)).inserted_primary_key[0]
    else:
        c.execute(update(rides).where(rides.c.id == ride_id).values(active=True))
    rev = _apply_selection(c, ride_id, chosen, now, "rider")
    log_event(c, gid, "confirmed", now, detail={"selection": chosen, "excluded": sorted(exclude),
                                                "selection_revision": rev})
    return ride_id


def reject(c: Connection, gid: int, now: float) -> None:
    """The members are separate rides. Nothing about the rides changes, because proposals changed nothing."""
    g = group(c, gid)
    if g["status"] != "proposed":
        raise DecisionError(f"group {gid} is {g['status']}; only a proposed group can be rejected")
    c.execute(update(duplicate_groups).where(duplicate_groups.c.id == gid).values(status="rejected", decided_at_utc=now))
    log_event(c, gid, "rejected", now)


def reopen(c: Connection, gid: int, now: float) -> None:
    """Undo a confirmation or rejection. The group is proposed again with all its recordings."""
    g = group(c, gid)
    if g["status"] == "proposed":
        raise DecisionError(f"group {gid} is already proposed")
    if g["status"] == "confirmed":
        ride_id = group_ride_id(c, gid)
        c.execute(update(rides).where(rides.c.id == ride_id).values(active=False))
        _set_singles_active(c, members(c, gid), True)
    c.execute(update(duplicate_group_members).where(duplicate_group_members.c.group_id == gid)
              .values(membership="member"))
    c.execute(update(duplicate_groups).where(duplicate_groups.c.id == gid).values(status="proposed", decided_at_utc=None))
    log_event(c, gid, "reopened", now, detail={"previous_status": g["status"]})


def accept_pending(c: Connection, gid: int, aid: int, selection: dict, now: float) -> int:
    """Add a recording proposed for an already confirmed ride, with a new full selection."""
    g = group(c, gid)
    if g["status"] != "confirmed" or aid not in members(c, gid, "pending"):
        raise DecisionError(f"activity {aid} is not pending in confirmed group {gid}")
    if _in_other_confirmed(c, gid, [aid]):
        raise DecisionError(f"activity {aid} already belongs to another confirmed ride")
    chosen = validate_selection(c, members(c, gid) + [aid], selection)
    c.execute(update(duplicate_group_members).where(duplicate_group_members.c.group_id == gid,
                                                    duplicate_group_members.c.activity_id == aid)
              .values(membership="member"))
    _set_singles_active(c, [aid], False)
    ride_id = group_ride_id(c, gid)
    rev = _apply_selection(c, ride_id, chosen, now, "rider")
    log_event(c, gid, "pending_accepted", now, activity_id=aid, detail={"selection": chosen, "selection_revision": rev})
    return ride_id


def exclude_pending(c: Connection, gid: int, aid: int, now: float) -> None:
    if aid not in members(c, gid, "pending"):
        raise DecisionError(f"activity {aid} is not pending in group {gid}")
    c.execute(update(duplicate_group_members).where(duplicate_group_members.c.group_id == gid,
                                                    duplicate_group_members.c.activity_id == aid)
              .values(membership="excluded"))
    log_event(c, gid, "pending_excluded", now, activity_id=aid)


def change_selection(c: Connection, ride_id: int, selection: dict, now: float) -> int:
    ride = c.execute(select(rides).where(rides.c.id == ride_id)).mappings().first()
    if ride is None or ride["kind"] != "group" or not ride["active"]:
        raise DecisionError("only a confirmed group ride has a selectable source per field")
    chosen = validate_selection(c, members(c, ride["group_id"]), selection)
    rev = _apply_selection(c, ride_id, chosen, now, "rider")
    log_event(c, ride["group_id"], "selection_changed", now, detail={"selection": chosen, "selection_revision": rev})
    return rev
