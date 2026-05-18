import time

import tripwire


class TestHandoffToken:
    def test_create_handoff_token_returns_string(self, mock_mcp_token):
        from spellbook.admin.auth import create_handoff_token

        token = create_handoff_token()
        assert isinstance(token, str)
        assert len(token) > 20

    def test_validate_handoff_token_consumes_on_first_use(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_handoff_token,
            validate_handoff_token,
        )

        token = create_handoff_token()
        assert validate_handoff_token(token) is True
        assert validate_handoff_token(token) is False  # consumed

    def test_validate_handoff_token_rejects_expired(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_handoff_token,
            validate_handoff_token,
            _handoff_tokens,
        )

        token = create_handoff_token()
        _handoff_tokens[token] = time.time() - 1  # expired
        assert validate_handoff_token(token) is False

    def test_validate_handoff_token_rejects_unknown(self, mock_mcp_token):
        from spellbook.admin.auth import validate_handoff_token

        assert validate_handoff_token("nonexistent-token") is False


class TestSessionCookie:
    def test_create_and_validate_session_cookie(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_session_cookie,
            validate_session_cookie,
        )

        cookie = create_session_cookie("test-session-id")
        session_id = validate_session_cookie(cookie)
        assert session_id == "test-session-id"

    def test_validate_session_cookie_rejects_tampered(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_session_cookie,
            validate_session_cookie,
        )

        cookie = create_session_cookie("test-session-id")
        tampered = cookie[:-5] + "XXXXX"
        assert validate_session_cookie(tampered) is None

    def test_validate_session_cookie_rejects_expired(self, mock_mcp_token):
        from spellbook.admin.auth import validate_session_cookie, _get_signing_key
        import json
        import hashlib
        import hmac as hmac_mod

        payload = json.dumps({"sid": "test", "exp": time.time() - 1})
        sig = hmac_mod.new(
            _get_signing_key(), payload.encode(), hashlib.sha256
        ).hexdigest()
        cookie = f"{payload}|{sig}"
        assert validate_session_cookie(cookie) is None

    def test_validate_session_cookie_rejects_malformed(self, mock_mcp_token):
        from spellbook.admin.auth import validate_session_cookie

        assert validate_session_cookie("not-a-valid-cookie") is None
        assert validate_session_cookie("") is None


class TestWSTicket:
    def test_create_ws_ticket_returns_string(self, mock_mcp_token):
        from spellbook.admin.auth import create_ws_ticket

        ticket = create_ws_ticket()
        assert isinstance(ticket, str)
        assert len(ticket) > 10

    def test_validate_ws_ticket_consumes_on_first_use(self, mock_mcp_token):
        from spellbook.admin.auth import create_ws_ticket, validate_ws_ticket

        ticket = create_ws_ticket()
        assert validate_ws_ticket(ticket) is True
        assert validate_ws_ticket(ticket) is False

    def test_validate_ws_ticket_rejects_expired(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_ws_ticket,
            validate_ws_ticket,
            _ws_tickets,
        )

        ticket = create_ws_ticket()
        _ws_tickets[ticket] = time.time() - 1
        assert validate_ws_ticket(ticket) is False


