"""Tests for OriginCheckMiddleware (CSRF defense via Origin header).

The middleware enforces a same-origin Origin header on state-changing HTTP
methods (POST/PUT/PATCH/DELETE). Safe methods (GET/HEAD/OPTIONS) and
WebSocket scopes pass through. Requests presenting a valid Bearer token
(matched against ``spellbook.admin.auth.load_token`` via
``secrets.compare_digest``) bypass the Origin check entirely; an *invalid*
Bearer token does NOT short-circuit -- it falls through to the Origin
check, which fails closed with 403.

``load_token`` is resolved at request time (not at middleware construction)
so ``monkeypatch.setattr("spellbook.admin.auth.load_token", ...)`` works in
tests.

These tests target the bare middleware wrapped around a trivial Starlette
app; they do NOT exercise the full admin app (Task 5 wires it).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from spellbook.admin.middleware import OriginCheckMiddleware

ALLOWED_ORIGINS = [
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://[::1]:8765",
]


async def _ok(request):
    return PlainTextResponse("ok")


def _make_client(allowed_origins: list[str] | None = None) -> TestClient:
    if allowed_origins is None:
        allowed_origins = ALLOWED_ORIGINS
    app = Starlette(
        routes=[
            Route("/", _ok, methods=["GET", "HEAD", "OPTIONS"]),
            Route("/mutate", _ok, methods=["POST", "PUT", "PATCH", "DELETE"]),
        ]
    )
    app.add_middleware(OriginCheckMiddleware, allowed_origins=allowed_origins)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Safe methods: no Origin required.
# ---------------------------------------------------------------------------


def test_get_no_origin_allowed() -> None:
    """GET requests bypass the Origin check entirely.

    ESCAPE: test_get_no_origin_allowed
      CLAIM: GET with no Origin header passes through to the route.
      PATH:  TestClient -> OriginCheckMiddleware (method=GET, skip) -> route.
      CHECK: status == 200 and body == "ok".
      MUTATION: Removing the safe-method early-return would cause GET with
                no Origin to 403. Removing the route would 404. Status+body
                pin both.
      ESCAPE: A middleware that allowed every request unconditionally would
              pass this test, but the rejection-path tests below would fail
              for it.
      IMPACT: Blocking GET would break the admin UI's HTML/asset fetches.
    """
    client = _make_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_options_no_origin_allowed() -> None:
    """OPTIONS requests bypass the Origin check entirely.

    ESCAPE: test_options_no_origin_allowed
      CLAIM: OPTIONS with no Origin header is not blocked by the middleware.
      PATH:  TestClient -> OriginCheckMiddleware (method=OPTIONS, skip)
             -> Starlette routing (which auto-handles OPTIONS or 405s).
      CHECK: status is NOT 403 (middleware did not reject).
      MUTATION: Treating OPTIONS as state-changing would make this 403.
      ESCAPE: A passthrough middleware would also pass; safe-method
              rejection tests below pin the contract.
      IMPACT: Blocking OPTIONS breaks CORS preflight even though the admin
              app is same-origin.
    """
    client = _make_client()
    resp = client.options("/")
    # Starlette returns 200 from auto-OPTIONS handling, or possibly 405 if
    # the route does not implement it; either way the middleware itself
    # MUST NOT 403 the request.
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# State-changing methods with a valid Origin: allowed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,origin",
    [
        ("POST", "http://127.0.0.1:8765"),
        ("POST", "http://localhost:8765"),
        ("POST", "http://[::1]:8765"),
    ],
    ids=["ipv4", "localhost", "ipv6"],
)
def test_post_valid_origin_allowed(method: str, origin: str) -> None:
    """POST with an Origin in the allowlist passes through.

    ESCAPE: test_post_valid_origin_allowed
      CLAIM: All three same-origin variants (IPv4, localhost, IPv6) are
             accepted on state-changing methods.
      PATH:  TestClient -> OriginCheckMiddleware -> allowlist check
             (origin in allowlist) -> route -> 200 "ok".
      CHECK: status == 200 and body == "ok".
      MUTATION:
        - Drop IPv6 from the allowlist -> ipv6 row fails.
        - Use ``startswith`` instead of exact membership -> still passes
          here but mismatched-origin test below fails.
        - Always-reject -> all three rows fail.
      ESCAPE: A middleware that accepted every Origin would also pass this
              row but the mismatched-origin test would fail.
      IMPACT: A regression here breaks the admin UI's own mutating calls.
    """
    client = _make_client()
    resp = client.request(method, "/mutate", headers={"Origin": origin})
    assert resp.status_code == 200
    assert resp.text == "ok"


# Convenience wrappers for the three labelled allowlist cases, so the
# task-required test names exist explicitly.

def test_post_valid_localhost_origin_allowed() -> None:
    """POST /mutate with Origin http://localhost:8765 -> 200."""
    client = _make_client()
    resp = client.post("/mutate", headers={"Origin": "http://localhost:8765"})
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_post_valid_ipv6_origin_allowed() -> None:
    """POST /mutate with Origin http://[::1]:8765 -> 200."""
    client = _make_client()
    resp = client.post("/mutate", headers={"Origin": "http://[::1]:8765"})
    assert resp.status_code == 200
    assert resp.text == "ok"


