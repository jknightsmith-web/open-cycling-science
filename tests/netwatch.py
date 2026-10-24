"""Run a Python module with every network call recorded (spec 8.5, acceptance 16).

    python tests/netwatch.py <log file> -m backend.api

An audit hook (PEP 578) sees each socket connect, sendto, bind and address
lookup made anywhere in the process, including by third party libraries, and
appends one JSON line per event to the log. Tests then assert that every
address in the log is loopback. This watches the running application, not a
test double.
"""
from __future__ import annotations

import json
import runpy
import sys
import threading

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_lock = threading.Lock()


def _host(args) -> object:
    for a in args:
        if isinstance(a, tuple) and a and isinstance(a[0], str):
            return a[0]
        if isinstance(a, str):
            return a
    return None


def main() -> None:
    log_path, flag, module = sys.argv[1], sys.argv[2], sys.argv[3]
    assert flag == "-m"
    log = open(log_path, "a", buffering=1)

    def hook(event: str, args) -> None:
        if not (event.startswith("socket.") or event in ("http.client.connect", "urllib.Request")):
            return
        if event in ("socket.__new__",):
            return
        host = _host(args)
        with _lock:
            log.write(json.dumps({"event": event, "host": host if isinstance(host, str) else repr(host),
                                  "loopback": host in LOOPBACK or host is None}) + "\n")

    sys.addaudithook(hook)
    sys.argv = [module] + sys.argv[4:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)


def offenders(log_path: str) -> list[dict]:
    with open(log_path) as f:
        events = [json.loads(line) for line in f if line.strip()]
    return [e for e in events if not e["loopback"]]


if __name__ == "__main__":
    main()
