"""Test wide guards.

Acceptance 16: the suite runs with outbound networking blocked. Any attempt
to connect to a non loopback address fails the test that made it.
"""
import socket

import pytest

_real_connect = socket.socket.connect
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and host not in _LOOPBACK and self.family != socket.AF_UNIX:
        raise RuntimeError(f"outbound network connection attempted to {address!r}")
    return _real_connect(self, address)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
