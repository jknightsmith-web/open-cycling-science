"""Idempotent import (spec 3.2 item 1, 5.7, acceptance 3 and 5).

Bytes are hashed first. Identical bytes create no new activity and the
existing one is reported. New bytes are stored in the vault unchanged, parsed,
normalised and persisted with their recording statistics, per sample validity,
timer events and activity scope metric runs, then checked for possible
duplicates. A file that fails to parse is kept and reported, never skipped
silently.
"""
from __future__ import annotations

import bisect
import json
from dataclasses import asdict, dataclass
from typing import Optional

from sqlalchemy import Connection, insert, select

from ..canonical.digest import timeline_digest
from ..canonical.model import CHANNELS, INVALID, MISSING, RawActivity, State
from ..canonical.timeline import EPS, Timeline, build_timeline
from ..canonical.validity import classify
from ..importers import archive, fit, tcx
from ..importers.detect import sniff
from ..importers.errors import ImportFailure
from ..storage.schema import (CHANNEL_COLUMNS, activities, activity_channels, samples, source_files,
                              timer_events, timer_segments)
from ..storage.vault import sha256_bytes
from . import Library, duplicates, rides
from .metric_store import store_activity_metrics

PARSERS = {"fit": (fit.parse, fit.PARSER_VERSION), "tcx": (tcx.parse, tcx.PARSER_VERSION)}


@dataclass
class ImportOutcome:
    filename: str
    status: str                      # imported | duplicate_bytes | failed
    sha256: Optional[str] = None
    source_file_id: Optional[int] = None
    activity_id: Optional[int] = None
    group_id: Optional[int] = None   # duplicate group proposed or joined, if any
    error_code: Optional[str] = None
    message: Optional[str] = None


def import_bytes(lib: Library, data: bytes, filename: str) -> list[ImportOutcome]:
    try:
        fmt = sniff(data)
    except ImportFailure as exc:
        return [ImportOutcome(filename, "failed", error_code=exc.code, message=exc.message)]
    if fmt != "zip":
        return [_import_one(lib, data, filename, fmt)]
    try:
        entries = archive.members(data)
    except ImportFailure as exc:
        return [ImportOutcome(filename, "failed", error_code=exc.code, message=exc.message)]
    out = []
    for name, content in entries:
        member = f"{filename}/{name}"
        try:
            inner = sniff(content)
        except ImportFailure as exc:
            out.append(ImportOutcome(member, "failed", error_code=exc.code, message=exc.message))
            continue
        if inner == "zip":
            out.append(ImportOutcome(member, "failed", error_code="unsupported", message="nested archives are not imported"))
            continue
        out.append(_import_one(lib, content, member, inner))
    return out


def _existing(c: Connection, digest: str, filename: str) -> Optional[ImportOutcome]:
    sf = c.execute(select(source_files).where(source_files.c.sha256 == digest)).mappings().first()
    if sf is None:
        return None
    aid = c.execute(select(activities.c.id).where(activities.c.source_file_id == sf["id"])).scalar()
    msg = f"identical bytes were already imported as {sf['original_filename']!r}"
    if sf["validation_status"] == "failed":
        msg += f" and failed: {sf['validation_details']}"
    return ImportOutcome(filename, "duplicate_bytes", digest, sf["id"], aid, message=msg)


def _import_one(lib: Library, data: bytes, filename: str, fmt: str) -> ImportOutcome:
    digest = sha256_bytes(data)
    with lib.engine.connect() as c:
        known = _existing(c, digest, filename)
    if known:
        return known
    parse, parser_version = PARSERS[fmt]
    failure: Optional[ImportFailure] = None
    raw = tl = None
    try:
        raw = parse(data)
        tl = build_timeline(raw)
    except ImportFailure as exc:
        failure = exc
    _, created = lib.vault.put(data)
    now = lib.now()
    try:
        with lib.engine.begin() as c:
            sf_id = c.execute(insert(source_files).values(
                sha256=digest, original_filename=filename, byte_length=len(data), media_format=fmt,
                imported_at_utc=now,
                parser_version=raw.metadata.get("parser_version", parser_version) if raw else parser_version,
                relative_storage_path=str(lib.vault.path_for(digest).relative_to(lib.root)),
                validation_status="failed" if failure else "ok",
                validation_details=json.dumps({"code": failure.code, "message": failure.message}) if failure else None,
            )).inserted_primary_key[0]
            if failure:
                return ImportOutcome(filename, "failed", digest, sf_id, error_code=failure.code,
                                     message=failure.message)
            aid = store_activity(c, sf_id, raw, tl)
            store_activity_metrics(c, aid, tl, timeline_digest(tl), digest, now)
            rides.create_single(c, aid, now)
            gid = duplicates.propose_for(c, aid, now)
    except BaseException:
        if created:
            lib.vault.delete(digest)   # nothing references the object; keep vault and database consistent
        raise
    return ImportOutcome(filename, "imported", digest, sf_id, aid, gid)


