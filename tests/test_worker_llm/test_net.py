"""Tests for ``spellbook.worker_llm.net.build_host_url``.

Guards IPv6 handling in every subprocess URL builder: bare ``::1`` in a URL
authority is ambiguous with the port separator, so IPv6 literals must be
bracketed. IPv4 and hostnames contain no colons and pass through unchanged.
"""

from __future__ import annotations

import pytest

from spellbook.worker_llm.net import build_host_url


@pytest.mark.parametrize(
    "host,port,path,expected",
    [
        # IPv4 literal: no brackets.
        ("127.0.0.1", 8765, "/api/events/publish",
         "http://127.0.0.1:8765/api/events/publish"),
        # IPv6 loopback: must be bracketed.
        ("::1", 8765, "/api/events/publish",
         "http://[::1]:8765/api/events/publish"),
        # IPv6 link-local: must be bracketed.
        ("fe80::1", 8765, "/api/events/publish",
         "http://[fe80::1]:8765/api/events/publish"),
        # Hostname: no brackets.
        ("localhost", 8765, "/api/events/publish",
         "http://localhost:8765/api/events/publish"),
        # Port may be str or int.
        ("127.0.0.1", "8765", "/health", "http://127.0.0.1:8765/health"),
        # Empty path is valid.
        ("127.0.0.1", 8765, "", "http://127.0.0.1:8765"),
        # Full IPv6 address.
        ("2001:db8::1", 8765, "/x",
         "http://[2001:db8::1]:8765/x"),
    ],
)
def test_build_host_url(host, port, path, expected):
    assert build_host_url(host, port, path) == expected
