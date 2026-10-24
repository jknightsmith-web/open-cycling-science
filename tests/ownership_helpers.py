"""A library with every kind of record WP9 must export, restore and delete. Synthetic only.

Ride A: Fenix, Hub and MyWhoosh recordings, confirmed with power from the Hub,
heart rate from the Fenix and cadence from MyWhoosh, then a fourth recording
of the same ride pending. Ride B: two recordings, proposed. A solo ride with
GPS positions and a marker filename. A validity case file (gap, missing,
invalid, suspect zero, observed zero, pause). A file that fails to parse. A
ZIP holding one recording. Saved preferences and display settings.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from sqlalchemy import select

from backend.library import Library, rides
from backend.library.ingest import import_bytes
from backend.storage.schema import SELECTABLE_FIELDS, app_settings, metadata
from fit_encoder import EVENT_START, EVENT_STOP_ALL, INVALID, activity_file
from library_fixtures import T0, fenix, hub, whoosh

MARKER = "ZQX-MARKER-7f3a9c41"
DAY = 86400
LAT, LONG = 612_345_678, -1_234_567   # semicircles; distinctive values to search for


def clock(start: int = 1_800_000_000):
    it = iter(range(start, start + 10_000_000))
    return lambda: float(next(it))


def new_library(root: Path) -> Library:
    return Library(root, now=clock())


def imp(lib: Library, data: bytes, name: str):
    out = import_bytes(lib, data, name)
    assert all(o.status in ("imported", "failed") for o in out), out
    return out[0]


def gps_ride(start: int) -> bytes:
    return activity_file([{"t": start + i, "power": 180 + i % 7, "heart_rate": 130,
                           "position_lat": LAT + i, "position_long": LONG - i} for i in range(400)],
                         file_id={"manufacturer": 1, "product": 4536, "serial_number": 5_550_001})


def validity_ride(start: int) -> bytes:
    recs = []
    for i in range(600):
        if 100 <= i < 130:
            continue
        r = {"t": start + i, "power": 220, "heart_rate": 150, "cadence": 88}
        if 200 <= i < 220:
            r.pop("power")
        if 300 <= i < 310:
            r["power"] = INVALID
        if 400 <= i < 410:
            r["power"] = 0
        if i == 5:
            r["heart_rate"] = 0
        if 500 <= i < 505:
            r["power"], r["cadence"] = 0, 0
        recs.append(r)
    return activity_file(recs, events=[(start, EVENT_START), (start + 450, EVENT_STOP_ALL), (start + 480, EVENT_START)],
                         file_id={"manufacturer": 1, "product": 4536, "serial_number": 99})


def selection(**by_field):
    return {f: by_field.get(f) for f in SELECTABLE_FIELDS}


def build(lib: Library) -> dict:
    ids: dict = {}
    ids["fenix"] = imp(lib, fenix(1800, start=T0, power=200), "fenix8.fit").activity_id
    ids["hub"] = imp(lib, hub(1795, start=T0 + 1, power=210), "hub.tcx").activity_id
    w = imp(lib, whoosh(1790, start=T0 + 3, power=205), "mywhoosh.fit")
    ids["whoosh"], ids["group_a"] = w.activity_id, w.group_id
    with lib.engine.begin() as c:
        ids["ride_a"] = rides.confirm(c, ids["group_a"], selection(
            timer=ids["fenix"], power=ids["hub"], heart_rate=ids["fenix"], cadence=ids["whoosh"],
            speed=ids["whoosh"], distance=ids["whoosh"]), lib.now())
    late = imp(lib, fenix(1700, start=T0 + 20, power=199, serial=3_400_777), "edge840.fit")
    ids["pending"] = late.activity_id
    b1 = imp(lib, fenix(900, start=T0 + DAY, power=150, serial=1), "day2_garmin.fit")
    b2 = imp(lib, hub(905, start=T0 + DAY + 2, power=160), "day2_wattbike.tcx")
    ids["b1"], ids["b2"], ids["group_b"] = b1.activity_id, b2.activity_id, b2.group_id
    ids["gps"] = imp(lib, gps_ride(T0 + 2 * DAY), f"{MARKER}.fit").activity_id
    ids["validity"] = imp(lib, validity_ride(T0 + 3 * DAY), "validity_cases.fit").activity_id
    bad = bytearray(fenix(60, start=T0 + 4 * DAY, serial=42))
    bad[len(bad) // 2] ^= 0xFF
    ids["failed_sf"] = imp(lib, bytes(bad), "damaged.fit").source_file_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("rides/zipped ride.fit", fenix(300, start=T0 + 5 * DAY, power=170, serial=8))
    ids["zipped"] = imp(lib, buf.getvalue(), "export.zip").activity_id
    with lib.engine.begin() as c:
        rides.set_preferences(c, {"power": [{"source_format": "tcx"}], "heart_rate": [{"source_platform": "garmin"}]})
        c.execute(app_settings.insert().values(key="display_time_zone", value_json='"Europe/London"'))
    return ids


def dump(lib: Library) -> dict[str, list[dict]]:
    """Every row of every table, in primary key order."""
    out = {}
    with lib.engine.connect() as c:
        for t in metadata.sorted_tables:
            order = list(t.primary_key.columns) or list(t.columns)
            out[t.name] = [dict(r) for r in c.execute(select(t).order_by(*order)).mappings()]
    return out


def scan(root: Path, needles: list[bytes]) -> list[str]:
    """Every file under root (database, WAL and SHM included) whose bytes or path contain a needle."""
    hits = []
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root)).encode()
        for n in needles:
            if n in rel:
                hits.append(f"path {p.relative_to(root)} contains {n!r}")
        if p.is_file():
            data = p.read_bytes()
            for n in needles:
                if n in data:
                    hits.append(f"{p.relative_to(root)} contains {n!r}")
    return hits


def needles_for(sha256: str, *text: str) -> list[bytes]:
    out = [sha256.encode(), sha256.upper().encode(), bytes.fromhex(sha256)]
    for t in text:
        out += [t.encode("utf-8"), t.encode("utf-16-le")]
    return out
