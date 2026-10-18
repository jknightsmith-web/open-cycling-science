"""Content sniffing: the file's bytes decide its format, not its name."""
from __future__ import annotations

from .errors import ImportFailure


def sniff(data: bytes) -> str:
    if len(data) >= 12 and data[8:12] == b".FIT":
        return "fit"
    if data[:4] == b"PK\x03\x04":
        return "zip"
    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"<?xml") or head.startswith(b"<"):
        if b"TrainingCenterDatabase" in data[:4096]:
            return "tcx"
    raise ImportFailure("unsupported", "not a FIT, TCX or zip file")
