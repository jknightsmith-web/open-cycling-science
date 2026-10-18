"""Canonical data structures shared by importers, timeline and metrics."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

CHANNELS = ("power", "heart_rate", "cadence", "speed", "distance", "temperature")


class State(str, Enum):
    """Validity state of one channel value (spec 5.2)."""
    OBSERVED = "observed"
    MISSING = "missing"
    INVALID = "invalid"
    INFERRED = "inferred"  # not permitted for any channel in Phase One


@dataclass(frozen=True)
class Reading:
    value: Optional[float]
    state: State

    def __post_init__(self):
        if (self.value is None) != (self.state is not State.OBSERVED):
            raise ValueError("Only observed readings carry a value")


MISSING = Reading(None, State.MISSING)
INVALID = Reading(None, State.INVALID)


@dataclass(frozen=True)
class RawRecord:
    """One record as an importer found it. Absent channels are missing.

    `fields` maps channel name to a numeric value, or to None when the field
    was present but carried an invalid sentinel.
    """
    timestamp_s: float
    fields: dict[str, Optional[float]] = field(default_factory=dict)


@dataclass(frozen=True)
class TimerEvent:
    timestamp_s: float
    kind: str  # "start" | "stop" (stop_all maps to stop)


@dataclass
class RawActivity:
    source_format: str
    records: list[RawRecord]
    timer_events: list[TimerEvent] = field(default_factory=list)
    device_timer_s: Optional[float] = None
    utc_offset_s: Optional[float] = None
    simulated_channels: frozenset[str] = frozenset()
    sensor_identity: dict[str, dict] = field(default_factory=dict)
    original_fields: list[dict] = field(default_factory=list)   # per record, as decoded
    metadata: dict = field(default_factory=dict)                 # platform, sport, devices


@dataclass(frozen=True)
class Interval:
    """Half open [start_s, end_s) with one reading per channel."""
    start_s: float
    end_s: float
    readings: dict[str, Reading]
    is_gap: bool = False

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def reading(self, channel: str) -> Reading:
        return self.readings.get(channel, MISSING)