class TestLogin:
    def test_login_with_correct_token_sets_cookie(self, unauthenticated_client, mock_mcp_token):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": mock_mcp_token},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "spellbook_admin_session" in response.cookies

    def test_login_sets_cookie_with_admin_path(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_login_sets_cookie_with_admin_path
          CLAIM: A successful POST /api/auth/login sets the
                 spellbook_admin_session cookie with ``Path=/admin``, scoping
                 it to the admin app and preventing the browser from sending
                 it to sibling paths like /mcp or /health.
          PATH:  login handler -> JSONResponse.set_cookie(..., path="/admin")
                 -> Starlette serializes Set-Cookie header with Path attribute.
          CHECK: Status 200 and the raw Set-Cookie header for
                 ``spellbook_admin_session`` contains ``Path=/admin``.
          MUTATION: If the path kwarg was missing (default), Starlette emits
                    ``Path=/`` and the assertion fails. If the path kwarg was
                    ``/admin/`` (trailing slash), the assertion still passes
                    on substring match but the deliberate exact form is
                    pinned by the equality reconstruction below.
          ESCAPE: A handler that wrote ``Path=/admin/foo`` would still
                  contain ``Path=/admin`` as a prefix; this is an accepted
                  loosening since "/admin" is itself a substring of any
                  more-specific path and the parent-route policy is the M2
                  contract.
          IMPACT: Without Path=/admin, the cookie is sent to /mcp and
                  /health, widening the cookie's exposure surface (M2).
        """
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": mock_mcp_token},
        )
        assert response.status_code == 200
        set_cookie_headers = [
            v.decode() for k, v in response.headers.raw if k.lower() == b"set-cookie"
        ]
        session_headers = [
            h for h in set_cookie_headers if "spellbook_admin_session=" in h
        ]
        assert len(session_headers) == 1, (
            f"Expected exactly one spellbook_admin_session Set-Cookie, got: "
            f"{set_cookie_headers!r}"
        )
        assert "Path=/admin" in session_headers[0], (
            f"Set-Cookie header missing Path=/admin: {session_headers[0]!r}"
        )

    def test_login_with_wrong_token_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_login_with_empty_password_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": ""},
        )
        assert response.status_code == 401


class TestCheckAuth:
    def test_check_with_valid_session_returns_200(self, client):
        response = client.get("/api/auth/check")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_check_without_session_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/auth/check")
        assert response.status_code == 401


class TestHandoffPost:
    """POST /api/auth/handoff: bearer-authed mint of opaque single-use handoff URL.

    Replaces the pre-Task-8 exchange-token flow that consumed a JSON body and
    returned an exchange_token. The new endpoint reads ``Authorization: Bearer
    <mcp_token>``, mints a server-side opaque handoff id via
    ``create_handoff_token()``, and returns ``{login_url}`` whose path is
    ``/admin/api/auth/handoff/<id>``. Tokens never appear in the URL.
    """

    def test_handoff_post_with_valid_bearer_returns_login_url(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_handoff_post_with_valid_bearer_returns_login_url
          CLAIM: A valid bearer mints a server-side handoff and returns an
                 absolute loopback URL containing the handoff id.
          PATH:  OriginCheck (bearer-exempt) -> route handler ->
                 secrets.compare_digest -> create_handoff_token ->
                 build login_url from app.state.bound_port.
          CHECK: 200, JSON has login_url, URL matches
                 http://127.0.0.1:<port>/admin/api/auth/handoff/<id>,
                 id is at least 32 chars (token_urlsafe(32) default).
          MUTATION: If the handler returned the OLD ``{"exchange_token": ...}``
                    shape, the regex match would fail. If it built a relative
                    URL, the ``http://127.0.0.1:`` prefix would be missing. If
                    the bound_port lookup was wrong, the port digits would
                    diverge from app.state.bound_port.
          ESCAPE: A handler that returned a fixed string matching the regex
                  but never actually stored a handoff in ``_handoff_tokens``
                  would still pass this single assertion. The companion
                  redirect test below closes that hole by consuming the URL.
          IMPACT: Loss of single-use semantics would let an attacker who
                  observed the URL replay it.
        """
        import re
        from spellbook.admin.routes.auth import router  # noqa: F401 - import-time check

        response = unauthenticated_client.post(
            "/api/auth/handoff",
            headers={"Authorization": f"Bearer {mock_mcp_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"login_url"}
        # Port comes from the admin app's bound_port (default 8765 per get_env).
        bound_port = unauthenticated_client.app.state.bound_port
        pattern = (
            rf"^http://127\.0\.0\.1:{bound_port}/admin/api/auth/handoff/[A-Za-z0-9_-]{{32,}}$"
        )
        assert re.match(pattern, body["login_url"]), (
            f"login_url {body['login_url']!r} does not match {pattern!r}"
        )

    def test_handoff_post_without_bearer_returns_401(self, unauthenticated_client):
        """
        ESCAPE: test_handoff_post_without_bearer_returns_401
          CLAIM: With a valid Origin (conftest default) but no Authorization
                 header, the request passes OriginCheck and the route handler
                 rejects with 401.
          PATH:  OriginCheck sees valid Origin, allows -> route handler reads
                 missing Authorization header -> 401.
          CHECK: status_code == 401 and detail is "Invalid token".
          MUTATION: If the handler accepted the absent header as a successful
                    auth (e.g. compared "" to "" with compare_digest after a
                    missing-stored-token branch), the status would be 200.
          ESCAPE: A handler that 403'd for the wrong reason (e.g. Origin
                  check failure) would also produce a non-200, but the
                  detail string assertion pins the right failure mode.
          IMPACT: A 200 here would mean unauthenticated handoff minting,
                  which is the very leak Task 8 is closing.
        """
        response = unauthenticated_client.post("/api/auth/handoff")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid token"}

    def test_handoff_post_with_invalid_bearer_returns_401(self, unauthenticated_client):
        """
        ESCAPE: test_handoff_post_with_invalid_bearer_returns_401
          CLAIM: A bearer whose token does NOT match load_token() is rejected
                 with 401 by the route (not silently bypassed by the
                 OriginCheck bearer-exemption, which only exempts on match).
          PATH:  OriginCheck: bearer present but wrong, falls through to
                 Origin (valid in conftest) -> route handler -> 401.
          CHECK: status_code == 401, detail == "Invalid token".
          MUTATION: If the handler short-circuited on bearer presence rather
                    than equality, it would 200. If compare_digest was
                    replaced by ``==``, the test still passes but a timing
                    oracle remains -- out of scope for this assertion.
          ESCAPE: A handler that returned 403 here would also fail. The
                  detail string pin makes the failure mode explicit.
          IMPACT: A 200 here means token forgery succeeds.
        """
        response = unauthenticated_client.post(
            "/api/auth/handoff",
            headers={"Authorization": "Bearer not-the-right-token"},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid token"}

    def test_handoff_post_with_lowercase_bearer_scheme_returns_login_url(
        self, unauthenticated_client, mock_mcp_token
    ):
        """RFC 7235: scheme matching on POST /handoff is case-insensitive.

        ESCAPE: test_handoff_post_with_lowercase_bearer_scheme_returns_login_url
          CLAIM: POST /api/auth/handoff with ``Authorization: bearer <mcp>``
                 (lowercase scheme) succeeds and returns a login_url, matching
                 the ``Bearer`` variant under RFC 7235's case-insensitivity.
          PATH:  OriginCheck (bearer-exempt; lowercase scheme accepted) ->
                 route handler (lowercase scheme accepted) -> compare_digest
                 -> create_handoff_token -> build login_url.
          CHECK: 200, body is a dict with sole key ``login_url``, and the URL
                 matches the same regex used by the canonical
                 valid-bearer test.
          MUTATION:
            - Case-sensitive scheme check in the route -> ``provided`` stays
              ``""`` -> compare_digest fails -> 401, status assertion fails.
            - Case-sensitive scheme check in the OriginCheckMiddleware ->
              bearer exemption misses, request falls through to Origin
              (default valid Origin from conftest), reaches route, route
              ALSO case-sensitively rejects -> 401, status assertion fails.
            - Wrong slice index after lowering -> compare_digest false -> 401.
          ESCAPE: A handler that always 200'd regardless of bearer would pass
                  this row but fail the invalid-bearer tests above.
          IMPACT: Without case-insensitive scheme matching at the route,
                  RFC-compliant lowercase-bearer clients cannot mint
                  handoff URLs.
        """
        import re

        response = unauthenticated_client.post(
            "/api/auth/handoff",
            headers={"Authorization": f"bearer {mock_mcp_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"login_url"}
        bound_port = unauthenticated_client.app.state.bound_port
        pattern = (
            rf"^http://127\.0\.0\.1:{bound_port}/admin/api/auth/handoff/[A-Za-z0-9_-]{{32,}}$"
        )
        assert re.match(pattern, body["login_url"]), (
            f"login_url {body['login_url']!r} does not match {pattern!r}"
        )

    def test_handoff_bad_bearer_with_good_origin_returns_401(
        self, unauthenticated_client
    ):
        """Real-route sibling to test_origin_bearer_bad_token_with_good_origin_returns_401.

        ESCAPE: test_handoff_bad_bearer_with_good_origin_returns_401
          CLAIM: A wrong Bearer token + a valid Origin reaches the real
                 ``/api/auth/handoff`` route and the route 401s. The
                 middleware-level test in test_origin_middleware.py covers the
                 same behavior against a stub app; this test pins the contract
                 against the real handler.
          PATH:  OriginCheck: bearer wrong, fall through; Origin valid, allow
                 -> route handler validates bearer with compare_digest -> 401.
          CHECK: status_code == 401, detail == "Invalid token".
          MUTATION: If the route handler 200'd on a wrong bearer (e.g. the
                    compare_digest branch was inverted), this test fails.
          ESCAPE: A handler that 403'd here would also fail. detail pin
                  guards the failure mode.
          IMPACT: Loss of bearer integrity at the route layer.
        """
        response = unauthenticated_client.post(
            "/api/auth/handoff",
            headers={
                "Authorization": "Bearer definitely-not-correct",
                "Origin": "http://127.0.0.1:8765",
            },
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid token"}


class TestHandoffGet:
    """GET /api/auth/handoff/{id}: opaque-id consumption, sets cookie, 302."""

    def _mint(self, client, mcp_token):
        """Helper: POST /handoff to get login_url, return the handoff id."""
        response = client.post(
            "/api/auth/handoff",
            headers={"Authorization": f"Bearer {mcp_token}"},
        )
        assert response.status_code == 200
        login_url = response.json()["login_url"]
        # /admin/api/auth/handoff/<id>
        return login_url.rsplit("/", 1)[1], login_url

    def test_handoff_get_valid_id_sets_cookie_and_redirects(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_handoff_get_valid_id_sets_cookie_and_redirects
          CLAIM: GETting a freshly-minted handoff id consumes the id, sets
                 a signed session cookie, and returns a 302 to /admin/.
          PATH:  OriginCheck (GET is safe method, passes) -> route handler ->
                 validate_handoff_token (pop+expiry check) ->
                 create_session_cookie -> RedirectResponse.
          CHECK: status 302, Location == /admin/, Set-Cookie present and
                 cookie value validates via validate_session_cookie.
          MUTATION: If RedirectResponse used 307, status_code check fails.
                    If the handler skipped set_cookie, the cookie assertion
                    fails. If validate_handoff_token was not called, the
                    second consumption would still succeed (covered by
                    test_handoff_get_replayed_returns_404).
          ESCAPE: A handler that always 302'd to /admin/ without consuming
                  the id would pass this single test but fail the replay
                  test. The combination forces correct semantics.
          IMPACT: Loss of single-use semantics is the H2 leak this fixes.
        """
        from spellbook.admin.auth import validate_session_cookie

        handoff_id, _ = self._mint(unauthenticated_client, mock_mcp_token)
        # Do not follow redirects so we can inspect Set-Cookie.
        response = unauthenticated_client.get(
            f"/api/auth/handoff/{handoff_id}", follow_redirects=False
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/"
        # Parse the Set-Cookie header directly. The cookie value contains
        # ``|``, ``:``, and ``,`` (from the signed JSON payload), so the
        # Set-Cookie machinery wraps it in double quotes per RFC 6265.
        # ``http.cookies.SimpleCookie`` unquotes that for us, matching
        # what a real browser sends back on subsequent requests.
        from http.cookies import SimpleCookie

        set_cookie_headers = [
            v.decode() for k, v in response.headers.raw if k.lower() == b"set-cookie"
        ]
        assert any(
            "spellbook_admin_session=" in h for h in set_cookie_headers
        ), f"No spellbook_admin_session in {set_cookie_headers!r}"
        jar = SimpleCookie()
        for header in set_cookie_headers:
            jar.load(header)
        morsel = jar.get("spellbook_admin_session")
        assert morsel is not None
        # The cookie value validates as a real session cookie.
        assert validate_session_cookie(morsel.value) is not None

    def test_handoff_sets_cookie_with_admin_path(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_handoff_sets_cookie_with_admin_path
          CLAIM: A successful GET /api/auth/handoff/{id} sets the
                 spellbook_admin_session cookie with ``Path=/admin``, matching
                 the login endpoint's scoping (M2).
          PATH:  POST /handoff to mint id -> GET /handoff/{id} -> handler ->
                 RedirectResponse.set_cookie(..., path="/admin") -> Set-Cookie
                 header.
          CHECK: Status 302 and the Set-Cookie header for
                 ``spellbook_admin_session`` contains ``Path=/admin``.
          MUTATION: If the path kwarg was missing on the handoff_consume's
                    set_cookie call, the header would carry ``Path=/`` and
                    the assertion fails. If only the login path was fixed
                    but not the handoff path, this test would catch the
                    drift.
          ESCAPE: A handler that wrote ``Path=/admin/foo`` would still
                  contain ``Path=/admin`` as a prefix; same loosening as in
                  the login test, deliberate.
          IMPACT: Without Path=/admin on the handoff-issued cookie, the
                  M2 mitigation is incomplete: bearer-handoff sessions
                  would still send the cookie to /mcp and /health.
        """
        # Mint a handoff id, then consume it.
        mint_response = unauthenticated_client.post(
            "/api/auth/handoff",
            headers={"Authorization": f"Bearer {mock_mcp_token}"},
        )
        assert mint_response.status_code == 200
        login_url = mint_response.json()["login_url"]
        handoff_id = login_url.rsplit("/", 1)[1]
        response = unauthenticated_client.get(
            f"/api/auth/handoff/{handoff_id}", follow_redirects=False
        )
        assert response.status_code == 302
        set_cookie_headers = [
            v.decode() for k, v in response.headers.raw if k.lower() == b"set-cookie"
        ]
        session_headers = [
            h for h in set_cookie_headers if "spellbook_admin_session=" in h
        ]
        assert len(session_headers) == 1, (
            f"Expected exactly one spellbook_admin_session Set-Cookie, got: "
            f"{set_cookie_headers!r}"
        )
        assert "Path=/admin" in session_headers[0], (
            f"Set-Cookie header missing Path=/admin: {session_headers[0]!r}"
        )

    def test_handoff_get_replayed_returns_404(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_handoff_get_replayed_returns_404
          CLAIM: A handoff id can be consumed exactly once. The second GET
                 returns 404 (NOT 410, to avoid existence oracle).
          PATH:  First GET pops the id from _handoff_tokens (success).
                 Second GET pops returns None -> validate returns False ->
                 404.
          CHECK: First call 302; second call 404.
          MUTATION: If the handler returned 200/302 on repeat consumption,
                    or 410/401 (which would oracle the existence of the id),
                    the assertion fails.
          ESCAPE: A handler that 404'd for ALL ids (never minting cookies)
                  would fail the first 302 assertion. Pairing both pins
                  the single-use semantic.
          IMPACT: Replay attacks (browser back/forward, history scrape).
        """
        handoff_id, _ = self._mint(unauthenticated_client, mock_mcp_token)
        first = unauthenticated_client.get(
            f"/api/auth/handoff/{handoff_id}", follow_redirects=False
        )
        assert first.status_code == 302
        second = unauthenticated_client.get(
            f"/api/auth/handoff/{handoff_id}", follow_redirects=False
        )
        assert second.status_code == 404

    def test_handoff_get_expired_returns_404(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_handoff_get_expired_returns_404
          CLAIM: After the 60s TTL expires (advance time +61s), the GET
                 returns 404. validate_handoff_token's expiry branch is
                 exercised.
          PATH:  tripwire mock of spellbook.admin.auth:time.time returns
                 real_now+61 -> GET -> validate_handoff_token pops and sees
                 expiry < now -> False -> 404.
          CHECK: status_code == 404.
          MUTATION: If the TTL was bumped to >60s or the comparison was
                    inverted, the test fails. If the handler returned 401
                    here, it would oracle existence.
          ESCAPE: A handler that 404'd for ALL inputs would pass this but
                  fail the valid-id test above.
          IMPACT: A leaked handoff id reusable past its TTL extends the
                  attack window.
        """
        import time as time_mod

        # Mint the handoff OUTSIDE the sandbox so create_handoff_token() uses
        # real wall-clock time (expiry = real_now + 60).
        handoff_id, _ = self._mint(unauthenticated_client, mock_mcp_token)
        real_time = time_mod.time

        # Inside the sandbox, every spellbook.admin.auth time.time() call
        # reports real_now + 61, putting the freshly-minted token past its
        # 60s TTL. The GET path invokes time.time() twice
        # (_cleanup_expired's `now`, then validate_handoff_token's
        # `time.time() < expiry`), so chain two FIFO side effects.
        advance = tripwire.mock("spellbook.admin.auth:time.time")
        advance.calls(lambda: real_time() + 61).calls(lambda: real_time() + 61)

        with tripwire:
            response = unauthenticated_client.get(
                f"/api/auth/handoff/{handoff_id}", follow_redirects=False
            )

        assert response.status_code == 404
        with tripwire.in_any_order():
            advance.assert_call(args=(), kwargs={})
            advance.assert_call(args=(), kwargs={})

    def test_handoff_get_unknown_returns_404(self, unauthenticated_client):
        """
        ESCAPE: test_handoff_get_unknown_returns_404
          CLAIM: A handoff id that was never minted returns 404.
          PATH:  GET -> validate_handoff_token pops None -> False -> 404.
          CHECK: status_code == 404.
          MUTATION: If the handler 401'd or 200'd for unknown ids, the
                    test fails.
          ESCAPE: A handler that 404'd for ALL ids would pass this but
                  fail the valid-id test.
          IMPACT: Oracle leak or unauthenticated session minting.
        """
        response = unauthenticated_client.get(
            "/api/auth/handoff/nonexistent-id-that-was-never-minted",
            follow_redirects=False,
        )
        assert response.status_code == 404

    def test_concurrent_handoffs_produce_distinct_ids(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_concurrent_handoffs_produce_distinct_ids
          CLAIM: Two POST /handoff calls produce distinct ids, AND each id
                 is individually consumable.
          PATH:  Two POST -> two distinct create_handoff_token() calls
                 (token_urlsafe(32) is collision-free for practical purposes)
                 -> two GETs -> two 302s.
          CHECK: id1 != id2; both GETs return 302.
          MUTATION: If create_handoff_token cached/reused a token across
                    calls (e.g. module-level singleton), id1 == id2. If
                    the GET consumed the wrong store entry, the second
                    GET would 404.
          ESCAPE: A handler that always 302'd regardless of id state would
                  pass the second-and-third assertions but the first
                  inequality still pins distinctness.
          IMPACT: Token reuse would break concurrent CLI logins.
        """
        id1, _ = self._mint(unauthenticated_client, mock_mcp_token)
        id2, _ = self._mint(unauthenticated_client, mock_mcp_token)
        assert id1 != id2
        r1 = unauthenticated_client.get(
            f"/api/auth/handoff/{id1}", follow_redirects=False
        )
        r2 = unauthenticated_client.get(
            f"/api/auth/handoff/{id2}", follow_redirects=False
        )
        assert r1.status_code == 302
        assert r2.status_code == 302


class TestLogout:
    """POST /api/auth/logout: clears the session cookie."""

    def test_logout_deletes_cookie_with_admin_path(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_logout_deletes_cookie_with_admin_path
          CLAIM: POST /api/auth/logout emits a Set-Cookie deletion header
                 for ``spellbook_admin_session`` scoped to ``Path=/admin``,
                 so the browser's cookie store key matches the one written
                 by /login and /handoff (both at Path=/admin) and the
                 deletion actually evicts the cookie.
          PATH:  Authenticate via /login -> POST /logout -> handler ->
                 JSONResponse.delete_cookie(name, path="/admin") -> Starlette
                 emits ``Set-Cookie: spellbook_admin_session=""; Max-Age=0;
                 Path=/admin; ...``.
          CHECK: Status 200 and the deletion Set-Cookie header contains both
                 ``spellbook_admin_session=`` and ``Path=/admin``. Browser
                 cookie-eviction semantics require the deletion's path to
                 match the original cookie's path, so this is the load-
                 bearing assertion.
          MUTATION: If the path kwarg on delete_cookie was missing, the
                    deletion header would carry ``Path=/`` and would not
                    evict the ``Path=/admin``-scoped cookie set by /login;
                    the assertion fails.
          ESCAPE: A handler that emitted a deletion with ``Path=/admin/foo``
                  would still contain the substring ``Path=/admin`` and
                  pass this test, but would also fail to evict the cookie
                  in a real browser. The accompanying /admin-scoped
                  login/handoff tests pin the parent-path contract.
          IMPACT: Without matching Path=/admin on the deletion, /logout is
                  a no-op in browsers: the session cookie stays in the
                  cookie jar and continues to be sent to /admin until its
                  Max-Age expires (24h). M2 fix is incomplete.
        """
        # First log in to mint a session cookie (and let httpx capture it
        # in the client jar), then call logout and inspect Set-Cookie.
        login_response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": mock_mcp_token},
        )
        assert login_response.status_code == 200
        logout_response = unauthenticated_client.post("/api/auth/logout")
        assert logout_response.status_code == 200
        set_cookie_headers = [
            v.decode()
            for k, v in logout_response.headers.raw
            if k.lower() == b"set-cookie"
        ]
        session_deletion_headers = [
            h for h in set_cookie_headers if "spellbook_admin_session=" in h
        ]
        assert len(session_deletion_headers) == 1, (
            f"Expected exactly one spellbook_admin_session Set-Cookie on "
            f"logout, got: {set_cookie_headers!r}"
        )
        assert "Path=/admin" in session_deletion_headers[0], (
            f"Logout Set-Cookie header missing Path=/admin: "
            f"{session_deletion_headers[0]!r}"
        )


class TestOldEndpointsRemoved:
    """Task 8 deletes /api/auth/exchange and /api/auth/callback entirely."""

    def test_old_exchange_endpoint_removed(
        self, unauthenticated_client, mock_mcp_token
    ):
        """
        ESCAPE: test_old_exchange_endpoint_removed
          CLAIM: POST /api/auth/exchange no longer accepts JSON bodies or
                 returns an exchange_token. The route is unmounted (FastAPI
                 returns 405 because no POST handler exists at that path)
                 and the response body does NOT contain ``exchange_token``.
          PATH:  POST hits FastAPI route table -> no POST handler at
                 /api/auth/exchange -> 405 Method Not Allowed (or 404 if
                 the path is also unrouted on every method).
          CHECK: status_code != 200 AND body does not contain the literal
                 substring ``exchange_token``. Pinning the absence of the
                 OLD success signature is the actual security contract.
          MUTATION: If the old @router.post("/exchange") line was left in
                    auth.py with the same body shape, the response would
                    be 200 with ``{"exchange_token": "..."}``; both
                    assertions would fail.
          ESCAPE: A handler that returned 200 with a body that happened
                  to omit the literal string ``exchange_token`` (e.g.
                  rename to ``token``) would pass the substring check but
                  fail the status-code check.
          IMPACT: H2 leak persists if the old endpoint still issues
                  exchange tokens that the CLI could feed into the old
                  /callback URL.
        """
        response = unauthenticated_client.post(
            "/api/auth/exchange",
            json={"token": mock_mcp_token},
            headers={"Authorization": f"Bearer {mock_mcp_token}"},
        )
        assert response.status_code != 200
        assert "exchange_token" not in response.text

    def test_old_callback_endpoint_removed(self, unauthenticated_client):
        """
        ESCAPE: test_old_callback_endpoint_removed
          CLAIM: GET /api/auth/callback?auth=<anything> no longer sets a
                 session cookie and no longer redirects to /admin/. The
                 route is unmounted; the SPA fallback may serve index.html
                 (200), but it MUST NOT issue a ``spellbook_admin_session``
                 cookie. The security contract is "no cookie issuance from
                 this URL", not "specific status code".
          PATH:  GET hits FastAPI route table -> no /callback handler ->
                 falls through to SPA fallback (serves index.html, no
                 cookie) OR 404 if SPA fallback is absent.
          CHECK: No ``Set-Cookie`` header for ``spellbook_admin_session``
                 in the response, AND the response is not a redirect to
                 /admin/ (which was the OLD success signature).
          MUTATION: If the old @router.get("/callback") line was left in
                    auth.py and was hit with a stub valid token, the
                    response would be a 302 with ``Set-Cookie:
                    spellbook_admin_session=...``. The cookie assertion
                    catches that.
          ESCAPE: A residual route that 401'd (invalid token) would not
                  set a cookie and would pass the cookie assertion. The
                  redirect-not-to-admin assertion guards the success
                  path. Both holes are not the H2 leak (no cookie issued
                  on invalid input is the correct behavior).
          IMPACT: H2 leak persists if the old endpoint still sets session
                  cookies from URL-borne tokens.
        """
        response = unauthenticated_client.get(
            "/api/auth/callback?auth=anything-at-all", follow_redirects=False
        )
        # Old route minted a session cookie on success; the new world MUST
        # never set this cookie from a URL query parameter.
        assert "spellbook_admin_session" not in response.cookies
        set_cookie_headers = [
            v for k, v in response.headers.raw if k.lower() == b"set-cookie"
        ]
        assert not any(
            b"spellbook_admin_session" in h for h in set_cookie_headers
        ), f"Unexpected session cookie in headers: {set_cookie_headers}"
        # Old route redirected to /admin/ on success; new world MUST NOT.
        if response.status_code in (301, 302, 303, 307, 308):
            assert response.headers.get("location") != "/admin/"
