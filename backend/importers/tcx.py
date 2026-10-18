"""TCX importer (architecture section 4). Parsed with defusedxml.

TCX has no timer events, so the timeline uses the assumed continuous timer
(decision D3). Absent Watts is missing, never 0.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from defusedxml import DefusedXmlException

from ..canonical.model import RawActivity, RawRecord
from .errors import ImportFailure

PARSER_VERSION = "tcx-1.0"
TCD = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"
TPX = "{http://www.garmin.com/xmlschemas/ActivityExtension/v2}"


def _time(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.timestamp() if dt.tzinfo else None


def _num(el: Optional[Element]) -> tuple[bool, Optional[float]]:
    """(present, value). Present but unparseable is invalid (value None)."""
    if el is None:
        return False, None
    try:
        return True, float((el.text or "").strip())
    except ValueError:
        return True, None


def parse(data: bytes) -> RawActivity:
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ImportFailure("corrupt", f"TCX XML rejected: {exc}") from exc
    if root.tag != f"{TCD}TrainingCenterDatabase":
        raise ImportFailure("unsupported", "root element is not TrainingCenterDatabase v2")
    activity = root.find(f"{TCD}Activities/{TCD}Activity")
    if activity is None:
        raise ImportFailure("not_activity", "TCX contains no Activity")

    records, originals = [], []
    untimed = 0
    lap_times = []
    for lap in activity.findall(f"{TCD}Lap"):
        present, total = _num(lap.find(f"{TCD}TotalTimeSeconds"))
        if present and total is not None:
            lap_times.append(total)
        for tp in lap.iter(f"{TCD}Trackpoint"):
            ts = _time(tp.findtext(f"{TCD}Time"))
            if ts is None:
                untimed += 1
                continue
            channels = {
                "heart_rate": tp.find(f"{TCD}HeartRateBpm/{TCD}Value"),
                "cadence": tp.find(f"{TCD}Cadence"),
                "distance": tp.find(f"{TCD}DistanceMeters"),
                "power": tp.find(f"{TCD}Extensions/{TPX}TPX/{TPX}Watts"),
                "speed": tp.find(f"{TCD}Extensions/{TPX}TPX/{TPX}Speed"),
            }
            fields = {}
            for ch, el in channels.items():
                present, value = _num(el)
                if present:
                    fields[ch] = value
            records.append(RawRecord(ts, fields))
            originals.append({ch: (el.text if el is not None else None) for ch, el in channels.items() if el is not None})
    if not records:
        raise ImportFailure("no_records", "TCX has no timestamped trackpoints")
    creator = activity.findtext(f"{TCD}Creator/{TCD}Name")
    return RawActivity(
        source_format="tcx",
        records=records,
        timer_events=[],
        device_timer_s=sum(lap_times) if lap_times else None,
        original_fields=originals,
        metadata={"source_platform": creator, "sport": activity.get("Sport"),
                  "untimed_trackpoints": untimed, "parser_version": PARSER_VERSION},
    )
