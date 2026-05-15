"""Tests for HostValidatorMiddleware (DNS rebinding defense).

The middleware validates the Host header against a bare-hostname allowlist
[127.0.0.1, localhost, ::1] with IPv6-aware extraction:

- ``127.0.0.1:8765`` -> ``127.0.0.1``
- ``[::1]:8765`` -> ``::1``
- Hostname comparison is case-insensitive (``LOCALHOST`` -> ``localhost``)
- Empty / malformed hosts -> rejected with HTTP 400

These tests target the bare middleware wrapped around a trivial Starlette
app; they do NOT exercise the full admin app (Task 3 wires it).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from spellbook.admin.middleware import HostValidatorMiddleware

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "::1"]


async def _ok(request):
    return PlainTextResponse("ok")


def _make_client(allowed: list[str] | None = None) -> TestClient:
    if allowed is None:
        allowed = ALLOWED_HOSTS
    app = Starlette(routes=[Route("/", _ok)])
    app.add_middleware(HostValidatorMiddleware, allowed_hosts=allowed)
    client = TestClient(app)
    # Drop the default TestClient Host (``testserver``) so each test
    # provides its own Host header explicitly.
    client.headers.pop("host", None)
    client.headers.pop("Host", None)
    return client


# (host_header_value, expect_status, description)
CASES: list[tuple[str | None, int, str]] = [
    ("127.0.0.1:8765", 200, "ipv4 with port"),
    ("127.0.0.1", 200, "ipv4 bare"),
    ("localhost:8765", 200, "localhost with port"),
    ("localhost", 200, "localhost bare"),
    ("[::1]:8765", 200, "ipv6 bracketed with port"),
    ("[::1]", 200, "ipv6 bracketed bare"),
    ("evil.com", 400, "rebinding bare"),
    ("evil.com:8765", 400, "rebinding with port"),
    ("127.0.0.1.evil.com", 400, "rebinding suffix attack"),
    ("", 400, "empty host header"),
    ("[bad", 400, "unclosed ipv6 bracket"),
    ("LOCALHOST", 200, "uppercase localhost"),
    ("Localhost:8765", 200, "mixed-case localhost with port"),
]


@pytest.mark.parametrize(
    "host_value,expect_status,description",
    CASES,
    ids=[c[2] for c in CASES],
)
def test_host_header_validation(
    host_value: str, expect_status: int, description: str
) -> None:
    """Each row of the design-doc Host validator table.

    ESCAPE: test_host_header_validation
      CLAIM: Middleware accepts only [127.0.0.1, localhost, ::1] (case-insensitive,
             port-stripped, IPv6-bracket-aware) and rejects everything else with 400.
      PATH:  TestClient -> HostValidatorMiddleware.__call__ -> _extract_hostname
             -> allowlist membership -> either pass-through (200) or
             PlainTextResponse("Invalid host header", status=400).
      CHECK: Exact status code equality per row.
      MUTATION:
        - Drop ``.lower()`` on extracted hostname -> ``LOCALHOST`` row fails.
        - Drop IPv6 bracket branch -> ``[::1]:8765`` extracts as ``[`` -> 400 (currently 200).
        - Use substring/endswith match -> ``127.0.0.1.evil.com`` would pass.
        - Forget the empty-string branch -> ``""`` may be accepted.
        - Return non-empty on malformed ``[bad`` -> would 200 instead of 400.
      ESCAPE: A middleware that accepts everything would pass the 200 rows but fail
              every 400 row; one that rejects everything would fail every 200 row.
              The 13 rows together pin the contract.
      IMPACT: DNS rebinding regressions silently re-open the admin sub-app to
              cross-origin browsers, defeating C1.
    """
    client = _make_client()
    headers = {}
    if host_value != "" and host_value is not None:
        headers["Host"] = host_value
    # When host_value is "", we intentionally send no Host header (empty == missing
    # at the HTTP layer for this middleware's purposes).
    resp = client.get("/", headers=headers)
    assert resp.status_code == expect_status, (
        f"{description}: Host={host_value!r} expected {expect_status}, "
        f"got {resp.status_code} body={resp.text!r}"
    )
    if expect_status == 400:
        assert resp.text == "Invalid host header"
    else:
        assert resp.text == "ok"
