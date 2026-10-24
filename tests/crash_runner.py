"""Stop a process abruptly in the middle of an operation, to test recovery (WP9).

    python tests/crash_runner.py <operation> <data root> [argument]

The process exits with os._exit at the named point: no cleanup handlers,
no finally blocks, as on a power cut or a forced quit.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from backend.library import Library, deletion, exports, ingest, restore   # noqa: E402

CRASH = 86


def die(*_a, **_k):
    sys.stdout.flush()
    os._exit(CRASH)


def main() -> None:
    op, root, arg = sys.argv[1], Path(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else None)
    lib = Library(root)
    if op == "delete-after-commit":          # database committed, vault object and exports not yet removed
        deletion._remove_files = die
        deletion.delete_activity(lib, int(arg))
    elif op == "restore-before-commit":      # vault objects written, tables not committed
        restore._insert_all = die
        restore.restore(lib, Path(arg))
    elif op == "restore-mid-insert":         # inside the insert transaction
        real = restore._jsonl

        def stop_at_samples(zf, name):
            if name == "data/json/samples.jsonl" and sys._getframe(1).f_code.co_name == "_insert_all":
                die()
            return real(zf, name)
        restore._jsonl = stop_at_samples
        restore.restore(lib, Path(arg))
    elif op == "export-mid-write":           # partial ZIP on disk
        real_w = exports._write_jsonl

        def stop(c, table):
            if table.name == "samples":
                die()
            return real_w(c, table)
        exports._write_jsonl = stop
        exports.build(lib, "archive")
    elif op == "import-after-vault":         # original stored, database not written
        ingest.store_activity = die
        ingest.import_bytes(lib, Path(arg).read_bytes(), Path(arg).name)
    else:
        raise SystemExit(f"unknown operation {op}")
    raise SystemExit("operation finished without reaching the crash point")


if __name__ == "__main__":
    main()
