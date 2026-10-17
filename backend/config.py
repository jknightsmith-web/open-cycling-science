"""Data root resolution (spec 8.1, decision D4).

The data root holds every piece of rider data and never defaults to a
location inside the source tree.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "OpenCyclingScience"
ENV_VAR = "OCS_DATA_ROOT"


def default_data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    # Cross platform development (spec 4); macOS is the acceptance platform.
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


def data_root() -> Path:
    configured = os.environ.get(ENV_VAR)
    return Path(configured).expanduser() if configured else default_data_root()


def layout(root: Path) -> dict[str, Path]:
    return {
        "vault": root / "vault" / "sha256",
        "db": root / "db" / "cycling.db",
        "exports": root / "exports",
        "backups": root / "backups",
        "logs": root / "logs",
    }
