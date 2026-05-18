"""Tests for automatic memory auto-store on hook events.

Covers UserPromptSubmit pattern-based self-capture of feedback/correction/
confirmation/remember prompts, the rule-dictation exception, and the Stop
hook handler that harvests ``<memory-candidate>`` blocks from the final
assistant message.

All mocks use tripwire per project policy (see AGENTS.md, "Testing with
Tripwire"). ``monkeypatch.setattr`` of module attributes is forbidden.

Strict-count discipline
-----------------------
Every fixture returns a ``_MockBuilder`` (or, for ``mock_http``, a
``Controller``). Each test MUST call ``.expect(n)`` on every fixture it
touches, declaring exactly how many times the SUT will invoke that mock.
Tripwire's FIFO queue enforces this strictly:

* SUT calls > registered: ``UnmockedInteractionError`` on the extra call.
* SUT calls < registered: ``UnusedMocksError`` at teardown.

This restores the verification signal that the previous ``_make_counting``
"pre-stack 50 ``required(False)`` entries" helper destroyed.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import tripwire
from dirty_equals import AnyThing

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Auto-verify infrastructure
# ---------------------------------------------------------------------------
#
# Tripwire requires that every intercepted call be asserted with an
# ``assert_*`` after the sandbox closes; otherwise it raises
# ``UnassertedInteractionsError`` at teardown. We track every
# ``_MockBuilder`` constructed during a test in a per-test registry and
# call ``verify_all()`` on each in an autouse finalizer. This eliminates
# the per-test ``mock_http.drain()`` boilerplate the previous helper used.


_active_builders: list["_MockBuilder"] = []


@pytest.fixture(autouse=True)
def _auto_verify_builders():
    """Per-test registry of created ``_MockBuilder``s; verify on teardown.

    Each test (or its fixtures) constructs ``_MockBuilder`` instances;
    they register themselves into ``_active_builders``. After the test
    body runs (and after ``with tripwire:`` exits), we call
    ``verify_all()`` on each so tripwire's "every intercepted call must
    be asserted" contract is satisfied. The strict-count FIFO enforces
    the call count; the wildcard ``assert_call`` here only consumes the
    recorded interactions.
    """
    _active_builders.clear()
    yield
    for builder in _active_builders:
        builder.verify_all()
    _active_builders.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _MockBuilder:
    """Strict tripwire wrapper bound to a default side-effect callable.

    Each test calls ``.expect(n)`` to register exactly ``n`` strict
    ``.calls(default_fn)`` entries on the underlying tripwire mock. The
    FIFO queue enforces the count: extra SUT calls raise
    ``UnmockedInteractionError`` and unconsumed entries raise
    ``UnusedMocksError`` at teardown.

    After the sandbox exits, the test (or the auto-verify autouse fixture
    below) must call ``.verify_all()``, which issues one wildcard
    ``assert_call`` per recorded interaction to satisfy tripwire's
    "every intercepted call must be asserted" contract. The strict-count
    registration + the test body's downstream behavior assertions (e.g.
    ``mock_http.calls == [...]``) carry the real verification signal.
    """

    def __init__(self, path: str, default_fn: Callable[..., Any]) -> None:
        self.path = path
        self._default_fn = default_fn
        self._n_expected: int = 0
        self.mock = tripwire.mock(path)
        _active_builders.append(self)

    def expect(self, n: int = 1) -> "_MockBuilder":
        """Register exactly ``n`` strict side-effects using the default fn."""
        for _ in range(n):
            self.mock.__call__.calls(self._default_fn)
        self._n_expected += n
        return self

    def expect_with(self, fn: Callable[..., Any], n: int = 1) -> "_MockBuilder":
        """Register exactly ``n`` strict side-effects using ``fn``."""
        for _ in range(n):
            self.mock.__call__.calls(fn)
        self._n_expected += n
        return self

    def verify_all(self) -> None:
        """Issue one wildcard assert_call per registered side-effect.

        Must be invoked after the ``with tripwire:`` block exits. Order
        is unconstrained (``in_any_order``).
        """
        with tripwire.in_any_order():
            for _ in range(self._n_expected):
                self.mock.__call__.assert_call(args=AnyThing, kwargs=AnyThing)


@pytest.fixture
def config_enabled() -> _MockBuilder:
    """Stub ``_get_config_value`` so memory.auto_store + auto_recall are True.

    Tests call ``config_enabled.expect(n)`` with the exact number of
    ``_get_config_value`` invocations the SUT makes in that test. For
    ``_memory_autostore_for_prompt`` and ``_handle_stop`` this is 1 per
    invocation (the ``_auto_store_enabled`` check).
    """
    def fake_config_value(key: str, default: Any = None) -> Any:
        if key in ("memory.auto_store", "memory.auto_recall"):
            return True
        return default

    return _MockBuilder("spellbook_hook:_get_config_value", fake_config_value)


@pytest.fixture
def config_store_disabled() -> _MockBuilder:
    """Stub ``_get_config_value`` so memory.auto_store is False."""
    def fake_config_value(key: str, default: Any = None) -> Any:
        if key == "memory.auto_store":
            return False
        if key == "memory.auto_recall":
            return True
        return default

    return _MockBuilder("spellbook_hook:_get_config_value", fake_config_value)


@pytest.fixture
def mock_git_context() -> _MockBuilder:
    """Stub ``_resolve_git_context`` to return a fixed (cwd, branch) tuple."""
    return _MockBuilder(
        "spellbook_hook:_resolve_git_context",
        lambda cwd: ("/repo/proj", "main"),
    )


@pytest.fixture
def mock_http():
    """Capture ``_http_post`` calls and stage optional responses per-URL.

    The controller's ``calls`` list is the test's observable assertion
    surface (existing tests inspect it for URL/payload/timeout shape).
    Each test calls ``mock_http.expect(n)`` with the exact number of
    ``_http_post`` invocations the SUT will make; this registers ``n``
    strict ``.calls(fake_http_post)`` entries on the underlying tripwire
    mock. The FIFO queue enforces the count, so extra POSTs raise
    ``UnmockedInteractionError`` and unconsumed entries raise
    ``UnusedMocksError`` at teardown.
    """

    class Controller:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.responses: dict[str, object] = {}
            self.raise_exc: Exception | None = None
            self._custom_handler: Callable[..., Any] | None = None
            self._n_expected: int = 0
            self._tripwire_mock = tripwire.mock("spellbook_hook:_http_post")

        def set_exception(self, exc: Exception) -> None:
            self.raise_exc = exc

        def set_response(self, url_suffix: str, response: object) -> None:
            self.responses[url_suffix] = response

        def set_handler(self, fn: Callable[..., Any]) -> None:
            """Override the default URL-keyed response dispatch.

            ``fn(url, payload, timeout)`` is called instead of the
            response-map lookup. Useful for tests that need per-call
            stateful behavior (e.g. flaky-on-second-call). The handler
            runs inside the same tripwire side-effect entry, so
            ``controller.calls`` still records every call before the
            handler runs.
            """
            self._custom_handler = fn

        def _fake_http_post(self, url, payload, timeout=5):
            self.calls.append({"url": url, "payload": payload, "timeout": timeout})
            if self.raise_exc is not None:
                raise self.raise_exc
            if self._custom_handler is not None:
                return self._custom_handler(url, payload, timeout)
            for suffix, resp in self.responses.items():
                if url.endswith(suffix):
                    return resp
            return None

        def expect(self, n: int) -> "Controller":
            """Register exactly ``n`` strict ``_http_post`` side-effects."""
            for _ in range(n):
                self._tripwire_mock.__call__.calls(self._fake_http_post)
            self._n_expected += n
            return self

        def verify_all(self) -> None:
            """Wildcard-assert each recorded interaction (autouse-invoked)."""
            with tripwire.in_any_order():
                for _ in range(self._n_expected):
                    self._tripwire_mock.__call__.assert_call(
                        args=AnyThing, kwargs=AnyThing,
                    )

    controller = Controller()
    _active_builders.append(controller)  # duck-typed: has .verify_all()
    return controller


# ---------------------------------------------------------------------------
# UserPromptSubmit auto-store behavior
# ---------------------------------------------------------------------------
#
# Per-test call accounting for ``_memory_autostore_for_prompt(prompt, cwd)``:
#
# 1. ``_auto_store_enabled()`` always calls ``_get_config_value`` once.
# 2. If the prompt is short, slash-prefixed, rule-dictation, or non-matching,
#    the function returns BEFORE touching git context or _http_post.
#    Counts: config_enabled=1, mock_git_context=0, mock_http=0.
# 3. If the prompt matches a pattern AND is not oversized: ``_derive_namespace``
#    is called once (-> 1 ``_resolve_git_context`` call) and one POST is made
#    to /api/memory/unconsolidated.
#    Counts: config_enabled=1, mock_git_context=1, mock_http=1.
# 4. If the prompt matches a correction pattern but exceeds
#    ``_AUTO_STORE_MAX_CONTENT_BYTES``: ``_log_autostore_oversized`` runs,
#    which calls ``_utcnow`` once and posts to /api/hook-log once. NO
#    ``_resolve_git_context`` (oversize bail returns before _derive_namespace).
#    Counts: config_enabled=1, mock_git_context=0, mock_http=1, utcnow=1.
# 5. If ``_auto_store_enabled`` returns False (config_store_disabled):
#    return immediately. Counts: config_store_disabled=1, others=0.


class TestUserPromptAutoStore:
    def test_correction_prompt_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.expect(1)
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

    def test_dont_prefix_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.expect(1)
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

    def test_confirmation_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.expect(1)
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

    def test_remember_keyword_stores_user_type(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.expect(1)
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

    def test_rule_dictation_skips_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        # Rule-dictation classification returns None before _derive_namespace
        # or _http_post are reached, so config is the only thing called.
        config_enabled.expect(1)
        prompt = "Give yourself the rule: always use ruff instead of flake8"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_rule_is_prefix_skips_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        prompt = "The rule is: use black instead of autopep8"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_add_a_rule_that_says_DOES_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        """``add a rule that says ...`` is a remember-style instruction, not a
        dictation where the user wants rule text echoed. It must auto-store."""
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.expect(1)
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
        config_enabled.expect(1)
        # Oversize returns BEFORE _derive_namespace, so mock_git_context
        # is NOT called. _log_autostore_oversized calls _utcnow once and
        # posts once to /api/hook-log.
        mock_http.expect(1)
        import datetime as _dt
        frozen = _dt.datetime(2026, 4, 14, 12, 0, 0, tzinfo=_dt.timezone.utc)

        utcnow = _MockBuilder("spellbook_hook:_utcnow", lambda: frozen)
        utcnow.expect(1)

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

    def test_slash_command_skipped(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        prompt = "/remember that we use tabs in Go files"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_short_prompt_skipped(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        prompt = "no don't"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_config_disabled_skips_all(
        self, mock_http, mock_git_context, config_store_disabled,
    ):
        # _auto_store_enabled reads False -> returns before anything else.
        config_store_disabled.expect(1)
        prompt = "Don't use that library, use the other one instead"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_non_matching_prompt_does_not_store(
        self, mock_http, mock_git_context, config_enabled,
    ):
        config_enabled.expect(1)
        prompt = "Please explain how the authentication flow works"
        with tripwire:
            spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []


# ---------------------------------------------------------------------------
# Stop hook handler
# ---------------------------------------------------------------------------
#
# Per-invocation call accounting for ``_handle_stop(data)``:
#
# A. Always 1 ``_get_config_value`` call (``_auto_store_enabled``).
# B. Returns early when ``transcript_path`` is empty -> 0 cache_path, 0
#    feature_enabled, 0 git, 0 http.
# C. Otherwise: 1 ``_load_stop_harvest_cache`` -> 1 cache_path call.
# D. If cache hit: returns. Total 1 cache_path call.
# E. Otherwise: 1 ``feature_enabled("transcript_harvest")`` call (assumes
#    the spellbook.worker_llm.config package imports OK -- it does in this
#    test env). ``feature_enabled`` returns False, so ``_queue_enabled``
#    is NOT called and ``_get_config_value`` total stays at 1.
# F. If no candidates parsed: ``_record_stop_harvest`` runs, which calls
#    ``_load_stop_harvest_cache`` once more (+1 cache_path) and
#    ``_atomic_write_json(_get_stop_harvest_cache_path(), ...)`` once
#    (+1 cache_path). Total 3 cache_path. Then returns. 0 git, 0 http.
# G. If candidates parsed and namespace derived: 1 ``_resolve_git_context``
#    call. Then one POST per candidate via ``_post_unconsolidated``.
#    If ALL POSTs succeed: ``_record_stop_harvest`` -> +2 cache_path.
#    Total: 3 cache_path, 1 git, N http.
# H. If any POST fails: ``_log_hook_error`` runs (+1 _utcnow, +1 http to
#    /api/hook-log). NO ``_record_stop_harvest``. Total cache_path stays at 1.
#    Total: 1 cache_path, 1 git, N+1 http, 1 utcnow.


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
    """Stop-hook tests.

    Every Stop-hook test must register two autouse-like mocks that the SUT
    calls unconditionally: ``_get_stop_harvest_cache_path`` (cache I/O) and
    ``feature_enabled`` from ``spellbook.worker_llm.config`` (the worker-LLM
    gate). The ``stop_hook_mocks`` fixture below returns a small builder
    pair that each test calls ``.expect(n)`` on with the SUT's exact call
    count for that test (1 for cache-hit / failed-POST paths, 3 for the
    success / no-candidates / empty-namespace paths).
    """

    @pytest.fixture
    def stop_hook_mocks(self, tmp_path):
        """Return (cache_path_builder, feature_builder, per_test_cache_path).

        ``cache_path_builder`` stubs ``_get_stop_harvest_cache_path`` to
        point at a per-test temp file (so the on-disk cache is isolated).
        ``feature_builder`` stubs ``feature_enabled`` to return False so
        the regex-only path runs. ``feature_builder`` is None when the
        worker-LLM package is not importable in this environment (rare).
        """
        per_test_cache = tmp_path / "_stop_harvest_cache.json"
        cache_path_builder = _MockBuilder(
            "spellbook_hook:_get_stop_harvest_cache_path",
            lambda: per_test_cache,
        )

        feature_builder: _MockBuilder | None = None
        try:
            import spellbook.worker_llm.config  # noqa: F401
            feature_builder = _MockBuilder(
                "spellbook.worker_llm.config:feature_enabled",
                lambda _name: False,
            )
        except Exception:
            pass

        return cache_path_builder, feature_builder, per_test_cache

    def test_stop_hook_harvests_single_candidate(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        cache_path, feature, _ = stop_hook_mocks
        # 1 candidate, all succeed: 3 cache_path, 1 feature, 1 config, 1 git, 1 http.
        cache_path.expect(3)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        mock_http.expect(1)
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

    def test_stop_hook_harvests_multiple_candidates(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        cache_path, feature, _ = stop_hook_mocks
        # 2 candidates, all succeed: 3 cache_path, 1 feature, 1 config, 1 git, 2 http.
        cache_path.expect(3)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        mock_http.expect(2)
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

    def test_stop_hook_ignores_malformed_candidate(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """Missing <type> tag -> skipped, no POST."""
        cache_path, feature, _ = stop_hook_mocks
        # 0 candidates parsed -> _record_stop_harvest still runs (line 1778):
        # 3 cache_path, 1 feature, 1 config, 0 git, 0 http.
        cache_path.expect(3)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(1)
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

    def test_stop_hook_network_failure_is_fail_open(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """Real-world failure: `_http_post` returns None when the daemon is
        unreachable. The Stop hook must still return cleanly AND the text_sha
        must NOT be recorded, so the next Stop invocation retries the harvest.
        Note: post-I5, `_post_unconsolidated` no longer has a try/except
        wrapper -- it relies on `_http_post` being fail-open at the
        transport layer (it catches its own exceptions and returns None).
        This test simulates that contract.
        """
        cache_path, feature, per_test_cache = stop_hook_mocks
        # 1 candidate, POST returns None (default) -> failed=1, no record:
        # 1 cache_path, 1 feature, 1 config, 1 git.
        # HTTP: 1 unconsolidated POST + 1 hook-log POST (from _log_hook_error
        # partial-failure diagnostic) = 2 http calls + 1 _utcnow call.
        cache_path.expect(1)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(1)
        mock_git_context.expect(1)
        mock_http.expect(2)
        utcnow = _MockBuilder(
            "spellbook_hook:_utcnow",
            lambda: __import__("datetime").datetime(
                2026, 4, 14, 12, 0, 0,
                tzinfo=__import__("datetime").timezone.utc,
            ),
        )
        utcnow.expect(1)

        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Some observation.</content>\n"
            "</memory-candidate>\n"
        ))
        # mock_http returns None by default -> simulates daemon unreachable.

        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
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
        if per_test_cache.exists():
            cache = json.loads(per_test_cache.read_text())
            assert str(transcript) not in cache, (
                "Failed POST must not record the text_sha; otherwise the "
                "candidate is silently lost forever on the next Stop."
            )

    def test_stop_hook_idempotent_on_repeat(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """Repeating the Stop hook with an unchanged transcript must issue
        zero additional HTTP calls -- the idempotency cache short-circuits.
        """
        cache_path, feature, _ = stop_hook_mocks
        # First invocation: 1 candidate, succeeds -> 3 cache_path, 1 feature,
        # 1 config, 1 git, 1 http.
        # Second invocation: cache HIT -> 1 cache_path, 0 feature, 1 config,
        # 0 git, 0 http.
        # Totals: 4 cache_path, 1 feature, 2 config, 1 git, 1 http.
        cache_path.expect(4)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(2)
        mock_git_context.expect(1)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        mock_http.expect(1)

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

    def test_stop_hook_records_sha_only_on_all_success(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """When all candidate POSTs succeed, the sha is recorded and a second
        invocation short-circuits with zero additional POSTs."""
        cache_path, feature, per_test_cache = stop_hook_mocks
        # First invocation: 2 candidates, all succeed -> 3 cache_path,
        # 1 feature, 1 config, 1 git, 2 http.
        # Second invocation: cache HIT -> 1 cache_path, 0 feature, 1 config,
        # 0 git, 0 http.
        # Totals: 4 cache_path, 1 feature, 2 config, 1 git, 2 http.
        cache_path.expect(4)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(2)
        mock_git_context.expect(1)
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})
        mock_http.expect(2)
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
        assert per_test_cache.exists()
        cache = json.loads(per_test_cache.read_text())
        assert str(transcript) in cache

        # Second invocation: zero additional POSTs.
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        assert len(mock_http.calls) == 2

    def test_stop_hook_retries_when_any_post_fails(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """If any candidate POST fails (returns None), the sha must NOT be
        recorded, and the next Stop invocation retries the whole harvest."""
        cache_path, feature, per_test_cache = stop_hook_mocks
        # First invocation: 2 candidates, flaky handler -> #1 succeeds,
        # #2 fails -> failed=1 -> _log_hook_error fires (+1 hook-log POST,
        # +1 _utcnow). Total first: 1 cache_path, 1 feature, 1 config, 1 git,
        # 3 http (2 unconsolidated + 1 hook-log), 1 utcnow.
        # Second invocation: cache MISS (sha not recorded) -> retries
        # everything. With flaky handler at counter=3,4: #3 succeeds, #4 fails
        # -> same partial-failure path: +1 cache_path, +1 feature, +1 config,
        # +1 git, +3 http, +1 utcnow.
        # Totals: 2 cache_path, 2 feature, 2 config, 2 git, 6 http, 2 utcnow.
        cache_path.expect(2)
        if feature is not None:
            feature.expect(2)
        config_enabled.expect(2)
        mock_git_context.expect(2)
        mock_http.expect(6)
        utcnow = _MockBuilder(
            "spellbook_hook:_utcnow",
            lambda: __import__("datetime").datetime(
                2026, 4, 14, 12, 0, 0,
                tzinfo=__import__("datetime").timezone.utc,
            ),
        )
        utcnow.expect(2)

        # Stateful per-call handler: odd succeeds, even fails.
        call_counter = {"n": 0}

        def flaky_handler(url, payload, timeout):
            # Only count actual unconsolidated POSTs; hook-log POSTs go
            # through the same mock_http but should not toggle our flaky
            # sequence (they always return None by default response map).
            if not url.endswith("/api/memory/unconsolidated"):
                return None
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
        if per_test_cache.exists():
            cache = json.loads(per_test_cache.read_text())
            assert str(transcript) not in cache

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

    def test_stop_hook_config_disabled_skips(
        self, tmp_path, mock_http, mock_git_context, config_store_disabled,
        stop_hook_mocks,
    ):
        # _auto_store_enabled returns False -> returns before cache /
        # feature_enabled / anything else. 1 config call only.
        config_store_disabled.expect(1)
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

    def test_stop_hook_malformed_transcript_fails_open(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """Non-JSON transcript body -> hook returns cleanly, no POSTs.

        _extract_last_assistant_text returns empty string -> returns at
        line 1632 BEFORE _load_stop_harvest_cache. So 1 config call, 0
        cache_path, 0 feature, 0 http.
        """
        config_enabled.expect(1)
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            "this is not json at all\n{broken json line\n",
            encoding="utf-8",
        )
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": str(transcript),
                "cwd": "/repo/proj",
            })
        assert mock_http.calls == []

    def test_stop_hook_missing_transcript_path_fails_open(
        self, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """Empty or missing transcript_path -> no POSTs, no exception.

        Returns immediately after _auto_store_enabled when transcript_path
        is empty/missing. Two invocations -> 2 config calls only.
        """
        config_enabled.expect(2)
        with tripwire:
            spellbook_hook._handle_stop({"cwd": "/repo/proj"})
        assert mock_http.calls == []
        with tripwire:
            spellbook_hook._handle_stop({
                "transcript_path": "",
                "cwd": "/repo/proj",
            })
        assert mock_http.calls == []

    def test_candidate_missing_content_is_skipped(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
        stop_hook_mocks,
    ):
        """Candidate with <type> but no <content> -> parser skips, no POST.

        0 candidates parsed -> _record_stop_harvest still runs (see test
        ``test_stop_hook_ignores_malformed_candidate``). Same counts:
        3 cache_path, 1 feature, 1 config, 0 git, 0 http.
        """
        cache_path, feature, _ = stop_hook_mocks
        cache_path.expect(3)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(1)
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

    def test_stop_hook_empty_namespace_short_circuits(
        self, tmp_path, mock_http, config_enabled,
        stop_hook_mocks,
    ):
        """Empty namespace from _derive_namespace -> no POSTs even with candidates.

        We register a custom _derive_namespace mock returning ("", "", "").
        SUT call path: 1 config, 1 cache_path (load), 1 feature, then 1
        _derive_namespace, then _record_stop_harvest (+2 cache_path) and
        returns. Note ``_derive_namespace`` is the mocked symbol here, NOT
        ``_resolve_git_context``, so mock_git_context is not needed.
        Totals: 1 config, 3 cache_path, 1 feature, 1 derive_namespace, 0 http.
        """
        cache_path, feature, _ = stop_hook_mocks
        cache_path.expect(3)
        if feature is not None:
            feature.expect(1)
        config_enabled.expect(1)
        derive = _MockBuilder(
            "spellbook_hook:_derive_namespace",
            lambda cwd: ("", "", ""),
        )
        derive.expect(1)
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
