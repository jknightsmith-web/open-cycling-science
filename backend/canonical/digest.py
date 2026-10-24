"""Canonical timeline digest: the `input_revision` of activity scope metric runs (architecture 5).

The digest covers everything a metric can read from a timeline: timer
segments, timer source, every interval with its readings and gap flag, and
the simulated channel set. Floats are written with `repr`, which round trips
exactly, so equal digests mean bit identical inputs.
"""
from __future__ import annotations

import hashlib
import json

from .model import CHANNELS
from .timeline import Timeline


def timeline_digest(tl: Timeline) -> str:
    h = hashlib.sha256()

    def put(obj) -> None:
        h.update(json.dumps(obj, separators=(",", ":")).encode())
        h.update(b"\n")

    put({"timer_source": tl.timer_source,
         "segments": [[repr(a), repr(b)] for a, b in tl.segments],
         "nominal_interval_s": repr(tl.nominal_interval_s),
         "simulated": sorted(tl.simulated_channels)})
    for iv in tl.intervals:
        put([repr(iv.start_s), repr(iv.end_s), iv.is_gap,
             [[iv.reading(ch).state.value, repr(iv.reading(ch).value)] for ch in CHANNELS]])
    return h.hexdigest()
