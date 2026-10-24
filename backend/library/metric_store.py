"""Metric runs and values with provenance (spec P7, architecture 5).

A run records what was computed (metric id, version, parameters), from what
(input revision, source file hashes) and by which code (computation version).
Runs are never updated; a changed input creates a new run and old runs stay.
"""
from __future__ import annotations

import json
from importlib import metadata as _md
from typing import Any, Iterable, Optional

from sqlalchemy import Connection, func, insert, select

from ..canonical.timeline import Timeline
from ..metrics import m001_duration, m004_mmp
from ..metrics.m002_m003_power import mean_power, mechanical_work
from ..metrics.result import MetricResult
from ..storage.schema import metric_runs, metric_values

try:
    COMPUTATION_VERSION = f"ocs-{_md.version('open-cycling-science')}"
except _md.PackageNotFoundError:   # running from a source tree without install
    COMPUTATION_VERSION = "ocs-source"

AVAILABLE = ("valid", "lower_bound", "unconfirmed_duplicates_included")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def compute_activity_metrics(tl: Timeline) -> list[MetricResult]:
    results = [m001_duration.compute(tl), mean_power(tl), mechanical_work(tl)]
    results += [m004_mmp.compute(tl, T) for T in m004_mmp.DEFAULT_DURATIONS_S]
    return results


def insert_run(c: Connection, scope_type: str, scope_id: int, result: MetricResult, input_revision: str,
               now: float, provenance: dict) -> int:
    run_id = c.execute(insert(metric_runs).values(
        metric_id=result.metric_id, metric_version=result.version, scope_type=scope_type, scope_id=scope_id,
        parameter_json=_dumps(result.parameters), input_revision=input_revision, calculated_at_utc=now,
        quality_json=_dumps(result.details),
        computation_version=COMPUTATION_VERSION, provenance_json=_dumps(provenance),
    )).inserted_primary_key[0]
    c.execute(insert(metric_values).values(
        run_id=run_id, numeric_value=result.value, state=result.state, units=result.units,
        uncertainty_json=None))   # null = not quantified (spec 6.4 item 5)
    return run_id


def store_activity_metrics(c: Connection, activity_id: int, tl: Timeline, input_revision: str,
                           source_sha256: str, now: float) -> None:
    provenance = {"activity_ids": [activity_id], "source_sha256": [source_sha256]}
    for r in compute_activity_metrics(tl):
        insert_run(c, "activity", activity_id, r, input_revision, now, provenance)


def latest(c: Connection, scope_type: str, scope_ids: Iterable[int]) -> dict[int, list[dict]]:
    """Newest run per (metric, parameters) for each scope id, joined with its value."""
    ids = list(scope_ids)
    if not ids:
        return {}
    newest = (select(func.max(metric_runs.c.id).label("id"))
              .where(metric_runs.c.scope_type == scope_type, metric_runs.c.scope_id.in_(ids))
              .group_by(metric_runs.c.scope_id, metric_runs.c.metric_id, metric_runs.c.parameter_json)
              .subquery())
    rows = c.execute(select(metric_runs, metric_values.c.numeric_value, metric_values.c.state,
                            metric_values.c.units, metric_values.c.uncertainty_json)
                     .join(metric_values, metric_values.c.run_id == metric_runs.c.id)
                     .where(metric_runs.c.id.in_(select(newest.c.id)))
                     .order_by(metric_runs.c.metric_id, metric_runs.c.id)).mappings().all()
    out: dict[int, list[dict]] = {i: [] for i in ids}
    for r in rows:
        out[r["scope_id"]].append({
            "run_id": r["id"], "metric_id": r["metric_id"], "version": r["metric_version"],
            "parameters": json.loads(r["parameter_json"]), "value": r["numeric_value"], "state": r["state"],
            "units": r["units"], "details": json.loads(r["quality_json"] or "{}"),
            "input_revision": r["input_revision"], "calculated_at_utc": r["calculated_at_utc"],
            "computation_version": r["computation_version"],
            "provenance": json.loads(r["provenance_json"] or "{}"),
            "uncertainty": json.loads(r["uncertainty_json"]) if r["uncertainty_json"] else None,
        })
    return out


def find(runs: list[dict], metric_id: str, **params) -> Optional[dict]:
    for r in runs:
        if r["metric_id"] == metric_id and all(r["parameters"].get(k) == v for k, v in params.items()):
            return r
    return None
