"""FIT activity importer using fitdecode (MIT, decision D8).

Mapping per architecture section 4. A field absent from a record's definition
is missing; a field carrying the FIT invalid sentinel (decoded as None) is
invalid. Values are never defaulted to zero.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Optional

import fitdecode

from ..canonical.model import RawActivity, RawRecord, TimerEvent
from .errors import ImportFailure
from .location import strip_location

PARSER_VERSION = f"fit-1.0+fitdecode-{fitdecode.__version__}"

RECORD_FIELDS = {  # channel -> FIT record field names in preference order
    "power": ("power",),
    "heart_rate": ("heart_rate",),
    "cadence": ("cadence",),
    "speed": ("enhanced_speed", "speed"),
    "distance": ("distance",),
    "temperature": ("temperature",),
}
TIMER_EVENT_TYPES = {"start": "start", "stop": "stop", "stop_all": "stop",
                     "stop_disable": "stop", "stop_disable_all": "stop"}
# ANT+ device types that can source a channel (FIT profile antplus_device_type)
CHANNEL_DEVICE_TYPES = {"heart_rate": {120, "heart_rate"},
                        "power": {11, "bike_power", 17, "fitness_equipment"},
                        "cadence": {121, "bike_speed_cadence", 122, "bike_cadence", 11, "bike_power",
                                    17, "fitness_equipment"}}
SIMULATING_MANUFACTURERS = {"mywhoosh"}


def _epoch(v: Any) -> Optional[float]:
    return v.timestamp() if isinstance(v, datetime) else None


def _jsonable(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    return v


def _fields(frame) -> dict[str, Any]:
    return strip_location({f.name: _jsonable(f.value) for f in frame.fields})


def parse(data: bytes) -> RawActivity:
    records: list[RawRecord] = []
    originals: list[dict] = []
    events: list[TimerEvent] = []
    sessions: list[dict] = []
    devices: list[dict] = []
    file_id: dict = {}
    local_offset: Optional[float] = None
    try:
        with fitdecode.FitReader(io.BytesIO(data), check_crc=fitdecode.CrcCheck.RAISE) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                name = frame.name
                if name == "record":
                    ts = _epoch(frame.get_value("timestamp", fallback=None)) if frame.has_field("timestamp") else None
                    if ts is None:
                        continue  # a record without a time cannot be placed; counted below
                    fields: dict[str, Optional[float]] = {}
                    for channel, names in RECORD_FIELDS.items():
                        for n in names:
                            if frame.has_field(n):
                                v = frame.get_value(n)
                                fields[channel] = float(v) if isinstance(v, (int, float)) else None
                                break
                    records.append(RawRecord(ts, fields))
                    originals.append(_fields(frame))
                elif name == "event" and frame.get_value("event", fallback=None) == "timer":
                    kind = TIMER_EVENT_TYPES.get(frame.get_value("event_type", fallback=None))
                    ts = _epoch(frame.get_value("timestamp", fallback=None))
                    if kind and ts is not None:
                        events.append(TimerEvent(ts, kind))
                elif name == "session":
                    sessions.append(_fields(frame))
                elif name == "device_info":
                    devices.append(_fields(frame))
                elif name == "file_id":
                    file_id = _fields(frame)
                elif name == "activity" and frame.has_field("local_timestamp"):
                    ts = _epoch(frame.get_value("timestamp", fallback=None))
                    lt = frame.get_value("local_timestamp", fallback=None)
                    lt = _epoch(lt) if isinstance(lt, datetime) else None
                    if ts is not None and lt is not None:
                        local_offset = lt - ts
    except fitdecode.FitError as exc:
        raise ImportFailure("corrupt", f"FIT decode failed: {exc}") from exc
    if file_id.get("type") not in (None, "activity"):
        raise ImportFailure("not_activity", f"FIT file type is {file_id.get('type')!r}")
    if not records:
        raise ImportFailure("no_records", "FIT file has no timestamped records")

    manufacturer = str(file_id.get("manufacturer", "")).lower()
    sub_sports = {str(s.get("sub_sport")) for s in sessions}
    simulated = frozenset({"speed", "distance"}) if (
        manufacturer in SIMULATING_MANUFACTURERS or "virtual_activity" in sub_sports) else frozenset()
    timer_values = [s.get("total_timer_time") for s in sessions if isinstance(s.get("total_timer_time"), (int, float))]

    sensor_identity = {}
    for channel, types in CHANNEL_DEVICE_TYPES.items():
        cands = [d for d in devices if d.get("device_type") in types or d.get("antplus_device_type") in types]
        sensor_identity[channel] = {"match": cands[0] if len(cands) == 1 else None, "candidates": cands}

    # The recording's own identity: a re-export of one recording keeps it even when bytes differ.
    ident = None
    if file_id.get("serial_number") is not None and file_id.get("time_created") is not None:
        ident = ":".join(str(file_id.get(k)) for k in ("manufacturer", "product", "serial_number", "time_created"))
        ident = f"fit:{ident}"
    return RawActivity(
        source_format="fit",
        records=records,
        timer_events=events,
        device_timer_s=sum(timer_values) if timer_values else None,
        utc_offset_s=local_offset,
        simulated_channels=simulated,
        sensor_identity=sensor_identity,
        original_fields=originals,
        metadata={"file_id": file_id, "sessions": sessions, "devices": devices,
                  "source_platform": manufacturer or None,
                  "original_activity_id": ident,
                  "device": {k: file_id.get(k) for k in ("manufacturer", "product", "serial_number")},
                  "sport": next((s.get("sport") for s in sessions), None),
                  "sub_sport": next((s.get("sub_sport") for s in sessions), None),
                  "parser_version": PARSER_VERSION},
    )