def _suspect(tl: Timeline):
    starts = [a for a, _ in tl.suspect_zero_runs]

    def hit(t: float) -> bool:
        i = bisect.bisect_right(starts, t + EPS) - 1
        return i >= 0 and t < tl.suspect_zero_runs[i][1] - EPS
    return hit


def store_activity(c: Connection, source_file_id: int, raw: RawActivity, tl: Timeline) -> int:
    meta = raw.metadata
    aid = c.execute(insert(activities).values(
        source_file_id=source_file_id,
        original_activity_id=meta.get("original_activity_id"),
        source_platform=meta.get("source_platform"),
        device_identity_json=json.dumps({"device": meta.get("device"), "devices": meta.get("devices", [])},
                                        default=str, sort_keys=True),
        sport=None if meta.get("sport") is None else str(meta.get("sport")),
        start_utc=tl.t_start, end_utc=tl.t_end, utc_offset_s=raw.utc_offset_s,
        elapsed_s=(tl.t_end - tl.t_start) if tl.t_end is not None else None,
        timer_s=tl.timer_s, timer_source=tl.timer_source, device_timer_s=tl.device_timer_s,
        nominal_interval_s=tl.nominal_interval_s,
        recording_stats_json=json.dumps(asdict(tl.stats), sort_keys=True),
        recording_flags_json=json.dumps(sorted(tl.flags)),
    )).inserted_primary_key[0]

    # Every record is stored, in time order. Records sharing a timestamp after the
    # first are marked invalid (spec 5.3 item 1); their raw fields stay in original_field_json.
    order = sorted(range(len(raw.records)), key=lambda i: raw.records[i].timestamp_s)
    suspect = _suspect(tl)
    invalid_counts = dict.fromkeys(CHANNELS, 0)
    rows, last = [], None
    for idx, i in enumerate(order):
        rec = raw.records[i]
        dup = last is not None and abs(rec.timestamp_s - last) < EPS
        if not dup:
            last = rec.timestamp_s
        row = {"activity_id": aid, "sample_index": idx, "timestamp_utc": rec.timestamp_s,
               "suspect_zero": (not dup) and suspect(rec.timestamp_s),
               "original_field_json": json.dumps(raw.original_fields[i], default=str, sort_keys=True)
               if i < len(raw.original_fields) else None}
        for ch, (value_col, validity_col) in CHANNEL_COLUMNS.items():
            present = ch in rec.fields
            reading = (INVALID if present else MISSING) if dup else classify(ch, present, rec.fields.get(ch))
            if reading.state is State.INVALID:
                invalid_counts[ch] += 1
            row[value_col], row[validity_col] = reading.value, reading.state.value
        rows.append(row)
    if rows:
        c.execute(insert(samples), rows)

    for ch in CHANNELS:
        c.execute(insert(activity_channels).values(
            activity_id=aid, channel=ch, present=any(ch in r.fields for r in raw.records),
            sensor_identity_json=json.dumps(raw.sensor_identity.get(ch), default=str, sort_keys=True)
            if ch in raw.sensor_identity else None,
            origin="simulated" if ch in raw.simulated_channels else "measured",
            observed_s=tl.stats.channel_observed_s.get(ch, 0.0),
            invalid_count=invalid_counts[ch],
            suspect_zero_s=sum(b - a for a, b in tl.suspect_zero_runs) if ch == "power" else 0.0,
        ))
    if raw.timer_events:
        c.execute(insert(timer_events), [
            {"activity_id": aid, "timestamp_utc": e.timestamp_s, "event_type": e.kind,
             "source_field": f"{raw.source_format}:event.timer"} for e in raw.timer_events])
    if tl.segments:
        c.execute(insert(timer_segments), [
            {"activity_id": aid, "start_utc": a, "end_utc": b, "source": tl.timer_source} for a, b in tl.segments])
    return aid
