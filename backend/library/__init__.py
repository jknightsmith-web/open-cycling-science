"""The rider's library: import, activities, duplicate groups, rides and aggregates (WP6).

`Library` binds one data root: its database (migrated on open) and its vault.
Every write goes through one transaction per user action, so a failed step
leaves nothing half done.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from ..config import data_root, layout
from ..storage.db import engine_for, upgrade
from ..storage.maintenance import recover
from ..storage.vault import Vault


class Library:
    def __init__(self, root: Path, now: Callable[[], float] = time.time):
        self.root = Path(root)
        self.now = now
        self._open()

    def _open(self) -> None:
        self.paths = layout(self.root)
        upgrade(self.paths["db"])
        self.engine = engine_for(self.paths["db"])
        self.vault = Vault(self.paths["vault"])
        from ..science.registry import sync_definitions
        with self.engine.begin() as c:
            sync_definitions(c)
        # Finish what an interrupted import, export, restore or deletion left (spec 8.4).
        self.recovery = recover(self.engine, self.vault, [self.paths["exports"], self.paths["backups"]],
                                self.paths["exports"])

    def reopen(self) -> None:
        """Re-create an empty install at the same root after "delete everything"."""
        self._open()

    @classmethod
    def open(cls, root: Optional[Path] = None, **kw) -> "Library":
        return cls(root or data_root(), **kw)
