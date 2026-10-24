"""Local API (architecture 8, design 06 section 6). Bound to 127.0.0.1 by `python -m backend.api`.

Every metric value carries metric_id, version, classification, units, state,
coverage, parameters, input_revision, source_sha256 and a link to its
register entry (acceptance 12). A value whose register entry is incomplete is
returned with state `not_displayable` and no number (spec 6.2).

The built frontend (frontend/dist) is served at `/`; any path that is not an
API, asset or catalogue path returns its index.html so deep links work.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from ..config import layout
from ..library import Library, aggregates, rides
from ..library.ingest import import_bytes
from ..library.metric_store import COMPUTATION_VERSION, latest
from ..library.series import envelope, load_timeline
from ..science import registry
from ..storage.schema import (CHANNEL_COLUMNS, activities, activity_channels, app_settings, duplicate_group_events,
                              duplicate_group_members, duplicate_groups, ride_selection_history, rides as rides_t,
                              samples, source_files, timer_segments)
from . import catalogue
from . import models as m

MAX_UPLOAD_BYTES = 256 * 1024 ** 2   # architecture 9
FRONTEND_DIST = Path(os.environ.get("OCS_FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
SERIES_CHANNELS = tuple(CHANNEL_COLUMNS)


def metric_view(run: dict) -> dict:
    e = registry.entries().get(run["metric_id"])
    ok = registry.displayable(run["metric_id"], run["version"])
    return {
        "metric_id": run["metric_id"], "version": run["version"],
        "display_name": e["display_name"] if e else None,
        "classification": e["classification"] if e else None,
        "units": run["units"],
        "value": run["value"] if ok else None,
        "state": run["state"] if ok else "not_displayable",
        "coverage": run["details"].get("coverage"),
        "parameters": run["parameters"], "details": run["details"],
        "input_revision": run["input_revision"], "computation_version": run["computation_version"],
        "calculated_at_utc": run["calculated_at_utc"],
        "source_sha256": run["provenance"].get("source_sha256", []),
        "source_activity_ids": run["provenance"].get("activity_ids", []),
        "uncertainty": run["uncertainty"] or "not quantified",
        "register_url": f"/api/science/metrics/{run['metric_id']}",
        "catalogue_url": f"/science/{run['metric_id']}",
    }


def _activity_rows(c, where=None, order_desc=True, offset=0, limit=None) -> list[dict]:
    q = (select(activities, source_files.c.sha256, source_files.c.original_filename, source_files.c.media_format,
                source_files.c.parser_version)
         .join(source_files, source_files.c.id == activities.c.source_file_id))
    if where is not None:
        q = q.where(where)
    order = activities.c.start_utc.desc() if order_desc else activities.c.start_utc.asc()
    q = q.order_by(order, activities.c.id.desc() if order_desc else activities.c.id.asc()).offset(offset)
    if limit is not None:
        q = q.limit(limit)
    rows = [dict(r) for r in c.execute(q).mappings()]
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    chans: dict[int, dict] = {i: {} for i in ids}
    for ch in c.execute(select(activity_channels.c.activity_id, activity_channels.c.channel, activity_channels.c.present,
                               activity_channels.c.origin).where(activity_channels.c.activity_id.in_(ids))):
        chans[ch.activity_id][ch.channel] = {"present": bool(ch.present), "origin": ch.origin}
    groups: dict[int, dict] = {}
    for g in c.execute(select(duplicate_group_members.c.activity_id, duplicate_group_members.c.group_id,
                              duplicate_group_members.c.membership, duplicate_groups.c.status)
                       .join(duplicate_groups, duplicate_groups.c.id == duplicate_group_members.c.group_id)
                       .where(duplicate_group_members.c.activity_id.in_(ids))
                       .order_by(duplicate_group_members.c.group_id)):
        # The open group (proposed or confirmed) wins over a rejected one.
        if g.activity_id not in groups or groups[g.activity_id]["status"] == "rejected":
            groups[g.activity_id] = {"id": g.group_id, "status": g.status, "membership": g.membership}
    single = {r.activity_id: (r.id, bool(r.active)) for r in c.execute(
        select(rides_t.c.id, rides_t.c.activity_id, rides_t.c.active).where(rides_t.c.activity_id.in_(ids)))}
    group_rides = {r.group_id: r.id for r in c.execute(select(rides_t.c.id, rides_t.c.group_id)
                                                       .where(rides_t.c.group_id.is_not(None), rides_t.c.active))}
    out = []
    for r in rows:
        g = groups.get(r["id"])
        ride_id, active = single.get(r["id"], (None, False))
        if not active and g and g["status"] == "confirmed" and g["membership"] == "member":
            ride_id = group_rides.get(g["id"])
        out.append({**r, "channels": chans[r["id"]], "flags": json.loads(r["recording_flags_json"] or "[]"),
                    "ride_id": ride_id, "group": g})
    return out


def _row_view(r: dict) -> dict:
    return {k: r[k] for k in m.ActivityRow.model_fields}


def create_app(lib: Library) -> FastAPI:
    app = FastAPI(title="Open Cycling Science", docs_url=None, redoc_url=None)  # no CDN assets (spec 8.5)

    def decide(fn):
        try:
            with lib.engine.begin() as c:
                return fn(c)
        except rides.DecisionError as exc:
            raise HTTPException(409, str(exc)) from None

    # ------------------------------------------------------------ import
    @app.post("/api/imports", response_model=m.ImportResponse)
    async def post_import(request: Request, filename: str = Query(...)):
        data = await request.body()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"upload larger than {MAX_UPLOAD_BYTES} bytes")
        return {"outcomes": [o.__dict__ for o in import_bytes(lib, data, filename)]}

    @app.get("/api/imports", response_model=m.ImportLogPage)
    def import_log(offset: int = 0, limit: int = Query(50, le=500)):
        with lib.engine.connect() as c:
            total = c.execute(select(func.count()).select_from(source_files)).scalar()
            rows = c.execute(select(source_files, activities.c.id.label("activity_id"))
                             .outerjoin(activities, activities.c.source_file_id == source_files.c.id)
                             .order_by(source_files.c.imported_at_utc.desc(), source_files.c.id.desc())
                             .offset(offset).limit(limit)).mappings().all()
        return {"total": total, "items": [
            {"source_file_id": r["id"], "sha256": r["sha256"], "original_filename": r["original_filename"],
             "media_format": r["media_format"], "byte_length": r["byte_length"],
             "imported_at_utc": r["imported_at_utc"], "validation_status": r["validation_status"],
             "error": json.loads(r["validation_details"]) if r["validation_details"] else None,
             "activity_id": r["activity_id"]} for r in rows]}

    # ------------------------------------------------------------ activities
    @app.get("/api/activities", response_model=m.ActivityPage)
    def list_activities(offset: int = 0, limit: int = Query(50, le=500), order: str = Query("desc", pattern="^(asc|desc)$")):
        with lib.engine.connect() as c:
            total = c.execute(select(func.count()).select_from(activities)).scalar()
            rows = _activity_rows(c, order_desc=order == "desc", offset=offset, limit=limit)
        return {"total": total, "items": [_row_view(r) for r in rows]}

    @app.get("/api/activities/{aid}", response_model=m.ActivityDetail)
    def get_activity(aid: int):
        with lib.engine.connect() as c:
            found = _activity_rows(c, where=activities.c.id == aid)
            if not found:
                raise HTTPException(404, "no such activity")
            a = found[0]
            chans = c.execute(select(activity_channels).where(activity_channels.c.activity_id == aid)
                              .order_by(activity_channels.c.channel)).mappings().all()
            segs = c.execute(select(timer_segments.c.start_utc, timer_segments.c.end_utc)
                             .where(timer_segments.c.activity_id == aid).order_by(timer_segments.c.start_utc)).all()
            runs = latest(c, "activity", [aid])[aid]
        return {**_row_view(a), "device_timer_s": a["device_timer_s"], "nominal_interval_s": a["nominal_interval_s"],
                "original_activity_id": a["original_activity_id"], "parser_version": a["parser_version"],
                "device_identity": json.loads(a["device_identity_json"] or "{}"),
                "recording_stats": json.loads(a["recording_stats_json"] or "{}"),
                "channel_info": [{"channel": ch["channel"], "present": bool(ch["present"]), "origin": ch["origin"],
                                  "observed_s": ch["observed_s"], "invalid_count": ch["invalid_count"],
                                  "suspect_zero_s": ch["suspect_zero_s"],
                                  "sensor_identity": json.loads(ch["sensor_identity_json"])
                                  if ch["sensor_identity_json"] else "unknown"} for ch in chans],
                "timer_segments": [list(s) for s in segs],
                "metrics": [metric_view(r) for r in runs]}

    @app.get("/api/activities/{aid}/samples", response_model=m.SamplePage)
    def get_samples(aid: int, offset: int = 0, limit: int = Query(500, le=20000)):
        """Each channel as {value, validity}: value is null unless validity is observed (spec P6)."""
        with lib.engine.connect() as c:
            total = c.execute(select(func.count()).select_from(samples).where(samples.c.activity_id == aid)).scalar()
            rows = c.execute(select(samples).where(samples.c.activity_id == aid).order_by(samples.c.sample_index)
                             .offset(offset).limit(limit)).mappings().all()
        return {"total": total, "items": [
            {"sample_index": r["sample_index"], "timestamp_utc": r["timestamp_utc"],
             "suspect_zero": bool(r["suspect_zero"]),
             "channels": {ch: {"value": r[v], "validity": r[s]} for ch, (v, s) in CHANNEL_COLUMNS.items()}}
            for r in rows]}

    @app.get("/api/activities/{aid}/series", response_model=m.Series)
    def get_series(aid: int, channel: str = Query(...), points: int = Query(2000, ge=16, le=20000)):
        """Display envelope for charts (design 06 B3). Not a metric; never shown as a value."""
        if channel not in SERIES_CHANNELS:
            raise HTTPException(422, f"channel must be one of {SERIES_CHANNELS}")
        with lib.engine.connect() as c:
            tl = load_timeline(c, aid)
        if tl is None:
            raise HTTPException(404, "no such activity")
        out = envelope(tl, channel, points)
        out["suspect_zero"] = [list(r) for r in tl.suspect_zero_runs] if channel == "power" else []
        out["timer_segments"] = [list(s) for s in tl.segments]
        return out

    # ------------------------------------------------------------ duplicate groups
    def group_view(c, gid: int) -> dict:
        g = rides.group(c, gid)
        mem = c.execute(select(duplicate_group_members).where(duplicate_group_members.c.group_id == gid)
                        .order_by(duplicate_group_members.c.activity_id)).mappings().all()
        events = c.execute(select(duplicate_group_events).where(duplicate_group_events.c.group_id == gid)
                           .order_by(duplicate_group_events.c.id)).mappings().all()
        candidates = [x["activity_id"] for x in mem if x["membership"] in ("member", "pending")]
        return {"id": gid, "status": g["status"], "rule_version": g["rule_version"],
                "proposed_at_utc": g["proposed_at_utc"], "decided_at_utc": g["decided_at_utc"],
                "evidence": json.loads(g["overlap_json"] or "{}"),
                "members": [dict(x) for x in mem],
                "ride_id": rides.group_ride_id(c, gid),
                "selection_prefill": rides.prefill(c, candidates) if candidates else {},
                "events": [{**{k: v for k, v in e.items() if k != "detail_json"},
                            "detail": json.loads(e["detail_json"]) if e["detail_json"] else None} for e in events]}

    @app.get("/api/duplicate-groups", response_model=list[m.DuplicateGroup])
    def list_groups(status: Optional[str] = None):
        with lib.engine.connect() as c:
            q = select(duplicate_groups.c.id).order_by(duplicate_groups.c.id.desc())
            if status:
                q = q.where(duplicate_groups.c.status == status)
            return [group_view(c, gid) for (gid,) in c.execute(q)]

    @app.get("/api/duplicate-groups/{gid}", response_model=m.DuplicateGroup)
    def get_group(gid: int):
        with lib.engine.connect() as c:
            try:
                return group_view(c, gid)
            except rides.DecisionError as exc:
                raise HTTPException(404, str(exc)) from None

    @app.post("/api/duplicate-groups/{gid}/confirm", response_model=m.RideId)
    def confirm(gid: int, body: m.SelectionBody):
        return {"ride_id": decide(lambda c: rides.confirm(c, gid, body.selection, lib.now(),
                                                          tuple(body.exclude_activity_ids)))}

    @app.post("/api/duplicate-groups/{gid}/reject", response_model=m.StatusOut)
    def reject(gid: int):
        decide(lambda c: rides.reject(c, gid, lib.now()))
        return {"status": "rejected"}

    @app.post("/api/duplicate-groups/{gid}/reopen", response_model=m.StatusOut)
    def reopen(gid: int):
        decide(lambda c: rides.reopen(c, gid, lib.now()))
        return {"status": "proposed"}

    @app.post("/api/duplicate-groups/{gid}/members/{aid}/accept", response_model=m.RideId)
    def accept(gid: int, aid: int, body: m.SelectionBody):
        return {"ride_id": decide(lambda c: rides.accept_pending(c, gid, aid, body.selection, lib.now()))}

    @app.post("/api/duplicate-groups/{gid}/members/{aid}/exclude", response_model=m.StatusOut)
    def exclude(gid: int, aid: int):
        decide(lambda c: rides.exclude_pending(c, gid, aid, lib.now()))
        return {"status": "excluded"}

    # ------------------------------------------------------------ rides
    def ride_view(c, ride_id: int) -> dict:
        r = c.execute(select(rides_t).where(rides_t.c.id == ride_id)).mappings().first()
        if r is None:
            raise HTTPException(404, "no such ride")
        hist = c.execute(select(ride_selection_history).where(ride_selection_history.c.ride_id == ride_id)
                         .order_by(ride_selection_history.c.id)).mappings().all()
        members = rides.members(c, r["group_id"]) if r["group_id"] else [r["activity_id"]]
        return {**{k: r[k] for k in ("id", "kind", "activity_id", "group_id", "selection_revision")},
                "needs_review": bool(r["needs_review"]), "active": bool(r["active"]), "members": members,
                "sources": rides.sources(c, ride_id), "selection_history": [dict(h) for h in hist],
                "metrics": [metric_view(x) for x in latest(c, "ride", [ride_id])[ride_id]]}

    @app.get("/api/rides/{ride_id}", response_model=m.Ride)
    def get_ride(ride_id: int):
        with lib.engine.connect() as c:
            return ride_view(c, ride_id)

    @app.put("/api/rides/{ride_id}/channels", response_model=m.RevisionOut)
    def put_channels(ride_id: int, body: m.SelectionBody):
        return {"selection_revision": decide(lambda c: rides.change_selection(c, ride_id, body.selection, lib.now()))}

    @app.get("/api/channel-preferences", response_model=dict[str, list[dict]])
    def get_prefs():
        with lib.engine.connect() as c:
            return rides.get_preferences(c)

    @app.put("/api/channel-preferences", response_model=dict[str, list[dict]])
    def put_prefs(body: dict[str, list[dict]] = Body(...)):
        decide(lambda c: rides.set_preferences(c, body))
        return body

    # ------------------------------------------------------------ aggregates
    @app.get("/api/aggregates", response_model=m.RangeTotals)
    def get_aggregates(start_utc: float, end_utc: float):
        with lib.engine.connect() as c:
            return aggregates.totals(c, start_utc, end_utc)

    @app.get("/api/aggregates/weekly", response_model=list[m.WeekTotals])
    def get_weekly(tz: str, first_day: str, last_day: str):
        try:
            ZoneInfo(tz)
            with lib.engine.connect() as c:
                return aggregates.weekly(c, tz, first_day, last_day)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from None

    # ------------------------------------------------------------ settings and system
    def read_settings(c) -> dict:
        stored = {k: json.loads(v) for k, v in c.execute(select(app_settings.c.key, app_settings.c.value_json))}
        return m.Settings(**{k: v for k, v in stored.items() if k in m.Settings.model_fields}).model_dump()

    @app.get("/api/settings", response_model=m.Settings)
    def get_settings():
        with lib.engine.connect() as c:
            return read_settings(c)

    @app.put("/api/settings", response_model=m.Settings)
    def put_settings(body: m.Settings):
        if body.display_time_zone is not None:
            try:
                ZoneInfo(body.display_time_zone)
            except (ZoneInfoNotFoundError, ValueError):
                raise HTTPException(422, f"unknown time zone {body.display_time_zone!r}") from None
        with lib.engine.begin() as c:
            for k, v in body.model_dump().items():
                c.execute(app_settings.delete().where(app_settings.c.key == k))
                c.execute(app_settings.insert().values(key=k, value_json=json.dumps(v)))
            return read_settings(c)

    @app.get("/api/system", response_model=m.System)
    def system():
        paths = layout(lib.root)
        db_bytes = sum(p.stat().st_size for p in paths["db"].parent.glob(paths["db"].name + "*") if p.is_file())
        objects = [p for p in paths["vault"].rglob("*") if p.is_file()] if paths["vault"].exists() else []
        return {"data_root": str(lib.root), "database_bytes": db_bytes,
                "vault_bytes": sum(p.stat().st_size for p in objects), "vault_objects": len(objects),
                "app_version": COMPUTATION_VERSION.removeprefix("ocs-"), "computation_version": COMPUTATION_VERSION,
                "registry": [{"metric_id": e["metric_id"], "version": str(e["version"]),
                              "last_reviewed": str(e["last_reviewed"])} for e in registry.entries().values()],
                "host": "127.0.0.1"}

    # ------------------------------------------------------------ science
    @app.get("/api/science/metrics", response_model=list[m.ScienceRow])
    def science_list():
        return [{"metric_id": e["metric_id"], "version": str(e["version"]), "display_name": e["display_name"],
                 "classification": e["classification"], "units": e["units"],
                 "complete": not registry.problems(e), "register_url": f"/api/science/metrics/{e['metric_id']}"}
                for e in registry.entries().values()]

    @app.get("/api/science/metrics/{metric_id}")
    def science_entry(metric_id: str) -> dict:
        try:
            e = registry.entry(metric_id)
        except registry.RegistryError as exc:
            raise HTTPException(404, str(exc)) from None
        return {**registry.with_sources(e), "version": str(e["version"]), "last_reviewed": str(e["last_reviewed"]),
                "problems": registry.problems(e)}

    @app.get("/api/science/states")
    def science_states() -> dict:
        return registry.states()

    # Server rendered catalogue: a fallback that needs no JavaScript (design 06, 5.4).
    @app.get("/catalogue", response_class=HTMLResponse)
    def catalogue_page():
        return catalogue.index_page()

    @app.get("/catalogue/{metric_id}", response_class=HTMLResponse)
    def catalogue_metric_page(metric_id: str):
        try:
            return catalogue.metric_page(metric_id)
        except registry.RegistryError as exc:
            raise HTTPException(404, str(exc)) from None

    # ------------------------------------------------------------ frontend (B8)
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "no such endpoint")
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return HTMLResponse("<!doctype html><title>Open Cycling Science</title><p>The interface is not built. "
                            "Run <code>make setup</code>. The science catalogue is at <a href='/catalogue'>/catalogue</a>.</p>")

    return app
