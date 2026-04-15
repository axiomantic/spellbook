"""Tests for automatic memory auto-store on hook events.

Covers UserPromptSubmit pattern-based self-capture of feedback/correction/
confirmation/remember prompts, the rule-dictation exception, and the Stop
hook handler that harvests ``<memory-candidate>`` blocks from the final
assistant message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_enabled(monkeypatch):
    """Force memory.auto_store + memory.auto_recall to True."""
    def fake_config_value(key, default=None):
        if key in ("memory.auto_store", "memory.auto_recall"):
            return True
        return default
    monkeypatch.setattr(spellbook_hook, "_get_config_value", fake_config_value)


@pytest.fixture
def config_store_disabled(monkeypatch):
    """Force memory.auto_store to False, auto_recall True."""
    def fake_config_value(key, default=None):
        if key == "memory.auto_store":
            return False
        if key == "memory.auto_recall":
            return True
        return default
    monkeypatch.setattr(spellbook_hook, "_get_config_value", fake_config_value)


@pytest.fixture
def mock_git_context(monkeypatch):
    """Stub _resolve_git_context so tests do not depend on git state."""
    monkeypatch.setattr(
        spellbook_hook,
        "_resolve_git_context",
        lambda cwd: ("/repo/proj", "main"),
    )


@pytest.fixture
def mock_http(monkeypatch):
    """Capture _http_post calls and stage optional responses per-URL."""

    class Controller:
        def __init__(self):
            self.calls: list[dict] = []
            self.responses: dict[str, object] = {}
            self.raise_exc: Exception | None = None

        def set_exception(self, exc: Exception) -> None:
            self.raise_exc = exc

        def set_response(self, url_suffix: str, response: object) -> None:
            self.responses[url_suffix] = response

    controller = Controller()

    def fake_http_post(url, payload, timeout=5):
        controller.calls.append({"url": url, "payload": payload, "timeout": timeout})
        if controller.raise_exc is not None:
            raise controller.raise_exc
        for suffix, resp in controller.responses.items():
            if url.endswith(suffix):
                return resp
        return None

    monkeypatch.setattr(spellbook_hook, "_http_post", fake_http_post)
    return controller


# ---------------------------------------------------------------------------
# UserPromptSubmit auto-store behavior
# ---------------------------------------------------------------------------


class TestUserPromptAutoStore:
    def test_correction_prompt_stores_feedback(
        self, mock_http, mock_git_context, config_enabled,
    ):
        prompt = "Actually use ruff instead of flake8 for linting"
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
        prompt = "Don't mock the database in integration tests"
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
        prompt = "Yes exactly, that was the right call"
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
        prompt = "Remember that I prefer tabs over spaces in Makefiles"
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
        prompt = "Give yourself the rule: always use ruff instead of flake8"
        spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_rule_is_prefix_skips_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        prompt = "The rule is: use black instead of autopep8"
        spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_add_a_rule_that_says_DOES_autostore(
        self, mock_http, mock_git_context, config_enabled,
    ):
        """`add a rule that says ...` is a remember-style instruction, not a
        dictation where the user wants rule text echoed. It must auto-store."""
        prompt = "Add a rule that says: never push to main directly"
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
        self, mock_http, mock_git_context, config_enabled, monkeypatch,
    ):
        """A 2001-char correction prompt must not be POSTed to
        /api/memory/unconsolidated; a diagnostic entry must be routed through
        the daemon's /api/hook-log endpoint with the oversize reason,
        total length, and a 200-char preview.

        Uses exact-equality on the hook-log payload (timestamp frozen) so the
        format is pinned; substring checks would silently allow format drift.
        """
        # Freeze datetime.now(timezone.utc) inside the hook module.
        import datetime as _dt
        frozen = _dt.datetime(2026, 4, 14, 12, 0, 0, tzinfo=_dt.timezone.utc)

        class _FrozenDT(_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen if tz is None else frozen.astimezone(tz)

        monkeypatch.setattr(spellbook_hook, "datetime", _FrozenDT)

        prompt = "Actually " + ("x" * 2000)  # triggers correction, > 2000 chars
        assert len(prompt) > spellbook_hook._AUTO_STORE_MAX_CONTENT_BYTES

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
        prompt = "/remember that we use tabs in Go files"
        spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_short_prompt_skipped(
        self, mock_http, mock_git_context, config_enabled,
    ):
        prompt = "no don't"
        spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_config_disabled_skips_all(
        self, mock_http, mock_git_context, config_store_disabled,
    ):
        prompt = "Don't use that library, use the other one instead"
        spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []

    def test_non_matching_prompt_does_not_store(
        self, mock_http, mock_git_context, config_enabled,
    ):
        prompt = "Please explain how the authentication flow works"
        spellbook_hook._memory_autostore_for_prompt(prompt, cwd="/repo/proj")
        assert mock_http.calls == []


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
    def test_stop_hook_harvests_single_candidate(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
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
    ):
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
    ):
        """Missing <type> tag -> skipped, no POST."""
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <content>No type field, should be ignored.</content>\n"
            "</memory-candidate>\n"
        ))

        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })

        assert mock_http.calls == []

    def test_stop_hook_network_failure_is_fail_open(
        self, tmp_path, mock_http, mock_git_context, config_enabled, monkeypatch,
    ):
        """Real-world failure: `_http_post` returns None when the daemon is
        unreachable. The Stop hook must still return cleanly AND the text_sha
        must NOT be recorded, so the next Stop invocation retries the harvest.

        Note: post-I5, `_post_unconsolidated` no longer has a try/except
        wrapper — it relies on `_http_post` being fail-open at the
        transport layer (it catches its own exceptions and returns None).
        This test simulates that contract.
        """
        # Redirect cache dir to tmp_path so idempotency cache doesn't leak.
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # Rebind the cache path constant that was bound at import time.
        cache_path = tmp_path / ".local" / "spellbook" / "cache" / "last-stop-harvest.json"
        monkeypatch.setattr(
            spellbook_hook,
            "STOP_HARVEST_CACHE_PATH",
            cache_path,
        )

        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Some observation.</content>\n"
            "</memory-candidate>\n"
        ))
        # mock_http returns None by default -> simulates daemon unreachable.

        # Must not raise.
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

    def test_stop_hook_idempotent_on_repeat(
        self, tmp_path, mock_http, mock_git_context, config_enabled, monkeypatch,
    ):
        """Repeating the Stop hook with an unchanged transcript must issue
        zero additional HTTP calls — the idempotency cache short-circuits.

        Post-I4+I5 fix: idempotency only engages when ALL posts succeeded on
        the first call, so we must stage a successful response here.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            spellbook_hook,
            "STOP_HARVEST_CACHE_PATH",
            tmp_path / ".local" / "spellbook" / "cache" / "last-stop-harvest.json",
        )
        mock_http.set_response("/api/memory/unconsolidated", {"ok": True})

        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Idempotency check.</content>\n"
            "</memory-candidate>\n"
        ))

        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        first_count = len(mock_http.calls)
        assert first_count == 1

        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert len(mock_http.calls) == first_count, (
            "Second Stop hook invocation should not POST again when the "
            "transcript's final-assistant text is unchanged."
        )

    def test_stop_hook_records_sha_only_on_all_success(
        self, tmp_path, mock_http, mock_git_context, config_enabled, monkeypatch,
    ):
        """When all candidate POSTs succeed, the sha is recorded and a second
        invocation short-circuits with zero additional POSTs."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cache_path = tmp_path / ".local" / "spellbook" / "cache" / "last-stop-harvest.json"
        monkeypatch.setattr(
            spellbook_hook, "STOP_HARVEST_CACHE_PATH", cache_path,
        )
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
        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        assert len(mock_http.calls) == 2

    def test_stop_hook_retries_when_any_post_fails(
        self, tmp_path, mock_http, mock_git_context, config_enabled, monkeypatch,
    ):
        """If any candidate POST fails (returns None), the sha must NOT be
        recorded, and the next Stop invocation retries the whole harvest."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cache_path = tmp_path / ".local" / "spellbook" / "cache" / "last-stop-harvest.json"
        monkeypatch.setattr(
            spellbook_hook, "STOP_HARVEST_CACHE_PATH", cache_path,
        )

        # Fail the SECOND POST only. Every odd-indexed call returns None.
        original_fake_http = spellbook_hook._http_post
        call_counter = {"n": 0}

        def flaky_http(url, payload, timeout=5):
            mock_http.calls.append({"url": url, "payload": payload, "timeout": timeout})
            call_counter["n"] += 1
            # 1st, 3rd calls succeed; 2nd, 4th fail.
            if call_counter["n"] % 2 == 0:
                return None
            return {"ok": True}

        monkeypatch.setattr(spellbook_hook, "_http_post", flaky_http)

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
        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })
        unconsolidated_after = [
            c for c in mock_http.calls
            if c["url"].endswith("/api/memory/unconsolidated")
        ]
        assert len(unconsolidated_after) == 4
        _ = original_fake_http  # retain reference; not used further

    def test_stop_hook_config_disabled_skips(
        self, tmp_path, mock_http, mock_git_context, config_store_disabled,
    ):
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Ignored because store is off.</content>\n"
            "</memory-candidate>\n"
        ))

        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })

        assert mock_http.calls == []

    def test_stop_hook_malformed_transcript_fails_open(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        """Non-JSON transcript body -> hook returns cleanly, no POSTs."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            "this is not json at all\n{broken json line\n",
            encoding="utf-8",
        )

        # Must not raise.
        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })

        assert mock_http.calls == []

    def test_stop_hook_missing_transcript_path_fails_open(
        self, mock_http, mock_git_context, config_enabled,
    ):
        """Empty or missing transcript_path -> no POSTs, no exception."""
        # Missing key entirely.
        spellbook_hook._handle_stop({"cwd": "/repo/proj"})
        assert mock_http.calls == []

        # Explicit empty string.
        spellbook_hook._handle_stop({
            "transcript_path": "",
            "cwd": "/repo/proj",
        })
        assert mock_http.calls == []

    def test_candidate_missing_content_is_skipped(
        self, tmp_path, mock_http, mock_git_context, config_enabled,
    ):
        """Candidate with <type> but no <content> -> parser skips, no POST."""
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "</memory-candidate>\n"
        ))

        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })

        assert mock_http.calls == []

    def test_stop_hook_empty_namespace_short_circuits(
        self, tmp_path, monkeypatch, mock_http, config_enabled,
    ):
        """Empty namespace from _derive_namespace -> no POSTs even with candidates."""
        monkeypatch.setattr(
            spellbook_hook,
            "_derive_namespace",
            lambda cwd: ("", "", ""),
        )
        transcript = tmp_path / "session.jsonl"
        _write_transcript(transcript, (
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>Would be stored if namespace were set.</content>\n"
            "</memory-candidate>\n"
        ))

        spellbook_hook._handle_stop({
            "transcript_path": str(transcript),
            "cwd": "/repo/proj",
        })

        assert mock_http.calls == []
