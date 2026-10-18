"""Minimal FIT encoder for synthetic test fixtures (architecture section 2, C23).

Implements only what the tests need, from the published FIT protocol: file
header, definition and data messages, compressed timestamp headers, invalid
sentinels and both CRCs. Not shipped with the application.
"""
from __future__ import annotations

import struct
from typing import Optional

FIT_EPOCH_UNIX = 631065600  # 1989-12-31T00:00:00Z

_CRC_TABLE = (0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
              0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400)

# base type id -> (struct code, invalid sentinel)
ENUM, SINT8, UINT8, UINT16, UINT32, STRING = 0x00, 0x01, 0x02, 0x84, 0x86, 0x07
_BASE = {ENUM: ("B", 0xFF), SINT8: ("b", 0x7F), UINT8: ("B", 0xFF),
         UINT16: ("H", 0xFFFF), UINT32: ("I", 0xFFFFFFFF)}

# message number -> {field name: (field number, base type, scale)}
MESSAGES = {
    "file_id": (0, {"type": (0, ENUM, 1), "manufacturer": (1, UINT16, 1), "product": (2, UINT16, 1),
                    "time_created": (4, UINT32, 1)}),
    "record": (20, {"timestamp": (253, UINT32, 1), "heart_rate": (3, UINT8, 1), "cadence": (4, UINT8, 1),
                    "power": (7, UINT16, 1), "speed": (6, UINT16, 1000), "distance": (5, UINT32, 100),
                    "temperature": (13, SINT8, 1)}),
    "event": (21, {"timestamp": (253, UINT32, 1), "event": (0, ENUM, 1), "event_type": (1, ENUM, 1)}),
    "session": (18, {"timestamp": (253, UINT32, 1), "start_time": (2, UINT32, 1), "sport": (5, ENUM, 1),
                     "sub_sport": (6, ENUM, 1), "total_elapsed_time": (7, UINT32, 1000),
                     "total_timer_time": (8, UINT32, 1000)}),
    "activity": (34, {"timestamp": (253, UINT32, 1), "local_timestamp": (5, UINT32, 1)}),
    "device_info": (23, {"timestamp": (253, UINT32, 1), "device_index": (0, UINT8, 1),
                         "device_type": (1, UINT8, 1), "manufacturer": (2, UINT16, 1), "product": (4, UINT16, 1)}),
}
EVENT_TIMER, EVENT_START, EVENT_STOP, EVENT_STOP_ALL = 0, 0, 1, 4
SPORT_CYCLING, SUB_VIRTUAL, SUB_INDOOR = 2, 58, 6
INVALID = object()  # write the field's invalid sentinel


def crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def fit_time(unix_s: float) -> int:
    return int(round(unix_s)) - FIT_EPOCH_UNIX


class FitWriter:
    def __init__(self):
        self.body = bytearray()
        self._defs: dict[tuple, int] = {}
        self._next = {"record": 0, "other": 4}   # records use 0-3 so compressed headers can address them
        self._last_ts: Optional[int] = None

    def _local_for(self, msg: str, names: tuple[str, ...]) -> int:
        key = (msg, names)
        if key in self._defs:
            return self._defs[key]
        pool = "record" if msg == "record" else "other"
        lo, size = (0, 4) if pool == "record" else (4, 12)
        local = lo + (self._next[pool] - lo) % size
        self._next[pool] += 1
        for k, v in list(self._defs.items()):
            if v == local:
                del self._defs[k]
        num, spec = MESSAGES[msg]
        fields = [spec[n] for n in names]
        self.body += struct.pack("<BBBHB", 0x40 | local, 0, 0, num, len(fields))
        for fnum, btype, _ in fields:
            self.body += struct.pack("<BBB", fnum, struct.calcsize("<" + _BASE[btype][0]), btype)
        self._defs[key] = local
        return local

    def write(self, msg: str, compressed_timestamp: bool = False, **values) -> None:
        """Write one message. Values are in physical units; INVALID writes the sentinel."""
        _, spec = MESSAGES[msg]
        if compressed_timestamp:
            ts = values.pop("timestamp")
            names = tuple(values)
            local = self._local_for(msg, names)
            if local > 3:
                raise ValueError("compressed headers need local types 0 to 3")
            offset = ts & 0x1F
            if self._last_ts is None or ts - self._last_ts >= 32 or ts < self._last_ts:
                raise ValueError("compressed timestamp must be within 31 s after the last timestamp")
            header = 0x80 | (local << 5) | offset
            self._last_ts = ts
        else:
            names = tuple(values)
            local = self._local_for(msg, names)
            header = local
            if "timestamp" in values:
                self._last_ts = values["timestamp"]
        self.body.append(header)
        for n in names:
            _, btype, scale = spec[n]
            code, sentinel = _BASE[btype]
            v = values[n]
            raw = sentinel if v is INVALID else int(round(v * scale))
            self.body += struct.pack("<" + code, raw)

    def bytes(self, profile_version: int = 2100) -> bytes:
        header = struct.pack("<BBHI4s", 14, 0x20, profile_version, len(self.body), b".FIT")
        header += struct.pack("<H", crc16(header))
        data = header + bytes(self.body)
        return data + struct.pack("<H", crc16(data))


def activity_file(records: list[dict], events: list[tuple[float, int]] = (), session: Optional[dict] = None,
                  devices: list[dict] = (), local_offset_s: Optional[int] = None,
                  compress_after_first: bool = False) -> bytes:
    """Build an activity FIT file.

    records: dicts with unix 't' plus any of power, heart_rate, cadence, speed,
    distance, temperature (INVALID for a sentinel; omit a key for an absent field).
    events: (unix time, event_type) timer events.
    """
    w = FitWriter()
    t0 = fit_time(records[0]["t"]) if records else 0
    w.write("file_id", type=4, manufacturer=255, product=1, time_created=t0)
    for d in devices:
        w.write("device_info", timestamp=t0, **d)
    timeline = [("r", r["t"], r) for r in records] + [("e", t, et) for t, et in events]
    timeline.sort(key=lambda x: (x[1], x[0] == "r"))
    first = True
    for kind, t, payload in timeline:
        ts = fit_time(t)
        if kind == "e":
            w.write("event", timestamp=ts, event=EVENT_TIMER, event_type=payload)
            continue
        fields = {k: v for k, v in payload.items() if k != "t"}
        w.write("record", compressed_timestamp=compress_after_first and not first, timestamp=ts, **fields)
        first = False
    if session is not None:
        end = fit_time(records[-1]["t"]) if records else t0
        w.write("session", timestamp=end, start_time=t0, **session)
    if local_offset_s is not None:
        end = fit_time(records[-1]["t"])
        w.write("activity", timestamp=end, local_timestamp=end + local_offset_s)
    return w.bytes()