# ---------------------------------------------------------------------------
# State-changing methods rejected for missing or wrong Origin.
# ---------------------------------------------------------------------------


def test_post_missing_origin_rejected() -> None:
    """POST with no Origin header is rejected.

    ESCAPE: test_post_missing_origin_rejected
      CLAIM: POST with no Authorization and no Origin -> 403.
      PATH:  TestClient -> OriginCheckMiddleware (method=POST, no bearer,
             no Origin) -> PlainTextResponse 403.
      CHECK: status == 403 and body == "Forbidden: invalid Origin".
      MUTATION:
        - Default-allow on missing Origin -> 200, this row fails.
        - Return 401/400 instead of 403 -> status assertion fails.
        - Return a JSON envelope -> body assertion fails (task contract
          requires plain text).
      ESCAPE: A middleware that always 403s every state-changing request
              would pass this row but fail the valid-Origin rows.
      IMPACT: Missing this check re-enables CSRF on the admin sub-app.
    """
    client = _make_client()
    resp = client.post("/mutate")
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


def test_post_mismatched_origin_rejected() -> None:
    """POST with an Origin not in the allowlist is rejected.

    ESCAPE: test_post_mismatched_origin_rejected
      CLAIM: POST with Origin: http://evil.com -> 403.
      PATH:  TestClient -> OriginCheckMiddleware (no bearer) -> Origin not
             in allowlist -> PlainTextResponse 403.
      CHECK: status == 403 and body == "Forbidden: invalid Origin".
      MUTATION:
        - Substring/endswith match -> evil.com containing a localhost
          fragment could pass; here exact membership is the only safe
          comparison and this row pins it.
        - Always-allow -> this row fails.
      ESCAPE: A middleware that 403s every state-changing request would
              also pass this row; the valid-Origin rows guard against that.
      IMPACT: A regression here re-opens cross-origin CSRF.
    """
    client = _make_client()
    resp = client.post("/mutate", headers={"Origin": "http://evil.com"})
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_state_changing_method_missing_origin_rejected(method: str) -> None:
    """PUT/PATCH/DELETE with no Origin header are all rejected.

    ESCAPE: test_state_changing_method_missing_origin_rejected
      CLAIM: All four mutating verbs are gated by the Origin check.
      PATH:  TestClient -> OriginCheckMiddleware -> classify method as
             state-changing -> no bearer -> Origin missing -> 403.
      CHECK: status == 403 and body == "Forbidden: invalid Origin".
      MUTATION:
        - Only gating POST (omitting PUT/PATCH/DELETE from the set) ->
          those rows pass through to the route as 200 "ok", failing this
          assertion.
        - Mis-spelling a verb in the state-changing set -> same failure.
      ESCAPE: A blanket "reject all state-changing requests" implementation
              would pass this, but valid-Origin rows guard against it.
      IMPACT: Skipping any verb leaves CSRF holes on that method.
    """
    client = _make_client()
    resp = client.request(method, "/mutate")
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


# Explicit single-method tests so the task-required test names exist.

def test_put_missing_origin_rejected() -> None:
    """PUT /mutate with no Origin -> 403."""
    client = _make_client()
    resp = client.put("/mutate")
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


def test_patch_missing_origin_rejected() -> None:
    """PATCH /mutate with no Origin -> 403."""
    client = _make_client()
    resp = client.patch("/mutate")
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


def test_delete_missing_origin_rejected() -> None:
    """DELETE /mutate with no Origin -> 403."""
    client = _make_client()
    resp = client.delete("/mutate")
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


# ---------------------------------------------------------------------------
# Bearer exemption.
# ---------------------------------------------------------------------------


