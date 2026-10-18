"""WP3: FIT, TCX and zip importers on synthetic files (real file checks need rider files)."""
import io
import zipfile

import pytest

from backend.canonical.model import State
from backend.canonical.timeline import TIMER_ASSUMED_CONTINUOUS, TIMER_DEVICE_EVENTS, build_timeline
from backend.importers import archive, fit, tcx
from backend.importers.detect import sniff
from backend.importers.errors import ImportFailure
from backend.metrics import m001_duration
from backend.metrics.m002_m003_power import mean_power
from fit_encoder import EVENT_START, EVENT_STOP_ALL, INVALID, SUB_INDOOR, SUB_VIRTUAL, activity_file

T = 1_760_000_000


def steady(n=10, **extra):
    return [{"t": T + i, "power": 200, "heart_rate": 130, "cadence": 90, **extra} for i in range(n)]


def test_fit_round_trip_values_and_timer_events():
    data = activity_file(steady(15), events=[(T, EVENT_START), (T + 5, EVENT_STOP_ALL), (T + 10, EVENT_START)],
                         session={"total_timer_time": 10, "sport": 2, "sub_sport": SUB_INDOOR})
    raw = fit.parse(data)
    assert sniff(data) == "fit" and len(raw.records) == 15
    assert raw.records[0].fields == {"power": 200.0, "heart_rate": 130.0, "cadence": 90.0}
    tl = build_timeline(raw)
    assert tl.timer_source == TIMER_DEVICE_EVENTS and tl.timer_s == 10
    r = m001_duration.compute(tl)
    assert r.details["device_timer_s"] == 10 and "device_timer_mismatch" not in tl.flags
    assert raw.simulated_channels == frozenset()


def test_fit_sentinel_is_invalid_and_absent_field_is_missing():
    recs = steady(4) + [{"t": T + 4, "power": INVALID, "heart_rate": 131}, {"t": T + 5, "heart_rate": 131},
                        {"t": T + 6, "power": 0, "heart_rate": INVALID}]
    tl = build_timeline(fit.parse(activity_file(recs)))
    assert tl.intervals[4].reading("power").state is State.INVALID
    assert tl.intervals[5].reading("power").state is State.MISSING
    assert tl.intervals[6].reading("power").value == 0
    assert tl.intervals[6].reading("power").state is State.OBSERVED
    assert tl.intervals[6].reading("heart_rate").state is State.INVALID
    assert tl.intervals[4].reading("cadence").state is State.MISSING


def test_fit_compressed_timestamps_decode_to_the_same_times():
    plain = fit.parse(activity_file(steady(40)))
    compressed = fit.parse(activity_file(steady(20), compress_after_first=True))
    assert [r.timestamp_s for r in compressed.records] == [r.timestamp_s for r in plain.records[:20]]


def test_fit_utc_offset_and_virtual_activity():
    raw = fit.parse(activity_file(steady(5, speed=8.5, distance=12.0), local_offset_s=7200,
                                  session={"total_timer_time": 5, "sport": 2, "sub_sport": SUB_VIRTUAL}))
    assert raw.utc_offset_s == 7200
    assert raw.simulated_channels == {"speed", "distance"}   # spec 5.6
    assert raw.records[0].fields["speed"] == pytest.approx(8.5)


def test_fit_device_identity_per_channel():
    raw = fit.parse(activity_file(steady(3), devices=[{"device_index": 1, "device_type": 120, "manufacturer": 1, "product": 2},
                                                      {"device_index": 2, "device_type": 11, "manufacturer": 73, "product": 1}]))
    assert raw.sensor_identity["heart_rate"]["match"]["device_type"] == 120
    assert raw.sensor_identity["power"]["match"]["manufacturer"] == "wattbike"


def test_fit_corrupt_crc_is_rejected():
    data = bytearray(activity_file(steady(5)))
    data[30] ^= 0xFF
    with pytest.raises(ImportFailure) as e:
        fit.parse(bytes(data))
    assert e.value.code == "corrupt"


