"""WP9 endpoints: errors and refusals over HTTP (the happy path runs on the live server in
test_running_app_network.py)."""
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.library import Library
from library_fixtures import fenix, hub


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Library(tmp_path / "data")))


def upload(client, data, name):
    return client.post("/api/imports", params={"filename": name}, content=data).json()["outcomes"][0]


def test_export_list_download_and_remove(client):
    upload(client, fenix(), "f.fit")
    e = client.post("/api/exports", params={"kind": "derived"}).json()
    assert [x["name"] for x in client.get("/api/exports").json()] == [e["name"]]
    r = client.get(f"/api/exports/{e['name']}")
    assert r.status_code == 200 and r.content[:2] == b"PK" and r.headers["content-type"] == "application/zip"
    assert client.delete(f"/api/exports/{e['name']}").json() == {"status": "deleted"}
    assert client.get("/api/exports").json() == []
    assert client.post("/api/exports", params={"kind": "everything"}).status_code == 422
    assert client.get("/api/exports/..%2F..%2Fdb%2Fcycling.db").status_code == 404     # only export names


def test_restore_into_a_library_with_data_is_refused(client):
    upload(client, fenix(), "f.fit")
    arch = client.get("/api/export/archive").content
    r = client.post("/api/restore", content=arch)
    assert r.status_code == 409 and "empty library" in r.json()["detail"]
    assert client.post("/api/restore", content=b"junk").status_code == 409


def test_deletion_preview_then_delete_and_unknown_ids(client):
    a = upload(client, fenix(), "f.fit")
    b = upload(client, hub(), "h.tcx")
    p = client.get(f"/api/activities/{a['activity_id']}/deletion").json()
    assert p["committed"] is False and p["groups"][0]["effect"] == "dissolved"
    assert len(client.get("/api/activities").json()["items"]) == 2          # preview changed nothing
    d = client.delete(f"/api/activities/{a['activity_id']}").json()
    assert d["committed"] and d["groups"] == p["groups"]
    assert client.delete(f"/api/activities/{a['activity_id']}").status_code == 404
    assert client.get("/api/imports/999/deletion").status_code == 404
    assert client.delete(f"/api/imports/{b['source_file_id']}").json()["activity_id"] == b["activity_id"]


def test_delete_everything_needs_the_token(client):
    upload(client, fenix(), "f.fit")
    assert client.post("/api/data/delete-all", json={"token": "wrong"}).status_code == 409
    p = client.get("/api/data/delete-all").json()
    assert p["counts"]["recordings"] == 1 and p["cannot_delete"]
    out = client.post("/api/data/delete-all", json={"token": p["token"]}).json()
    assert out["counts"]["recordings"] == 1
    assert client.get("/api/activities").json()["total"] == 0
    assert upload(client, fenix(), "again.fit")["status"] == "imported"           # empty install works


def test_rides_needing_review_lists_a_ride_whose_source_was_deleted(client):
    a, b = upload(client, fenix(), "f.fit"), upload(client, hub(), "h.tcx")
    c = upload(client, fenix(serial=5, power=190), "g.fit")
    g = client.get("/api/duplicate-groups").json()[0]
    sel = {"timer": a["activity_id"], "power": b["activity_id"], "heart_rate": a["activity_id"],
           "cadence": a["activity_id"], "speed": None, "distance": None, "temperature": None}
    ride = client.post(f"/api/duplicate-groups/{g['id']}/confirm", json={"selection": sel}).json()["ride_id"]
    assert client.get("/api/rides-needing-review").json() == []
    client.delete(f"/api/activities/{b['activity_id']}")
    assert client.get("/api/rides-needing-review").json() == [ride]
    r = client.get(f"/api/rides/{ride}").json()
    assert r["needs_review"] and r["sources"]["power"] is None
    assert any(h["source_deleted"] for h in r["selection_history"])