def test_post_with_valid_bearer_no_origin_allowed(monkeypatch) -> None:
    """A valid Bearer token bypasses the Origin check.

    ESCAPE: test_post_with_valid_bearer_no_origin_allowed
      CLAIM: POST with ``Authorization: Bearer <valid>`` and no Origin -> 200.
      PATH:  TestClient -> OriginCheckMiddleware -> Authorization parses as
             Bearer -> load_token() returns the patched value ->
             secrets.compare_digest() returns True -> pass through -> 200.
      CHECK: status == 200 and body == "ok".
      MUTATION:
        - Closing load_token over construction time (instead of resolving
          per-request) would defeat the monkeypatch and load_token's real
          implementation would be called; this test would 403.
        - Using ``==`` instead of secrets.compare_digest still passes (the
          equality is the same), but the security property differs; the
          invalid-bearer test below pins fail-closed behavior.
        - Inverting the bearer-match branch -> 403, this row fails.
      ESCAPE: A middleware that always allows when Authorization is present
              (regardless of value) would pass this row but fail the
              invalid-bearer row below.
      IMPACT: Without the bearer exemption, the CLI's POST /handoff (which
              has no browser Origin header) cannot authenticate.
    """
    monkeypatch.setattr(
        "spellbook.admin.auth.load_token", lambda: "secret-token-123"
    )
    client = _make_client()
    resp = client.post(
        "/mutate", headers={"Authorization": "Bearer secret-token-123"}
    )
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_post_with_invalid_bearer_no_origin_rejected(monkeypatch) -> None:
    """An invalid Bearer token does NOT short-circuit -- falls through to Origin.

    ESCAPE: test_post_with_invalid_bearer_no_origin_rejected
      CLAIM: POST with ``Authorization: Bearer <wrong>`` and no Origin -> 403.
             Critically, this is NOT a 401 from the bearer branch -- the
             middleware must FALL THROUGH to the Origin check and 403.
      PATH:  TestClient -> OriginCheckMiddleware -> Authorization parses as
             Bearer -> load_token() returns patched value ->
             secrets.compare_digest() returns False -> fall through to
             Origin branch -> no Origin -> 403.
      CHECK: status == 403 and body == "Forbidden: invalid Origin".
      MUTATION:
        - Returning 401 from the bearer-mismatch branch instead of falling
          through -> status assertion fails (status 401 != 403).
        - Allowing on any Bearer prefix regardless of value -> 200, fails.
        - Comparing against the wrong load_token target -> false negative.
      ESCAPE: A middleware that always 403s state-changing requests
              regardless of headers would pass this row but fail the
              valid-bearer row above.
      IMPACT: Returning 401 here would leak token-validity oracle behavior;
              the design contract is to fall through to Origin so the
              status code is identical to "no auth attempted".
    """
    monkeypatch.setattr(
        "spellbook.admin.auth.load_token", lambda: "secret-token-123"
    )
    client = _make_client()
    resp = client.post(
        "/mutate", headers={"Authorization": "Bearer wrong-token"}
    )
    assert resp.status_code == 403
    assert resp.text == "Forbidden: invalid Origin"


def test_post_with_valid_bearer_bad_origin_allowed(monkeypatch) -> None:
    """A valid Bearer token wins even when the Origin is bad.

    ESCAPE: test_post_with_valid_bearer_bad_origin_allowed
      CLAIM: POST with valid bearer AND ``Origin: http://evil.com`` -> 200.
             The bearer exemption takes precedence over Origin.
      PATH:  TestClient -> OriginCheckMiddleware -> Authorization parses
             as valid Bearer -> pass through -> route -> 200 "ok".
      CHECK: status == 200 and body == "ok".
      MUTATION:
        - Checking Origin BEFORE bearer -> evil.com would 403 first, this
          row fails.
        - Requiring both bearer AND valid Origin -> 403, fails.
      ESCAPE: A middleware that allowed everything would also pass; the
              missing-Origin + no-bearer row guards against it.
      IMPACT: The CLI may send requests from contexts where the Origin
              header (if any) is meaningless; bearer must take precedence.
    """
    monkeypatch.setattr(
        "spellbook.admin.auth.load_token", lambda: "secret-token-123"
    )
    client = _make_client()
    resp = client.post(
        "/mutate",
        headers={
            "Authorization": "Bearer secret-token-123",
            "Origin": "http://evil.com",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "ok"