def test_fit_truncated_is_rejected():
    with pytest.raises(ImportFailure):
        fit.parse(activity_file(steady(5))[:-20])


TCX = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
  xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
 <Activities><Activity Sport="Biking"><Id>2025-10-09T08:53:20Z</Id>
  <Lap StartTime="2025-10-09T08:53:20Z"><TotalTimeSeconds>{total}</TotalTimeSeconds><Track>{points}</Track></Lap>
  <Creator><Name>Synthetic</Name></Creator>
 </Activity></Activities>
</TrainingCenterDatabase>"""


def tp(sec, watts=None, hr=None, cad=None):
    ext = f"<Extensions><ns3:TPX><ns3:Watts>{watts}</ns3:Watts></ns3:TPX></Extensions>" if watts is not None else ""
    hr_el = f"<HeartRateBpm><Value>{hr}</Value></HeartRateBpm>" if hr is not None else ""
    cad_el = f"<Cadence>{cad}</Cadence>" if cad is not None else ""
    return f"<Trackpoint><Time>2025-10-09T08:53:{20 + sec:02d}.000Z</Time>{hr_el}{cad_el}{ext}</Trackpoint>"


def test_tcx_power_and_missing_watts():
    pts = "".join(tp(i, 200, 130, 90) for i in range(8)) + tp(8, None, 130, 90) + tp(9, 200, 130, 90)
    data = TCX.format(total=10, points=pts).encode()
    raw = tcx.parse(data)
    assert sniff(data) == "tcx" and raw.device_timer_s == 10
    tl = build_timeline(raw)
    assert tl.timer_source == TIMER_ASSUMED_CONTINUOUS            # D3
    assert tl.intervals[8].reading("power").state is State.MISSING
    mp = mean_power(tl)
    assert mp.details["coverage"] == pytest.approx(0.9)
    assert mp.state == "insufficient_coverage" and mp.value is None     # 90% < 95%, missing not zero


def test_tcx_fractional_timestamps():
    pts = "".join(f"<Trackpoint><Time>2025-10-09T08:53:20.{ms:03d}Z</Time><Extensions><ns3:TPX><ns3:Watts>150</ns3:Watts>"
                  f"</ns3:TPX></Extensions></Trackpoint>" for ms in (0, 250, 500, 750))
    tl = build_timeline(tcx.parse(TCX.format(total=1, points=pts).encode()))
    assert tl.nominal_interval_s == pytest.approx(0.25) and tl.timer_s == pytest.approx(1.0)


def test_tcx_entity_expansion_is_refused():
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><TrainingCenterDatabase>&b;</TrainingCenterDatabase>'
    with pytest.raises(ImportFailure):
        tcx.parse(bomb)


def zipped(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(name, data)
    return buf.getvalue()


def test_zip_returns_only_activity_members():
    f = activity_file(steady(3))
    out = archive.members(zipped([("a/ride.fit", f), ("notes.txt", b"x"), ("b/hub.TCX", b"<x/>")]))
    assert [n for n, _ in out] == ["a/ride.fit", "b/hub.TCX"] and out[0][1] == f


@pytest.mark.parametrize("name", ["../escape.fit", "/abs/ride.fit", "C:/ride.fit"])
def test_zip_path_traversal_rejected(name):
    with pytest.raises(ImportFailure) as e:
        archive.members(zipped([(name, b"x")]))
    assert e.value.code == "unsafe_archive"


def test_zip_bomb_ratio_rejected():
    with pytest.raises(ImportFailure):
        archive.members(zipped([("big.fit", b"\0" * 5_000_000)]))


def test_unknown_content_rejected_regardless_of_name():
    with pytest.raises(ImportFailure):
        sniff(b"MZ\x90\x00 executable pretending to be ride.fit")
