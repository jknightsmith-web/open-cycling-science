"""Local API (architecture 8). Bound to 127.0.0.1 by `python -m backend.api`.

Every metric value carries metric_id, version, classification, units, state,
coverage, parameters, input_revision, source_sha256 and a link to its
register entry (acceptance 12). A value whose register entry is incomplete is
returned with state `not_displayable` and no number (spec 6.2).
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from ..library import Library, aggregates, rides
from ..library.ingest import import_bytes
from ..library.metric_store import latest
from ..science import registry
from ..storage.schema import (CHANNEL_COLUMNS, activities, activity_channels, duplicate_group_events,
                              duplicate_group_members, duplicate_groups, samples, source_files, timer_segments)
from . import catalogue

MAX_UPLOAD_BYTES = 256 * 1024 ** 2   # architecture 9


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


def create_app(lib: Library) -> FastAPI:
    app = FastAPI(title="Open Cycling Science", docs_url=None, redoc_url=None)  # no CDN assets (spec 8.5)

    def decide(fn):
        try:
            with lib.engine.begin() as c:
                return fn(c)
        except rides.DecisionError as exc:
            raise HTTPException(409, str(exc)) from None

    # ------------------------------------------------------------ import
    @app.post("/api/imports")
    async def post_import(request: Request, filename: str = Query(...)):
        data = await request.body()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"upload larger than {MAX_UPLOAD_BYTES} bytes")
        return {"outcomes": [o.__dict__ for o in import_bytes(lib, data, filename)]}

    # ------------------------------------------------------------ activities
    @app.get("/api/activities")
    def list_activities():
        with lib.engine.connect() as c:
            rows = c.execute(select(activities.c.id, activities.c.start_utc, activities.c.timer_s,
                                    activities.c.source_platform, activities.c.timer_source,
                                    source_files.c.original_filename, source_files.c.sha256)
                             .join(source_files, source_files.c.id == activities.c.source_file_id)
                             .order_by(activities.c.start_utc)).mappings().all()
        return [dict(r) for r in rows]

    @app.get("/api/activities/{aid}")
    def get_activity(aid: int):
        with lib.engine.connect() as c:
            a = c.execute(select(activities, source_files.c.sha256, source_files.c.original_filename,
                                 source_files.c.media_format, source_files.c.parser_version)
                          .join(source_files, source_files.c.id == activities.c.source_file_id)
                          .where(activities.c.id == aid)).mappings().first()
            if a is None:
                raise HTTPException(404, "no such activity")
            chans = c.execute(select(activity_channels).where(activity_channels.c.activity_id == aid)).mappings().all()
            segs = c.execute(select(timer_segments.c.start_utc, timer_segments.c.end_utc)
                             .where(timer_segments.c.activity_id == aid)).all()
            runs = latest(c, "activity", [aid])[aid]
        out = {k: v for k, v in a.items() if not k.endswith("_json")}
        out["device_identity"] = json.loads(a["device_identity_json"] or "{}")
        out["recording_stats"] = json.loads(a["recording_stats_json"] or "{}")
        out["recording_flags"] = json.loads(a["recording_flags_json"] or "[]")
        out["channels"] = [{**{k: v for k, v in ch.items() if k != "sensor_identity_json"},
                            "sensor_identity": json.loads(ch["sensor_identity_json"]) if ch["sensor_identity_json"] else "unknown"}
                           for ch in chans]
        out["timer_segments"] = [list(s) for s in segs]
        out["metrics"] = [metric_view(r) for r in runs]
        return out

    @app.get("/api/activities/{aid}/samples")
    def get_samples(aid: int, offset: int = 0, limit: int = Query(3600, le=20000)):
        """Each channel as {value, validity}: value is null unless validity is observed (spec P6)."""
        with lib.engine.connect() as c:
            rows = c.execute(select(samples).where(samples.c.activity_id == aid).order_by(samples.c.sample_index)
                             .offset(offset).limit(limit)).mappings().all()
        return [{"sample_index": r["sample_index"], "timestamp_utc": r["timestamp_utc"],
                 "suspect_zero": bool(r["suspect_zero"]),
                 "channels": {ch: {"value": r[v], "validity": r[s]} for ch, (v, s) in CHANNEL_COLUMNS.items()}}
                for r in rows]

    # ------------------------------------------------------------ duplicate groups
    def group_view(c, gid: int) -> dict:
        g = rides.group(c, gid)
        mem = c.execute(select(duplicate_group_members).where(duplicate_group_members.c.group_id == gid)
                        .order_by(duplicate_group_members.c.activity_id)).mappings().all()
        events = c.execute(select(duplicate_group_events).where(duplicate_group_events.c.group_id == gid)
                           .order_by(duplicate_group_events.c.id)).mappings().all()
        candidates = [m["activity_id"] for m in mem if m["membership"] in ("member", "pending")]
        return {"id": gid, "status": g["status"], "rule_version": g["rule_version"],
                "proposed_at_utc": g["proposed_at_utc"], "decided_at_utc": g["decided_at_utc"],
                "evidence": json.loads(g["overlap_json"] or "{}"),
                "members": [dict(m) for m in mem],
                "ride_id": rides.group_ride_id(c, gid),
                "selection_prefill": rides.prefill(c, candidates) if candidates else {},
                "events": [{**{k: v for k, v in e.items() if k != "detail_json"},
                            "detail": json.loads(e["detail_json"]) if e["detail_json"] else None} for e in events]}

    @app.get("/api/duplicate-groups")
    def list_groups(status: Optional[str] = None):
        with lib.engine.connect() as c:
            q = select(duplicate_groups.c.id).order_by(duplicate_groups.c.id)
            if status:
                q = q.where(duplicate_groups.c.status == status)
            return [group_view(c, gid) for (gid,) in c.execute(q)]

    @app.get("/api/duplicate-groups/{gid}")
    def get_group(gid: int):
        with lib.engine.connect() as c:
            try:
                return group_view(c, gid)
            except rides.DecisionError as exc:
                raise HTTPException(404, str(exc)) from None

    @app.post("/api/duplicate-groups/{gid}/confirm")
    def confirm(gid: int, body: dict = Body(...)):
        return {"ride_id": decide(lambda c: rides.confirm(c, gid, body.get("selection", {}), lib.now(),
                                                          tuple(body.get("exclude_activity_ids", ()))))}

    @app.post("/api/duplicate-groups/{gid}/reject")
    def reject(gid: int):
        decide(lambda c: rides.reject(c, gid, lib.now()))
        return {"status": "rejected"}

    @app.post("/api/duplicate-groups/{gid}/reopen")
    def reopen(gid: int):
        decide(lambda c: rides.reopen(c, gid, lib.now()))
        return {"status": "proposed"}

    @app.post("/api/duplicate-groups/{gid}/members/{aid}/accept")
    def accept(gid: int, aid: int, body: dict = Body(...)):
        return {"ride_id": decide(lambda c: rides.accept_pending(c, gid, aid, body.get("selection", {}), lib.now()))}

    @app.post("/api/duplicate-groups/{gid}/members/{aid}/exclude")
    def exclude(gid: int, aid: int):
        decide(lambda c: rides.exclude_pending(c, gid, aid, lib.now()))
        return {"membership": "excluded"}

    # ------------------------------------------------------------ rides
    def ride_view(c, ride_id: int) -> dict:
        from ..storage.schema import ride_selection_history, rides as rides_t
        r = c.execute(select(rides_t).where(rides_t.c.id == ride_id)).mappings().first()
        if r is None:
            raise HTTPException(404, "no such ride")
        hist = c.execute(select(ride_selection_history).where(ride_selection_history.c.ride_id == ride_id)
                         .order_by(ride_selection_history.c.id)).mappings().all()
        return {**dict(r), "sources": rides.sources(c, ride_id),
                "selection_history": [dict(h) for h in hist],
                "metrics": [metric_view(m) for m in latest(c, "ride", [ride_id])[ride_id]]}

    @app.get("/api/rides")
    def list_rides(include_inactive: bool = False):
        from ..storage.schema import rides as rides_t
        with lib.engine.connect() as c:
            q = select(rides_t.c.id).order_by(rides_t.c.id)
            if not include_inactive:
                q = q.where(rides_t.c.active)
            return [ride_view(c, rid) for (rid,) in c.execute(q)]

    @app.get("/api/rides/{ride_id}")
    def get_ride(ride_id: int):
        with lib.engine.connect() as c:
            return ride_view(c, ride_id)

    @app.put("/api/rides/{ride_id}/channels")
    def put_channels(ride_id: int, body: dict = Body(...)):
        return {"selection_revision": decide(lambda c: rides.change_selection(c, ride_id, body.get("selection", {}),
                                                                                lib.now()))}

    @app.get("/api/channel-preferences")
    def get_prefs():
        with lib.engine.connect() as c:
            return rides.get_preferences(c)

    @app.put("/api/channel-preferences")
    def put_prefs(body: dict = Body(...)):
        decide(lambda c: rides.set_preferences(c, body))
        return body

    # ------------------------------------------------------------ aggregates
    @app.get("/api/aggregates")
    def get_aggregates(start_utc: float, end_utc: float):
        with lib.engine.connect() as c:
            return aggregates.totals(c, start_utc, end_utc)

    # ------------------------------------------------------------ science catalogue
    @app.get("/api/science/metrics")
    def science_list():
        return [{"metric_id": e["metric_id"], "version": str(e["version"]), "display_name": e["display_name"],
                 "classification": e["classification"], "units": e["units"],
                 "complete": not registry.problems(e), "register_url": f"/api/science/metrics/{e['metric_id']}"}
                for e in registry.entries().values()]

    @app.get("/api/science/metrics/{metric_id}")
    def science_entry(metric_id: str):
        try:
            e = registry.entry(metric_id)
        except registry.RegistryError as exc:
            raise HTTPException(404, str(exc)) from None
        return {**registry.with_sources(e), "problems": registry.problems(e)}

    @app.get("/api/science/states")
    def science_states():
        return registry.states()

    @app.get("/science", response_class=HTMLResponse)
    def science_page():
        return catalogue.index_page()

    @app.get("/science/{metric_id}", response_class=HTMLResponse)
    def science_metric_page(metric_id: str):
        try:
            return catalogue.metric_page(metric_id)
        except registry.RegistryError as exc:
            raise HTTPException(404, str(exc)) from None

    return app
