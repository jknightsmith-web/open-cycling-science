"""Design 06 section 6: API additions B1 to B8."""
import pytest
from fastapi.testclient import TestClient

from backend.api import app as app_module
from backend.api.app import create_app
from backend.library import Library
from library_fixtures import T0, fenix, hub


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Library(tmp_path / "data")))


def upload(client, data, name):
    return client.post("/api/imports", params={"filename": name}, content=data).json()["outcomes"][0]


def test_import_log_lists_failures_and_links_activities(client):
    ok = upload(client, fenix(), "f.fit")
    upload(client, b"<?xml version='1.0'?><TrainingCenterDatabase/>", "bad.tcx")
    log = client.get("/api/imports").json()
    assert log["total"] == 2
    by_name = {r["original_filename"]: r for r in log["items"]}
    assert by_name["f.fit"]["activity_id"] == ok["activity_id"] and by_name["f.fit"]["error"] is None
    assert by_name["bad.tcx"]["validation_status"] == "failed" and by_name["bad.tcx"]["error"]["code"]


def test_activity_page_has_presence_flags_group_and_ride(client):
    f, h = upload(client, fenix(), "f.fit"), upload(client, hub(), "h.tcx")
    page = client.get("/api/activities", params={"limit": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    rows = {r["id"]: r for r in client.get("/api/activities").json()["items"]}
    hr = rows[h["activity_id"]]
    assert hr["channels"]["power"] == {"present": True, "origin": "measured"}
    assert hr["channels"]["heart_rate"]["present"] is False
    assert hr["group"] == {"id": h["group_id"], "status": "proposed", "membership": "member"}
    sel = {k: v["activity_id"] for k, v in client.get(f"/api/duplicate-groups/{h['group_id']}").json()["selection_prefill"].items()}
    ride_id = client.post(f"/api/duplicate-groups/{h['group_id']}/confirm", json={"selection": sel}).json()["ride_id"]
    rows = {r["id"]: r for r in client.get("/api/activities").json()["items"]}
    assert rows[f["activity_id"]]["ride_id"] == rows[h["activity_id"]]["ride_id"] == ride_id
    ride = client.get(f"/api/rides/{ride_id}").json()
    assert ride["members"] == [f["activity_id"], h["activity_id"]]


def test_series_endpoint_returns_runs_and_breaks(client):
    from fit_encoder import activity_file
    recs = [{"t": T0 + i, "power": 200} for i in range(30) if not 10 <= i < 15]
    aid = upload(client, activity_file(recs), "g.fit")["activity_id"]
    s = client.get(f"/api/activities/{aid}/series", params={"channel": "power"}).json()
    assert s["kind"] == "display_envelope" and len(s["runs"]) == 2
    assert s["breaks"][0]["reason"] == "gap" and s["breaks"][0]["start"] == pytest.approx(T0 + 10)
    assert client.get(f"/api/activities/{aid}/series", params={"channel": "watts"}).status_code == 422


def test_weekly_totals_follow_the_display_time_zone(client):
    # 23:30 UTC on Sunday 2025-10-12 is Monday 00:30 in Berlin, so the ride changes week but not value.
    start = 1760311800
    upload(client, fenix(600, start=start), "late.fit")
    params = {"first_day": "2025-10-06", "last_day": "2025-10-19"}
    utc = client.get("/api/aggregates/weekly", params={**params, "tz": "UTC"}).json()
    berlin = client.get("/api/aggregates/weekly", params={**params, "tz": "Europe/Berlin"}).json()
    assert [w["week"] for w in utc] == ["2025-W41", "2025-W42"]
    assert [w["ride_count"] for w in utc] == [1, 0] and [w["ride_count"] for w in berlin] == [0, 1]
    assert utc[0]["duration_s"] == berlin[1]["duration_s"] == 600
    assert client.get("/api/aggregates/weekly", params={**params, "tz": "Mars/Base"}).status_code == 422


def test_settings_persist_and_validate(client):
    assert client.get("/api/settings").json() == {"display_time_zone": None, "week_start": "monday"}
    assert client.put("/api/settings", json={"display_time_zone": "Australia/Sydney"}).status_code == 200
    assert client.get("/api/settings").json()["display_time_zone"] == "Australia/Sydney"
    assert client.put("/api/settings", json={"display_time_zone": "Nowhere/City"}).status_code == 422
    assert client.put("/api/settings", json={"week_start": "sunday"}).status_code == 422


def test_system_reports_location_sizes_and_loopback(client):
    upload(client, fenix(), "f.fit")
    s = client.get("/api/system").json()
    assert s["host"] == "127.0.0.1" and s["vault_objects"] == 1 and s["vault_bytes"] > 0 and s["database_bytes"] > 0
    assert [r["metric_id"] for r in s["registry"]] == ["M001", "M002", "M003", "M004"]


def test_frontend_served_with_deep_link_fallback(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(app_module, "FRONTEND_DIST", dist)
    c = TestClient(create_app(Library(tmp_path / "data")))
    assert "id=root" in c.get("/activities/12").text
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/api/nothing").status_code == 404


def test_openapi_schema_covers_every_api_route(client):
    schema = client.get("/openapi.json").json()
    for path in ("/api/imports", "/api/activities", "/api/activities/{aid}/series", "/api/aggregates/weekly",
                 "/api/settings", "/api/system", "/api/duplicate-groups/{gid}/confirm", "/api/rides/{ride_id}"):
        assert path in schema["paths"], path
