"""Unit tests must not touch the network or a database.

Forgetting to patch a new external call used to leave a test quietly passing
while spending API credits. This blocks outbound connections instead, so the
test fails with a clear message naming what it tried to reach.
"""

import socket

import pytest

BLOCKED = (
    "Unit tests cannot open connections (tried {target}). "
    "Patch the call that reaches out, or move the test to tests/integration."
)


@pytest.fixture(autouse=True)
def no_outbound_connections(monkeypatch):
    def blocked(self, address, *args, **kwargs):
        raise RuntimeError(BLOCKED.format(target=address))

    def blocked_create(address, *args, **kwargs):
        raise RuntimeError(BLOCKED.format(target=address))

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked_create)
