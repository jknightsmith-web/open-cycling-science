"""WP7 registry: completeness (acceptance 12), agreement with code and with the register document."""
import re
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.canonical import timeline
from backend.library import Library
from backend.metrics import m002_m003_power, m004_mmp
from backend.science import registry
from backend.storage.schema import metric_definitions
from helpers import ride
from backend.library.metric_store import compute_activity_metrics

REGISTER_DOC = Path(__file__).resolve().parents[1] / "docs" / "spec" / "02_RESEARCH_REGISTER.md"


def test_phase_one_metrics_have_complete_entries_and_nothing_else():
    assert sorted(registry.entries()) == list(registry.PHASE_ONE_METRICS)
    for metric_id, e in registry.entries().items():
        assert registry.problems(e) == [], metric_id
        assert registry.displayable(metric_id, str(e["version"]))


def test_incomplete_entry_is_detected_and_not_displayable(monkeypatch):
    broken = {k: v for k, v in registry.entry("M002").items() if k != "known_limitations"}
    broken["classification"] = "MEASURED"
    probs = registry.problems(broken)
    assert "known_limitations is missing or empty" in probs and any("classification" in p for p in probs)
    monkeypatch.setitem(registry.entries(), "M002", broken)
    assert not registry.displayable("M002", "1.0")


def test_unknown_source_reference_is_a_problem():
    e = {**registry.entry("M004"), "source_refs": [{"id": "R99", "role": "made up"}]}
    assert any("R99" in p for p in registry.problems(e))


def test_entries_agree_with_the_code_that_computes_them():
    results = compute_activity_metrics(timeline.build_timeline(ride([200] * 10)))
    for r in results:
        e = registry.entry(r.metric_id)
        assert (str(e["version"]), e["classification"], e["units"]) == (r.version, r.classification, r.units)
    assert registry.entry("M001")["parameter_set"]["gap_tolerance_factor"] == timeline.GAP_TOLERANCE_FACTOR
    assert registry.entry("M002")["parameter_set"]["min_coverage"] == m002_m003_power.MIN_COVERAGE
    assert registry.entry("M003")["parameter_set"]["lower_bound_label_below"] == m002_m003_power.MIN_COVERAGE
    assert tuple(registry.entry("M004")["parameter_set"]["durations_s"]) == m004_mmp.DEFAULT_DURATIONS_S


def _register_rows(metric_id: str) -> dict[str, str]:
    text = REGISTER_DOC.read_text()
    block = text.split(f"### {metric_id} ", 1)[1].split("\n### ", 1)[0]
    return {m.group(1).strip(): m.group(2).strip() for m in re.finditer(r"^\| ([^|]+) \| (.+) \|$", block, re.M)}


@pytest.mark.parametrize("metric_id", registry.PHASE_ONE_METRICS)
def test_entries_agree_with_the_frozen_register_document(metric_id):
    rows, e = _register_rows(metric_id), registry.entry(metric_id)
    assert rows["metric_id, version"] == f"{metric_id}, {e['version']}"
    assert rows["classification"] == e["classification"]
    assert rows["units"].startswith(e["units"])
    assert rows["scientific_validation_status"].split(";")[0] == e["evidence_label"]
    doc_refs = set(re.findall(r"\b([RD]\d\d)\b", rows["source_refs"]))
    assert doc_refs == {r["id"] for r in e["source_refs"]} - {"definition"}


def test_every_cited_source_carries_its_verification_status():
    for e in registry.entries().values():
        for ref in registry.with_sources(e)["source_refs"]:
            assert ref["status"] and ref["citation"]
    assert registry.bibliography()["R12"]["status"] == "M"   # unconfirmed DOI stays visible


def test_definitions_are_mirrored_into_the_database(tmp_path):
    lib = Library(tmp_path / "data")
    with lib.engine.connect() as c:
        rows = c.execute(select(metric_definitions).order_by(metric_definitions.c.metric_id)).mappings().all()
    assert [(r["metric_id"], r["version"], r["classification"]) for r in rows] == [
        ("M001", "1.0", "DERIVED"), ("M002", "1.0", "DERIVED"), ("M003", "1.0", "DERIVED"), ("M004", "1.0", "DERIVED")]
    assert all(r["documentation_path"].startswith("registry/metrics/") for r in rows)
    Library(tmp_path / "data")   # reopening is idempotent
