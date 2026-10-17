"""Channel validity classification (spec 5.2).

Physical ranges are engineering limits for rejecting corrupt values, not
physiological claims. HR 0 is invalid; power 0 and cadence 0 are observed.
"""
from __future__ import annotations

from typing import Optional

from .model import INVALID, MISSING, Reading, State

RANGES: dict[str, tuple[float, float]] = {
    "power": (0.0, 3000.0),
    "heart_rate": (20.0, 250.0),
    "cadence": (0.0, 250.0),
}


def classify(channel: str, present: bool, value: Optional[float]) -> Reading:
    if not present:
        return MISSING
    if value is None:
        return INVALID
    bounds = RANGES.get(channel)
    if bounds is not None and not (bounds[0] <= value <= bounds[1]):
        return INVALID
    return Reading(float(value), State.OBSERVED)
