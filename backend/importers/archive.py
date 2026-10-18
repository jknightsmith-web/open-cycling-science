"""Zip archive extraction with traversal and zip bomb limits (architecture section 9)."""
from __future__ import annotations

import io
import zipfile
from pathlib import PurePosixPath

from .errors import ImportFailure

MAX_ENTRIES = 20_000
MAX_TOTAL_BYTES = 4 * 1024 ** 3
MAX_ENTRY_BYTES = 256 * 1024 ** 2
MAX_RATIO = 200
ACCEPTED_SUFFIXES = {".fit", ".tcx"}


def members(data: bytes) -> list[tuple[str, bytes]]:
    """Return (name, bytes) for each FIT or TCX member. Other members are skipped and listed by the caller."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ImportFailure("corrupt", f"zip rejected: {exc}") from exc
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ImportFailure("unsafe_archive", f"{len(infos)} entries exceeds {MAX_ENTRIES}")
    total = 0
    out = []
    for info in infos:
        name = info.filename
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or (path.parts and path.parts[0].endswith(":")):
            raise ImportFailure("unsafe_archive", f"unsafe member path {name!r}")
        if info.is_dir() or path.suffix.lower() not in ACCEPTED_SUFFIXES:
            continue
        if info.file_size > MAX_ENTRY_BYTES:
            raise ImportFailure("unsafe_archive", f"{name!r} is larger than {MAX_ENTRY_BYTES} bytes")
        if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
            raise ImportFailure("unsafe_archive", f"{name!r} compression ratio exceeds {MAX_RATIO}")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ImportFailure("unsafe_archive", "archive expands beyond the total size limit")
        with zf.open(info) as f:
            content = f.read(MAX_ENTRY_BYTES + 1)
        if len(content) > MAX_ENTRY_BYTES:
            raise ImportFailure("unsafe_archive", f"{name!r} expands beyond its declared size")
        out.append((name, content))
    return out
