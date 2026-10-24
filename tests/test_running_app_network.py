"""Acceptance 16 and spec 8.5 on the running application, not the test client.

Starts the real server (uvicorn, `python -m backend.api`) in a separate
process under `netwatch.py`, which records every socket connect, bind, send
and name lookup made inside that process. Drives every workflow over HTTP on
127.0.0.1: import, duplicate confirmation, every read screen's API, settings,
all three exports, download, deletion preview and deletion, delete everything
and archive restore. Then requires that every recorded address is loopback,
and that the log is not empty (so the hook was active).
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from library_fixtures import T0, fenix, hub, whoosh
from netwatch import offenders
from ownership_helpers import gps_ride

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, tmp: Path):
        self.port = free_port()
        self.log = tmp / "net.jsonl"
        env = {**os.environ, "OCS_DATA_ROOT": str(tmp / "data"), "OCS_PORT": str(self.port)}
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "tests" / "netwatch.py"), str(self.log), "-m", "backend.api"],
                                     cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                self.get("/api/system")
                return
            except OSError:
                time.sleep(0.2)
        self.proc.kill()
        raise RuntimeError(self.proc.stdout.read().decode())

    def req(self, method: str, path: str, body: bytes | None = None, ctype: str = "application/octet-stream"):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, method=method,
                                   headers={"Content-Type": ctype} if body is not None else {})
        with urllib.request.urlopen(r, timeout=120) as resp:
            data = resp.read()
            return json.loads(data) if resp.headers.get("content-type", "").startswith("application/json") else data

    def get(self, path):
        return self.req("GET", path)

    def post_json(self, path, doc, method="POST"):
        return self.req(method, path, json.dumps(doc).encode(), "application/json")

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=30)


@pytest.fixture
def server(tmp_path):
    s = Server(tmp_path)
    yield s
    s.stop()


def test_every_workflow_on_the_running_server_stays_on_loopback(server, tmp_path):
    s = server
    ids = {}
    for name, data in [("fenix8.fit", fenix(900, start=T0)), ("hub.tcx", hub(895, start=T0 + 1)),
                       ("mywhoosh.fit", whoosh(890, start=T0 + 3)), ("gps.fit", gps_ride(T0 + 86400)),
                       ("broken.fit", b"\x0e\x10not fit")]:
        out = s.req("POST", f"/api/imports?filename={name}", data)["outcomes"][0]
        ids[name] = out.get("activity_id")
    [g] = [g for g in s.get("/api/duplicate-groups") if g["status"] == "proposed"]
    sel = {"timer": ids["fenix8.fit"], "power": ids["hub.tcx"], "heart_rate": ids["fenix8.fit"],
           "cadence": ids["mywhoosh.fit"], "speed": ids["mywhoosh.fit"], "distance": ids["mywhoosh.fit"], "temperature": None}
    ride = s.post_json(f"/api/duplicate-groups/{g['id']}/confirm", {"selection": sel})["ride_id"]
    aid = ids["gps.fit"]
    for path in ["/", "/library", f"/activities/{aid}", "/catalogue", "/catalogue/M004", "/api/activities?limit=50",
                 f"/api/activities/{aid}", f"/api/activities/{aid}/samples?limit=60",
                 f"/api/activities/{aid}/series?channel=power", f"/api/rides/{ride}", "/api/science/metrics",
                 "/api/science/metrics/M002", "/api/science/states", "/api/imports", "/api/system",
                 f"/api/aggregates?start_utc=0&end_utc=4000000000",
                 "/api/aggregates/weekly?tz=Europe/London&first_day=2025-10-06&last_day=2025-10-19"]:
        s.get(path)
    s.post_json("/api/settings", {"display_time_zone": "Europe/London", "week_start": "monday"}, method="PUT")
    for kind in ("originals", "derived", "archive"):
        s.req("POST", f"/api/exports?kind={kind}", b"")
    archive = s.get("/api/export/archive")
    assert archive[:2] == b"PK"
    assert s.get(f"/api/activities/{aid}/deletion")["vault_object_removed"]
    assert s.req("DELETE", f"/api/activities/{aid}")["committed"]
    token = s.get("/api/data/delete-all")["token"]
    s.post_json("/api/data/delete-all", {"token": token})
    report = s.req("POST", "/api/restore", archive, "application/zip")
    assert report["recompute_check"]["status"] == "passed"
    assert len(s.get("/api/activities?limit=50")["items"]) == 4
    s.stop()
    events = [json.loads(line) for line in s.log.read_text().splitlines()]
    assert any(e["event"] == "socket.bind" and e["host"] == "127.0.0.1" for e in events)   # the hook saw the server
    assert offenders(str(s.log)) == []


def test_netwatch_records_a_non_loopback_address(tmp_path):
    log = tmp_path / "probe.jsonl"
    subprocess.run([sys.executable, str(ROOT / "tests" / "netwatch.py"), str(log), "-m", "netwatch_probe"],
                   cwd=ROOT / "tests", check=True, timeout=60)
    assert [e["host"] for e in offenders(str(log))] == ["192.0.2.1"]
