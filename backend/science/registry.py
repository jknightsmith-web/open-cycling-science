"""In app metric registry (spec 6.2, P3, P4).

Loads `registry/metrics/*.yaml`, validates each entry against the 20 field
register contract and the code that computes it, and mirrors the entries into
the `metric_definitions` table. A metric whose entry is incomplete is not
displayable (spec 6.2): `displayable()` is the gate the API uses.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Connection, delete, insert

from ..storage.schema import metric_definitions

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"

CONTRACT_FIELDS = (  # spec 6.2, in order
    "metric_id", "version", "display_name", "classification", "units", "equation", "variable_definitions",
    "source_refs", "population_scope", "input_requirements", "data_quality_rules", "algorithm", "parameter_set",
    "assumptions", "known_limitations", "validation_protocol", "software_test_status",
    "scientific_validation_status", "uncertainty_statement", "last_reviewed",
)
CLASSES = ("OBSERVED", "DERIVED", "MODELLED", "EXPERIMENTAL")
EVIDENCE_LABELS = ("IDENTITY", "CONTROLLED", "LIMITED", "UNVERIFIED")
PHASE_ONE_METRICS = ("M001", "M002", "M003", "M004")   # spec 7: nothing else is approved in Phase One


class RegistryError(ValueError):
    pass


def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, (str, list, dict)) and len(v) == 0)


@lru_cache(maxsize=1)
def bibliography() -> dict[str, dict]:
    return yaml.safe_load((REGISTRY_DIR / "bibliography.yaml").read_text())


@lru_cache(maxsize=1)
def states() -> dict[str, dict]:
    return yaml.safe_load((REGISTRY_DIR / "states.yaml").read_text())


def problems(entry: dict) -> list[str]:
    """Every way an entry fails the contract. Empty means complete."""
    out = [f"{f} is missing or empty" for f in CONTRACT_FIELDS if f not in entry or _empty(entry[f])]
    if entry.get("classification") not in CLASSES:
        out.append(f"classification {entry.get('classification')!r} is not one of {CLASSES}")
    if entry.get("evidence_label") not in EVIDENCE_LABELS:
        out.append(f"evidence_label {entry.get('evidence_label')!r} is not one of {EVIDENCE_LABELS}")
    bib = bibliography()
    for ref in entry.get("source_refs") or []:
        if not isinstance(ref, dict) or ref.get("id") not in bib or _empty(ref.get("role")):
            out.append(f"source_ref {ref!r} does not resolve to the bibliography with a role")
    return out


@lru_cache(maxsize=1)
def entries() -> dict[str, dict]:
    out = {}
    for path in sorted((REGISTRY_DIR / "metrics").glob("*.yaml")):
        entry = yaml.safe_load(path.read_text())
        entry["documentation_path"] = str(path.relative_to(REGISTRY_DIR.parent))
        if entry.get("metric_id") != path.stem:
            raise RegistryError(f"{path.name} declares metric_id {entry.get('metric_id')!r}")
        out[entry["metric_id"]] = entry
    extra = set(out) - set(PHASE_ONE_METRICS)
    if extra:
        raise RegistryError(f"registry holds metrics not approved for Phase One: {sorted(extra)}")
    return out


def entry(metric_id: str) -> dict:
    try:
        return entries()[metric_id]
    except KeyError:
        raise RegistryError(f"{metric_id} has no register entry") from None


def displayable(metric_id: str, version: str) -> bool:
    e = entries().get(metric_id)
    return e is not None and str(e["version"]) == version and not problems(e)


def with_sources(e: dict) -> dict:
    """The entry with each source reference expanded to its citation, DOI and verification status."""
    bib = bibliography()
    return {**e, "source_refs": [{**r, **bib.get(r["id"], {})} for r in e["source_refs"]]}


def sync_definitions(c: Connection) -> None:
    """Mirror complete entries into metric_definitions, keyed by (metric_id, version)."""
    for metric_id, e in entries().items():
        if problems(e):
            continue
        c.execute(delete(metric_definitions).where(metric_definitions.c.metric_id == metric_id,
                                                   metric_definitions.c.version == str(e["version"])))
        c.execute(insert(metric_definitions).values(
            metric_id=metric_id, version=str(e["version"]), classification=e["classification"],
            units=e["units"], formula=e["equation"], evidence_status=e["scientific_validation_status"],
            documentation_path=e["documentation_path"],
            source_ref_json=json.dumps([r["id"] for r in e["source_refs"]])))
