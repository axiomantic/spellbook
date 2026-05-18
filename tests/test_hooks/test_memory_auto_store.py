"""Tests for automatic memory auto-store on hook events.

Covers UserPromptSubmit pattern-based self-capture of feedback/correction/
confirmation/remember prompts, the rule-dictation exception, and the Stop
hook handler that harvests ``<memory-candidate>`` blocks from the final
assistant message.

All mocks use tripwire per project policy (see AGENTS.md, "Testing with
Tripwire"). ``monkeypatch.setattr`` of module attributes is forbidden.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import tripwire

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _CountingMock:
    """Wrap a tripwire mock so the test can drain its timeline at end.

    Holds the underlying mock + a fire counter populated by the SUT-
    facing callable. Tests don't normally interact with this directly;
    ``mock_http.track(counting_mock)`` registers it for drain().
    """

    def __init__(self, tripwire_mock):
        self.tripwire_mock = tripwire_mock
        self.n_calls = 0


def _make_counting(path: str, fn, budget: int = 50):
    """Create a tripwire mock with a FIFO budget of repeatable calls.

    Tripwire's ``.calls(fn)`` enqueues one consumable side-effect; the
    SUT may call the same mock several times, so we pre-stack ``budget``
    copies. Each is registered with ``required(False)`` so unused
    entries do not flag as UnusedMocksError at teardown.

    ``budget=50`` is generous enough for the per-test SUT call patterns
    here (a few _http_post, _get_config_value, _resolve_git_context per
    test); raise it if a future test exhausts the queue.
    """
    cm = _CountingMock(tripwire.mock(path))

    def _wrapped(*args, **kwargs):
        cm.n_calls += 1
        return fn(*args, **kwargs)

    for _ in range(budget):
        cm.tripwire_mock.__call__.required(False).calls(_wrapped)
    return cm


@pytest.fixture
def config_enabled():
    """Force memory.auto_store + memory.auto_recall to True.

    Registers a tripwire mock for ``spellbook_hook._get_config_value``
    via a counting wrapper, so the test can drain the mock's timeline
    at end via ``mock_http.track(config_enabled)``.
    """
    def fake_config_value(key, default=None):
        if key in ("memory.auto_store", "memory.auto_recall"):
            return True
        return default

    return _make_counting("spellbook_hook:_get_config_value", fake_config_value)


@pytest.fixture
def config_store_disabled():
    """Force memory.auto_store to False, auto_recall True."""
    def fake_config_value(key, default=None):
        if key == "memory.auto_store":
            return False
        if key == "memory.auto_recall":
            return True
        return default

    return _make_counting("spellbook_hook:_get_config_value", fake_config_value)


@pytest.fixture
def mock_git_context():
    """Stub _resolve_git_context so tests do not depend on git state."""
    return _make_counting(
        "spellbook_hook:_resolve_git_context",
        lambda cwd: ("/repo/proj", "main"),
    )


@pytest.fixture
def mock_http():
    """Capture _http_post calls and stage optional responses per-URL.

    The controller's ``calls`` list is the test's observable assertion
    surface (existing tests inspect it for URL/payload/timeout shape).
    ``tripwire.mock.calls(fake)`` routes every ``_http_post`` invocation
    through ``fake``, which records the call onto ``controller.calls``
    before returning the staged response. The mock is registered with
    ``required(False)`` because many tests assert zero calls.

    Each test using this fixture must call ``mock_http.drain()`` after
    the ``with tripwire:`` block has exited. The drain helper issues
    one wildcard ``assert_call`` per recorded call, satisfying
    tripwire's "every intercepted call must be asserted" contract
    without weakening the test's own content assertions against
    ``controller.calls``.
    """
    from dirty_equals import AnyThing

    class Controller:
        def __init__(self):
            self.calls: list[dict] = []
            self.responses: dict[str, object] = {}
            self.raise_exc: Exception | None = None
            self._tripwire_mock = None
            self._other_mocks: list = []
            self._custom_handler = None

        def set_exception(self, exc: Exception) -> None:
            self.raise_exc = exc

        def set_response(self, url_suffix: str, response: object) -> None:
            self.responses[url_suffix] = response

        def set_handler(self, fn) -> None:
            """Override the default URL-keyed response dispatch.

            ``fn(url, payload, timeout)`` is called instead of the
            response-map lookup. Useful for tests that need per-call
            stateful behavior (e.g. flaky-on-second-call). The handler
            is still called inside the same tripwire side-effect entry,
            so ``controller.calls`` still records every call before the
            handler runs.
            """
            self._custom_handler = fn

        def drain(self) -> None:
            """Drain tripwire timeline for _http_post + all tracked mocks."""
            assert self._tripwire_mock is not None
            with tripwire.in_any_order():
                for _ in self.calls:
                    self._tripwire_mock.assert_call(
                        args=AnyThing, kwargs=AnyThing, returned=AnyThing,
                    )
                for counting in self._other_mocks:
                    for _ in range(counting.n_calls):
                        counting.tripwire_mock.assert_call(
                            args=AnyThing, kwargs=AnyThing, returned=AnyThing,
                        )

        def track(self, counting_mock):
            """Register an auxiliary _CountingMock for drain() to consume."""
            self._other_mocks.append(counting_mock)

    controller = Controller()

    def fake_http_post(url, payload, timeout=5):
        controller.calls.append({"url": url, "payload": payload, "timeout": timeout})
        if controller.raise_exc is not None:
            raise controller.raise_exc
        if controller._custom_handler is not None:
            return controller._custom_handler(url, payload, timeout)
        for suffix, resp in controller.responses.items():
            if url.endswith(suffix):
                return resp
        return None

    http_mock = tripwire.mock("spellbook_hook:_http_post")
    # Pre-stack a generous FIFO of callable side-effects so the SUT can
    # invoke _http_post multiple times per test without exhausting the
    # queue. .required(False) on each entry ensures no UnusedMocksError.
    for _ in range(50):
        http_mock.__call__.required(False).calls(fake_http_post)
    controller._tripwire_mock = http_mock
    return controller


# ---------------------------------------------------------------------------
# UserPromptSubmit auto-store behavior
# ---------------------------------------------------------------------------


class TestUserPromptAutoStore:
    def test_correction_prompt_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "Actually use ruff instead of flake8 for linting"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == [{
            "url": "/api/memory/unconsolidated",
            "payload": {
                "project": "repo-proj",
                "branch": "main",
                "type": "feedback",
                "content": prompt,
                "tags": "auto-store,user-prompt,correction",
                "citations": "",
                "source": "user_prompt_submit",
            },
            "timeout": 5,
        }]
        mock_http.drain()
    def test_dont_prefix_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "Don't mock the database in integration tests"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == [{
            "url": "/api/memory/unconsolidated",
            "payload": {
                "project": "repo-proj",
                "branch": "main",
                "type": "feedback",
                "content": prompt,
                "tags": "auto-store,user-prompt,correction",
                "citations": "",
                "source": "user_prompt_submit",
            },
            "timeout": 5,
        }]
        mock_http.drain()
    def test_confirmation_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "Yes exactly, that was the right call"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == [{
            "url": "/api/memory/unconsolidated",
            "payload": {
                "project": "repo-proj",
                "branch": "main",
                "type": "feedback",
                "content": "CONFIRMATION: " + prompt,
                "tags": "auto-store,user-prompt,confirmation",
                "citations": "",
                "source": "user_prompt_submit",
            },
            "timeout": 5,
        }]
        mock_http.drain()
    def test_remember_keyword_stores_user_type(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "Remember that I prefer tabs over spaces in Makefiles"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == [{
            "url": "/api/memory/unconsolidated",
            "payload": {
                "project": "repo-proj",
                "branch": "main",
                "type": "user",
                "content": prompt,
                "tags": "auto-store,user-prompt,remember",
                "citations": "",
                "source": "user_prompt_submit",
            },
            "timeout": 5,
        }]
        mock_http.drain()
    def test_rule_dictation_skips_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "Give yourself the rule: always use ruff instead of flake8"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []
        mock_http.drain()
    def test_rule_is_prefix_skips_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "The rule is: use black instead of autopep8"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []
        mock_http.drain()
    def test_add_a_rule_that_says_DOES_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        """`add a rule that says ...` is a remember-style instruction, not a
        dictation where the user wants rule text echoed. It must auto-store."""
        prompt = "Add a rule that says: never push to main directly"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        # Classified via the `never X` correction body pattern -> feedback.
        # (Either correction or user classification is acceptable; the
        # critical behavior is that a POST was issued at all.)
        assert len(mock_http.calls) == 1
        call = mock_http.calls[0]
        assert call["url"].endswith("/api/memory/unconsolidated")
        assert call["payload"]["content"] == prompt
        assert call["payload"]["project"] == "repo-proj"
        mock_http.drain()
    def test_oversized_prompt_skipped_with_log_entry(
        self, mock_http, mock_git_context, config_enabled,
    ):
        """A 2001-char correction prompt must not be POSTed to
        /api/memory/unconsolidated; a diagnostic entry must be routed through
        the daemon's /api/hook-log endpoint with the oversize reason,
        total length, and a 200-char preview.

        Uses exact-equality on the hook-log payload (timestamp frozen) so the
        format is pinned; substring checks would silently allow format drift.

        Time is frozen by mocking ``spellbook_hook._utcnow`` (refactored
        from a bare ``datetime.now(timezone.utc)`` call site) so the timestamp
        in the hook-log payload is deterministic.
        """
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        import datetime as _dt
        frozen = _dt.datetime(2026, 4, 14, 12, 0, 0, tzinfo=_dt.timezone.utc)

        utcnow_mock = _make_counting("spellbook_hook:_utcnow", lambda: frozen)
        mock_http.track(utcnow_mock)

        prompt = "Actually " + ("x" * 2000)  # triggers correction, > 2000 chars
        assert len(prompt) > spellbook_hook._AUTO_STORE_MAX_CONTENT_BYTES

        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")

        # No POST to the unconsolidated memory queue.
        unconsolidated = [
            c for c in mock_http.calls
            if c["url"].endswith("/api/memory/unconsolidated")
        ]
        assert unconsolidated == []

        # Exactly one POST to /api/hook-log with the pinned payload shape.
        hook_log_calls = [
            c for c in mock_http.calls if c["url"].endswith("/api/hook-log")
        ]
        assert len(hook_log_calls) == 1
        payload = hook_log_calls[0]["payload"]
        expected_preview = repr(prompt[:200].replace("\n", " "))
        assert payload["timestamp"] == frozen.isoformat()
        assert payload["event"] == (
            "auto_store_skipped_oversized_prompt:UserPromptSubmit"
        )
        # Traceback ends with the RuntimeError line carrying the detail.
        expected_detail = (
            f"RuntimeError: total_length={len(prompt)} "
            f"preview={expected_preview}"
        )
        assert payload["traceback"].strip().endswith(expected_detail)
        mock_http.drain()
    def test_slash_command_skipped(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "/remember that we use tabs in Go files"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []
        mock_http.drain()
    def test_short_prompt_skipped(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "no don't"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []
        mock_http.drain()
    def test_config_disabled_skips_all(
        self, mock_http, mock_git_context, config_store_disabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_store_disabled)
        prompt = "Don't use that library, use the other one instead"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []
        mock_http.drain()
    def test_non_matching_prompt_does_not_store(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        prompt = "Please explain how the authentication flow works"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []
        mock_http.drain()
# ---------------------------------------------------------------------------
# Stop hook handler
# ---------------------------------------------------------------------------


def _write_transcript(path: Path, assistant_text: str) -> None:
    """Write a minimal JSONL transcript with a single assistant message."""
    msg = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": assistant_text}],
        },
    }
    path.write_text(json.dumps(msg) + "\n", encoding="utf-8")


class TestStopHookHarvest:
    @pytest.fixture(autouse=True)
    def stop_hook_cache_path(self, tmp_path, request):
        """Isolate every Stop-hook test from real on-disk + worker-LLM state.

        Two distinct sources of cross-run pollution previously made these
        tests order-dependent:

        1. The Stop-harvest cache (``~/.local/spellbook/cache/last-stop-
           harvest.json``) — ``_handle_stop`` short-circuits when the
           transcript's text-sha matches a cached entry. The SUT now
           reads this via the ``_get_stop_harvest_cache_path()`` helper
           specifically so tripwire can intercept it.
        2. ``feature_enabled("transcript_harvest")`` reads the user's
           real ``spellbook.json``. If flipped on, the hook takes the
           worker-LLM branch and never POSTs.

        Both are mocked via tripwire (counting wrappers, so the
        ``mock_http.track(...)`` drain protocol keeps the timeline
        clean). If the ``mock_http`` fixture is in use for this test,
        register them; otherwise the test may not be doing Stop-hook
        work and we still install the mocks but rely on each test's
        own ``mock_http.track(...) + drain()`` discipline.
        """
        per_test_cache = tmp_path / "_stop_harvest_cache.json"
        cache_path_mock = _make_counting(
            "spellbook_hook:_get_stop_harvest_cache_path",
            lambda: per_test_cache,
        )

        feature_mock = None
        try:
            # Lazy import: register only when the package is available.
            import spellbook.worker_llm.config  # noqa: F401
            feature_mock = _make_counting(
                "spellbook.worker_llm.config:feature_enabled",
                lambda _name: False,
            )
        except Exception:
            # If the worker-llm package is not importable in this
            # environment, the hook's own try/except already degrades to
            # the regex path; nothing more to stub.
            pass

        # If the test uses mock_http, auto-track the autouse mocks so
        # they participate in drain(). Tests that do not use mock_http
        # are responsible for not invoking the SUT path that fires
        # these mocks (which would otherwise raise UnassertedInteractions).
        try:
            mh = request.getfixturevalue("mock_http")
            mh.track(cache_path_mock)
            if feature_mock is not None:
                mh.track(feature_mock)
        except pytest.FixtureLookupError:
            pass

        return per_test_cache

    def test_stop_hook_harvests_single_candidate(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "Here is what I think.\n"
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>User corrected the test naming convention.</content>\n"
            "  <tags>tests,naming</tags>\n"
            "  <citations>tests/test_x.py:10</citations>\n"
            "</memory-candidate>\n"
            "Done."
        ))
        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert mock_http.calls == [{
            "url": "/api/memory/unconsolidated",
            "payload": {
                "project": "repo-proj",
                "branch": "main",
                "type": "feedback",
                "content": "User corrected the test naming convention.",
                "tags": "tests,naming",
                "citations": "tests/test_x.py:10",
                "source": "stop_hook",
            },
            "timeout": 5,
        }]
        mock_http.drain()

    def test_stop_hook_harvests_multiple_candidates(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>project</type>\n"
            "  <content>Milestone deadline is 2026-05-01.</content>\n"
            "  <tags>deadline</tags>\n"
            "  <citations></citations>\n"
            "</memory-candidate>\n"
            "some intervening text\n"
            "<memory-candidate>\n"
            "  <type>user</type>\n"
            "  <content>Prefers short code reviews.</content>\n"
            "  <tags></tags>\n"
            "  <citations></citations>\n"
            "</memory-candidate>\n"
        ))
        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        url = "/api/memory/unconsolidated"
        assert mock_http.calls == [
            {
                "url": url,
                "payload": {
                    "project": "repo-proj",
                    "branch": "main",
                    "type": "project",
                    "content": "Milestone deadline is 2026-05-01.",
                    "tags": "deadline",
                    "citations": "",
                    "source": "stop_hook",
                },
                "timeout": 5,
            },
            {
                "url": url,
                "payload": {
                    "project": "repo-proj",
                    "branch": "main",
                    "type": "user",
                    "content": "Prefers short code reviews.",
                    "tags": "",
                    "citations": "",
                    "source": "stop_hook",
                },
                "timeout": 5,
            },
        ]
        mock_http.drain()

    def test_stop_hook_ignores_malformed_candidate(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        """Missing <type> tag -> skipped, no POST."""
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <content>No type field, should be ignored.</content>\n"
            "</memory-candidate>\n"
        ))
        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert mock_http.calls == []
        mock_http.drain()

    def test_stop_hook_network_failure_is_fail_open(
        self, tmp_path, mock_http, mock_git_context, config_enabled, stop_hook_cache_path,
    ):
        """Real-world failure: `_http_post` returns None when the daemon is
        unreachable. The Stop hook must still return cleanly AND the text_sha
        must NOT be recorded, so the next Stop invocation retries the harvest.
        Note: post-I5, `_post_unconsolidated` no longer has a try/except
        wrapper — it relies on `_http_post` being fail-open at the
        transport layer (it catches its own exceptions and returns None).
        This test simulates that contract.
        """
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        cache_path = stop_hook_cache_path

        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Some observation.</content>\n"
            "</memory-candidate>\n"
        ))
        # mock_http returns None by default -> simulates daemon unreachable.

        # Must not raise.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        # The POST was attempted exactly once. A partial-failure diagnostic
        # is then routed to /api/hook-log (which itself returns None here,
        # fail-open by contract). Assert both calls in order.
        unconsolidated_calls = [
            c for c in mock_http.calls
            if c["url"].endswith("/api/memory/unconsolidated")
        ]
        assert unconsolidated_calls == [{
            "url": "/api/memory/unconsolidated",
            "payload": {
                "project": "repo-proj",
                "branch": "main",
                "type": "feedback",
                "content": "Some observation.",
                "tags": "",
                "citations": "",
                "source": "stop_hook",
            },
            "timeout": 5,
        }]
        hook_log_calls = [
            c for c in mock_http.calls if c["url"].endswith("/api/hook-log")
        ]
        assert len(hook_log_calls) == 1
        assert hook_log_calls[0]["payload"]["event"] == (
            "stop_harvest_partial_failure:Stop"
        )

        # CRITICAL: the sha must NOT be recorded when the POST failed.
        # Future Stop invocations must retry. Either the cache file does
        # not exist, or the transcript path is absent from it.
        if cache_path.exists():
            cache = json.loads(cache_path.read_text())
            assert str(transcript) not in cache, (
                "Failed POST must not record the text_sha; otherwise the "
                "candidate is silently lost forever on the next Stop."
            )
        mock_http.drain()

    def test_stop_hook_idempotent_on_repeat(
        self, tmp_path, mock_http, mock_git_context, config_enabled, stop_hook_cache_path,
    ):
        """Repeating the Stop hook with an unchanged transcript must issue
        zero additional HTTP calls — the idempotency cache short-circuits.
        Post-I4+I5 fix: idempotency only engages when ALL posts succeeded on
        the first call, so we must stage a successful response here.
        """
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})

        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Idempotency check.</content>\n"
            "</memory-candidate>\n"
        ))

        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        first_count = len(mock_http.calls)
        assert first_count == 1

        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert len(mock_http.calls) == first_count, (
            "Second Stop hook invocation should not POST again when the "
            "transcript's final-assistant text is unchanged."
        )
        mock_http.drain()

    def test_stop_hook_records_sha_only_on_all_success(
        self, tmp_path, mock_http, mock_git_context, config_enabled, stop_hook_cache_path,
    ):
        """When all candidate POSTs succeed, the sha is recorded and a second
        invocation short-circuits with zero additional POSTs."""
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        cache_path = stop_hook_cache_path
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>First candidate.</content>\n"
            "</memory-candidate>\n"
            "<memory-candidate>\n"
            "  <type>project</type>\n"
            "  <content>Second candidate.</content>\n"
            "</memory-candidate>\n"
        ))

        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert len(mock_http.calls) == 2

        # Sha recorded.
        assert cache_path.exists()
        cache = json.loads(cache_path.read_text())
        assert str(transcript) in cache

        # Second invocation: zero additional POSTs.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        assert len(mock_http.calls) == 2
        mock_http.drain()

    def test_stop_hook_retries_when_any_post_fails(
        self, tmp_path, mock_http, mock_git_context, config_enabled, stop_hook_cache_path,
    ):
        """If any candidate POST fails (returns None), the sha must NOT be
        recorded, and the next Stop invocation retries the whole harvest."""
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        cache_path = stop_hook_cache_path

        # Install a stateful per-call handler on the mock_http controller.
        # Every odd-indexed call returns success, every even fails.
        # mock_http.calls is still populated by the fixture's
        # fake_http_post wrapper before the handler runs, so the test's
        # existing assertions on controller.calls still hold.
        call_counter = {"n": 0}

        def flaky_handler(url, payload, timeout):
            call_counter["n"] += 1
            if call_counter["n"] % 2 == 0:
                return None
            return {"ok": True}

        mock_http.set_handler(flaky_handler)

        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>First candidate (will succeed).</content>\n"
            "</memory-candidate>\n"
            "<memory-candidate>\n"
            "  <type>project</type>\n"
            "  <content>Second candidate (will fail).</content>\n"
            "</memory-candidate>\n"
        ))

        # First invocation: 2 unconsolidated POSTs attempted, 1 failed -> sha
        # NOT recorded. A partial-failure diagnostic is also routed to
        # /api/hook-log, so the total call count includes that entry.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        unconsolidated = [
            c for c in mock_http.calls
            if c["url"].endswith("/api/memory/unconsolidated")
        ]
        assert len(unconsolidated) == 2
        if cache_path.exists():
            cache = json.loads(cache_path.read_text())
            assert str(transcript) not in cache

        # Second invocation: retries both candidates. Total unconsolidated
        # POSTs now == 4.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        unconsolidated_after = [
            c for c in mock_http.calls
            if c["url"].endswith("/api/memory/unconsolidated")
        ]
        assert len(unconsolidated_after) == 4
        mock_http.drain()

    def test_stop_hook_config_disabled_skips(
        self, tmp_path, mock_http, mock_git_context, config_store_disabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_store_disabled)
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Ignored because store is off.</content>\n"
            "</memory-candidate>\n"
        ))
        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert mock_http.calls == []
        mock_http.drain()

    def test_stop_hook_malformed_transcript_fails_open(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        """Non-JSON transcript body -> hook returns cleanly, no POSTs."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            "this is not json at all\n{broken json line\n",
            encoding="utf-8",
        )
        # Must not raise.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        assert mock_http.calls == []
        mock_http.drain()

    def test_stop_hook_missing_transcript_path_fails_open(
        self, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        """Empty or missing transcript_path -> no POSTs, no exception."""
        # Missing key entirely.
        with tripwire:
            spellbook_hook._handle_stop({"cwd": "/repo/proj"})
        assert mock_http.calls == []
        # Explicit empty string.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": "",
                "cwd": "/repo/proj",
            })
        assert mock_http.calls == []
        mock_http.drain()

    def test_candidate_missing_content_is_skipped(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        mock_http.track(mock_git_context)
        mock_http.track(config_enabled)
        """Candidate with <type> but no <content> -> parser skips, no POST."""
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "</memory-candidate>\n"
        ))
        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert mock_http.calls == []
        mock_http.drain()

    def test_stop_hook_empty_namespace_short_circuits(
        self, tmp_path, mock_http, config_enabled,
    ):
        """Empty namespace from _derive_namespace -> no POSTs even with candidates."""
        mock_http.track(config_enabled)
        derive_mock = _make_counting(
            "spellbook_hook:_derive_namespace",
            lambda cwd: ("", "", ""),
        )
        mock_http.track(derive_mock)
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Would be stored if namespace were set.</content>\n"
            "</memory-candidate>\n"
        ))
        with tripwire:

            spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert mock_http.calls == []
        mock_http.drain()
