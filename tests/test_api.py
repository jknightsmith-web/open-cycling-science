"""Local API and science catalogue (acceptance 1 binding, 6 through the API, 12)."""
import re

import pytest
from fastapi.testclient import TestClient

from backend.api import __main__ as server
from backend.api.app import create_app
from backend.library import Library
from backend.science import registry
from backend.storage.schema import SELECTABLE_FIELDS
from fit_encoder import INVALID, activity_file
from library_fixtures import T0, fenix, hub

REQUIRED = {"metric_id", "version", "classification", "units", "state", "coverage", "parameters",
            "input_revision", "source_sha256", "register_url"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Library(tmp_path / "data")))


def upload(client, data, name):
    r = client.post("/api/imports", params={"filename": name}, content=data,
                    headers={"content-type": "application/octet-stream"})
    assert r.status_code == 200
    return r.json()["outcomes"][0]


def test_server_binds_to_loopback_only():
    assert server.HOST == "127.0.0.1"


def test_every_metric_value_opens_its_register_entry(client):
    aid = upload(client, fenix(), "f.fit")["activity_id"]
    metrics = client.get(f"/api/activities/{aid}").json()["metrics"]
    assert {m["metric_id"] for m in metrics} == set(registry.PHASE_ONE_METRICS)
    for m in metrics:
        assert REQUIRED <= set(m) and m["state"] != "not_displayable"
        entry = client.get(m["register_url"]).json()
        assert entry["problems"] == [] and all(f in entry for f in registry.CONTRACT_FIELDS)
        page = client.get(m["catalogue_url"])
        assert page.status_code == 200 and m["metric_id"] in page.text
        assert m["uncertainty"] == "not quantified"


def test_value_hidden_when_entry_incomplete(client, monkeypatch):
    aid = upload(client, fenix(), "f.fit")["activity_id"]
    broken = {k: v for k, v in registry.entry("M002").items() if k != "assumptions"}
    monkeypatch.setitem(registry.entries(), "M002", broken)
    m = next(m for m in client.get(f"/api/activities/{aid}").json()["metrics"] if m["metric_id"] == "M002")
    assert m["value"] is None and m["state"] == "not_displayable"


def test_samples_endpoint_keeps_zero_missing_and_invalid_apart(client):
    recs = [{"t": T0, "power": 0, "heart_rate": 0}, {"t": T0 + 1, "power": INVALID}, {"t": T0 + 2, "power": 210}]
    aid = upload(client, activity_file(recs), "s.fit")["activity_id"]
    s = client.get(f"/api/activities/{aid}/samples").json()
    assert s[0]["channels"]["power"] == {"value": 0.0, "validity": "observed"}
    assert s[0]["channels"]["heart_rate"] == {"value": None, "validity": "invalid"}
    assert s[1]["channels"]["power"] == {"value": None, "validity": "invalid"}
    assert s[1]["channels"]["heart_rate"] == {"value": None, "validity": "missing"}


def test_duplicate_workflow_over_http(client):
    f, h = upload(client, fenix(), "f.fit"), upload(client, hub(), "h.tcx")
    gid = h["group_id"]
    g = client.get(f"/api/duplicate-groups/{gid}").json()
    assert g["status"] == "proposed" and g["evidence"]["pairs"][0]["overlap_fraction"] == pytest.approx(1.0)
    selection = {k: v["activity_id"] for k, v in g["selection_prefill"].items()}
    assert set(selection) == set(SELECTABLE_FIELDS)
    rng = {"start_utc": T0 - 60, "end_utc": T0 + 7200}
    assert client.get("/api/aggregates", params=rng).json()["ride_count"] == 2
    r = client.post(f"/api/duplicate-groups/{gid}/confirm", json={"selection": selection})
    assert r.status_code == 200
    ride = client.get(f"/api/rides/{r.json()['ride_id']}").json()
    assert ride["kind"] == "group" and ride["sources"] == selection
    assert {m["metric_id"] for m in ride["metrics"]} == set(registry.PHASE_ONE_METRICS)
    assert client.get("/api/aggregates", params=rng).json()["ride_count"] == 1
    assert client.post(f"/api/duplicate-groups/{gid}/reject").status_code == 409   # confirmed groups reopen first
    assert client.post(f"/api/duplicate-groups/{gid}/reopen").status_code == 200
    assert client.get("/api/aggregates", params=rng).json()["ride_count"] == 2


def test_catalogue_lists_every_entry_and_needs_no_network_assets(client):
    page = client.get("/science").text
    for metric_id in registry.PHASE_ONE_METRICS:
        assert f"/science/{metric_id}" in page
    for text in [page] + [client.get(f"/science/{m}").text for m in registry.PHASE_ONE_METRICS]:
        assert "<script" not in text and "<link" not in text
        assert not re.search(r"(src|href)=['\"]https?://(?!doi\.org/)", text)
    m4 = client.get("/science/M004").text
    for field in ("equation", "assumptions", "known limitations", "scientific validation status", "units"):
        assert field in m4
    assert "Highest observed" in m4 and "10.1007/s00421-021-04833-y" in m4
    assert client.get("/science/M099").status_code == 404
