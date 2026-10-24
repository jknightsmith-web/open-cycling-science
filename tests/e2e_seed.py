"""Seed a data root with synthetic recordings for the frontend end to end and performance tests.

    python tests/e2e_seed.py <data_root>            # scenario set for e2e
    python tests/e2e_seed.py <data_root> --perf 1000  # 1,000 activities plus one 3 h, 1 Hz ride

Everything is synthetic. No rider data.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.library import Library                       # noqa: E402
from backend.library.ingest import import_bytes             # noqa: E402
from fit_encoder import EVENT_START, EVENT_STOP_ALL, INVALID, activity_file  # noqa: E402
from library_fixtures import fenix, hub, whoosh             # noqa: E402

DAY = 86400
# Relative to now so the Overview's recent weeks contain the scenario rides.
RIDE_T0 = (int(time.time()) // DAY - 4) * DAY + 7 * 3600   # 07:00 UTC, four days ago


def scenario(lib: Library) -> dict:
    out = {}
    fenix_bytes = fenix(1800, start=RIDE_T0, power=200)
    out["fenix"] = import_bytes(lib, fenix_bytes, "fenix8.fit")[0].activity_id
    out["hub"] = import_bytes(lib, hub(1795, start=RIDE_T0 + 1, power=210, cadence=91), "hub.tcx")[0].activity_id
    w = import_bytes(lib, whoosh(1790, start=RIDE_T0 + 3, power=205), "mywhoosh.fit")[0]
    out["whoosh"], out["group"] = w.activity_id, w.group_id
    # A day later: one recording with every validity case the screens must keep apart.
    t0 = RIDE_T0 + DAY
    recs = []
    for i in range(600):
        if 100 <= i < 130:
            continue                                          # 30 s recording gap
        r = {"t": t0 + i, "power": 220, "heart_rate": 150, "cadence": 88}
        if 200 <= i < 220:
            r.pop("power")                                    # missing power
        if 300 <= i < 310:
            r["power"] = INVALID                              # invalid sentinel
        if 400 <= i < 410:
            r["power"] = 0                                    # suspect zero (cadence > 0)
        if i == 5:
            r["heart_rate"] = 0                               # HR 0 is invalid
        if 500 <= i < 505:
            r["power"] = 0
            r["cadence"] = 0                                  # coasting: observed zero
        recs.append(r)
    data = activity_file(recs, events=[(t0, EVENT_START), (t0 + 450, EVENT_STOP_ALL), (t0 + 480, EVENT_START)],
                         file_id={"manufacturer": 1, "product": 4536, "serial_number": 99})
    out["validity"] = import_bytes(lib, data, "validity_cases.fit")[0].activity_id
    # Two days later: power for only half the time, so mean power is unavailable and work is a lower bound.
    t1 = RIDE_T0 + 2 * DAY
    half = [{"t": t1 + i, "heart_rate": 140, **({"power": 180} if i < 300 else {})} for i in range(600)]
    out["low_coverage"] = import_bytes(lib, activity_file(half, file_id={"serial_number": 5}), "half_power.fit")[0].activity_id
    # Files for the import test (UI-03): one new, one byte identical to fenix8.fit, one corrupt.
    up = lib.root / "upload"
    up.mkdir(exist_ok=True)
    t2 = RIDE_T0 + 3 * DAY
    (up / "new_ride.fit").write_bytes(activity_file([{"t": t2 + i, "power": 190, "heart_rate": 135} for i in range(300)],
                                                    file_id={"serial_number": 6}))
    (up / "same_as_fenix.fit").write_bytes(fenix_bytes)
    damaged = bytearray(activity_file([{"t": t2 + DAY + i, "power": 100} for i in range(60)], file_id={"serial_number": 7}))
    damaged[len(damaged) // 2] ^= 0xFF                        # FIT header intact, CRC now fails
    (up / "corrupt.fit").write_bytes(bytes(damaged))
    out["upload_dir"] = str(up)
    return out


def perf(lib: Library, n: int) -> dict:
    began = time.perf_counter()
    for i in range(n):
        start = RIDE_T0 - (i + 1) * DAY // 2                  # two rides a day going back, never overlapping
        recs = [{"t": start + k, "power": 150 + (k % 60), "heart_rate": 130, "cadence": 85} for k in range(0, 1800, 5)]
        import_bytes(lib, activity_file(recs, file_id={"serial_number": 10_000 + i}), f"history_{i:04d}.fit")
    big = [{"t": RIDE_T0 + k, "power": 180 + (k % 120), "heart_rate": 140, "cadence": 88} for k in range(3 * 3600)]
    aid = import_bytes(lib, activity_file(big, file_id={"serial_number": 777}), "three_hours.fit")[0].activity_id
    return {"activities": n + 1, "three_hour_activity": aid, "seed_seconds": round(time.perf_counter() - began, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--perf", type=int, default=0)
    args = ap.parse_args()
    lib = Library(Path(args.root), now=time.time)
    info = perf(lib, args.perf) if args.perf else scenario(lib)
    (Path(args.root) / "seed.json").write_text(json.dumps(info))
    print(json.dumps(info))
