"""Location fields are not kept outside the original file (spec 8.2, decision D5).

The vault keeps every original byte, GPS included. The database copy of each
record's raw fields drops position, so derived data and derived exports carry
no location.
"""
from __future__ import annotations

import re
from typing import Any

_LOCATION = re.compile(r"(^|_)(position|lat|long|latitude|longitude)(_|$)")


def is_location_field(name: str) -> bool:
    return bool(_LOCATION.search(name))


def strip_location(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if not is_location_field(k)}
