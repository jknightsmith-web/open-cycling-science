"""Content addressed, write once file vault (spec 8.1).

Objects are stored at vault/sha256/ab/cd/<sha256>, written atomically, set
read only and verified by rehash. Identical bytes are stored once.
"""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path

CHUNK = 1 << 20


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


class VaultIntegrityError(Exception):
    pass


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:4] / digest

    def put(self, data: bytes) -> tuple[str, bool]:
        """Store bytes. Returns (sha256, created). Existing objects are verified, never rewritten."""
        digest = sha256_bytes(data)
        target = self.path_for(digest)
        if target.exists():
            self.verify(digest)
            return digest, False
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".incoming-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            os.replace(tmp, target)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        self.verify(digest)
        return digest, True

    def read(self, digest: str) -> bytes:
        self.verify(digest)
        return self.path_for(digest).read_bytes()

    def verify(self, digest: str) -> None:
        actual = sha256_file(self.path_for(digest))
        if actual != digest:
            raise VaultIntegrityError(f"vault object {digest} rehashes to {actual}")

    def delete(self, digest: str) -> None:
        """Remove an object. Callers must first confirm no activity references it."""
        p = self.path_for(digest)
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
        p.unlink()
