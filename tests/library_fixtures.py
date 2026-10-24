"""Synthetic recordings of one ride by three sources, for WP6 tests. No rider data.

`fenix` has heart rate and cadence with power from a pedal meter, `hub` is a
TCX with power and cadence, `whoosh` is a MyWhoosh style FIT with simulated
speed and distance. Start offsets and lengths differ slightly, as separate
recorders would.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fit_encoder import activity_file

T0 = 1_760_000_000
TCX_HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<TrainingCenterDatabase '
            'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" '
            'xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">'
            '<Activities><Activity Sport="Biking"><Id>{id}</Id><Lap StartTime="{id}">'
            '<TotalTimeSeconds>{total}</TotalTimeSeconds><Track>')
TCX_TAIL = '</Track></Lap><Creator><Name>Wattbike Hub</Name></Creator></Activity></Activities></TrainingCenterDatabase>'


def _iso(t: float) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fenix(n: int = 600, start: int = T0, power: float = 200, serial: int = 3_400_001) -> bytes:
    return activity_file([{"t": start + i, "power": power, "heart_rate": 140, "cadence": 90} for i in range(n)],
                         file_id={"manufacturer": 1, "product": 4536, "serial_number": serial})


def whoosh(n: int = 590, start: int = T0 + 3, power: float = 205) -> bytes:
    return activity_file([{"t": start + i, "power": power, "cadence": 88, "speed": 9.0, "distance": 9.0 * i}
                          for i in range(n)],
                         file_id={"manufacturer": 331, "product": 1, "serial_number": 77})


def hub(n: int = 595, start: int = T0 + 1, power: int = 210, cadence: int = 91) -> bytes:
    pts = "".join(f"<Trackpoint><Time>{_iso(start + i)}</Time><Cadence>{cadence}</Cadence><Extensions><ns3:TPX>"
                  f"<ns3:Watts>{power}</ns3:Watts></ns3:TPX></Extensions></Trackpoint>" for i in range(n))
    return (TCX_HEAD.format(id=_iso(start), total=n) + pts + TCX_TAIL).encode()


def vault_digest(root: Path) -> dict[str, str]:
    """Path -> sha256 of every vault object, to prove no step alters a recording."""
    out = {}
    for p in sorted((root / "vault").rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out
