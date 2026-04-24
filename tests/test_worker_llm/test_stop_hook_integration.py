"""Integration tests for the Stop hook's worker-LLM transcript_harvest gate.

The Stop hook (``hooks.spellbook_hook._handle_stop``) has three modes driven
by ``worker_llm_transcript_harvest_mode``:

- ``skip`` / feature-off: byte-identical regex path (default, backwards-compat
  invariant).
- ``replace``: worker supersedes the regex harvester. Loud-fail on worker
  error (no regex fallback, no sha recording).
- ``merge``: run both, content-hash dedup. Soft-fail on worker error (still
  post regex candidates, emit ``<worker-llm-error>``, record sha).

See impl plan Task D1; design §5.1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
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
    """Force memory.auto_store to True so ``_handle_stop`` proceeds."""

    def fake_config_value(key, default=None):
        if key == "memory.auto_store":
            return True
        return default

    monkeypatch.setattr(spellbook_hook, "_get_config_value", fake_config_value)


@pytest.fixture
def mock_git_context(monkeypatch):
    monkeypatch.setattr(
        spellbook_hook,
        "_resolve_git_context",
        lambda cwd: ("/repo/proj", "main"),
    )


@pytest.fixture
def isolated_harvest_cache(tmp_path, monkeypatch):
    """Scope the stop-harvest sha cache to tmp_path so runs don't collide."""
    cache_path = tmp_path / "last-stop-harvest.json"
    monkeypatch.setattr(spellbook_hook, "STOP_HARVEST_CACHE_PATH", cache_path)
    return cache_path


@pytest.fixture
def posted_candidates(monkeypatch):
    """Capture ``_post_unconsolidated`` calls and control their return value."""

    captured: list[dict] = []
    returns: dict = {"ok": True}

    def fake_post(**kw):
        captured.append(kw)
        return returns["ok"]

    monkeypatch.setattr(spellbook_hook, "_post_unconsolidated", fake_post)
    return captured, returns


def _write_transcript(path: Path, assistant_text: str) -> None:
    msg = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": assistant_text}],
        },
    }
    path.write_text(json.dumps(msg) + "\n", encoding="utf-8")


@pytest.fixture
def transcript_with_regex_candidate(tmp_path):
    """Transcript containing one well-formed <memory-candidate> XML block."""
    path = tmp_path / "session.jsonl"
    _write_transcript(
        path,
        (
            "Some reasoning.\n"
            "<memory-candidate>\n"
            "  <type>feedback</type>\n"
            "  <content>User corrected X.</content>\n"
            "  <tags>t1</tags>\n"
            "  <citations></citations>\n"
            "</memory-candidate>\n"
            "Done."
        ),
    )
    return path


@pytest.fixture
def transcript_plain(tmp_path):
    """Transcript without any <memory-candidate> block (worker-only path)."""
    path = tmp_path / "session.jsonl"
    _write_transcript(path, "The user and I discussed X. Worth remembering.")
    return path


# ---------------------------------------------------------------------------
# Feature-off (default / backwards-compat invariant)
# ---------------------------------------------------------------------------


class TestFeatureOff:
    """When feature_transcript_harvest is False the behavior is byte-identical
    to the pre-worker-LLM regex path. This test guards against accidental
    regressions to the default invariant.
    """

    def test_default_feature_off_is_regex_only(
        self,
        config_enabled,
        mock_git_context,
        isolated_harvest_cache,
        posted_candidates,
        transcript_with_regex_candidate,
        worker_llm_transport,
        monkeypatch,
    ):
        # Do NOT set worker_llm_config fixture; feature flag is implicitly off.
        # Script an empty transport to prove no worker call was made.
        seen = worker_llm_transport([])
        captured, _ = posted_candidates

        spellbook_hook._handle_stop(
            {
                "transcript_path": str(transcript_with_regex_candidate),
                "cwd": "/repo/proj",
            }
        )

        assert len(captured) == 1, captured
        assert captured[0]["mtype"] == "feedback"
        assert captured[0]["content"] == "User corrected X."
        # Zero HTTP calls to the worker endpoint (fixture would raise on pop).
        assert seen == []


# ---------------------------------------------------------------------------
# REPLACE mode
# ---------------------------------------------------------------------------


class TestReplaceMode:
    def test_replace_success_posts_worker_candidates_only(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        mock_git_context,
        isolated_harvest_cache,
        posted_candidates,
        transcript_with_regex_candidate,
    ):
        """Worker returns one candidate; regex block is present but IGNORED."""
        worker_llm_config["worker_llm_transcript_harvest_mode"] = "replace"

        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 200,
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            '[{"type":"project",'
                                            '"content":"worker-only-1",'
                                            '"tags":["x"]}]'
                                        )
                                    }
                                }
                            ]
                        },
                        "delay_s": 0.0,
                        "raise_on_send": None,
                    },
                )()
            ]
        )

        captured, _ = posted_candidates
        spellbook_hook._handle_stop(
            {
                "transcript_path": str(transcript_with_regex_candidate),
                "cwd": "/repo/proj",
            }
        )

        # Worker candidate posted; the regex one is NOT (replace semantics).
        assert len(captured) == 1, captured
        assert captured[0]["mtype"] == "project"
        assert captured[0]["content"] == "worker-only-1"
        assert captured[0]["tags"] == "x"

    def test_replace_worker_error_emits_loud_block_no_regex_fallback(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        mock_git_context,
        isolated_harvest_cache,
        posted_candidates,
        transcript_with_regex_candidate,
        capsys,
    ):
        """Worker unreachable -> inject <worker-llm-error> on stdout, POST
        nothing, do NOT record sha."""
        worker_llm_config["worker_llm_transcript_harvest_mode"] = "replace"
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 0,
                        "body": "",
                        "delay_s": 0.0,
                        "raise_on_send": httpx.ConnectError("refused"),
                    },
                )()
            ]
        )
        captured, _ = posted_candidates

        spellbook_hook._handle_stop(
            {
                "transcript_path": str(transcript_with_regex_candidate),
                "cwd": "/repo/proj",
            }
        )

        out = capsys.readouterr()
        assert "<worker-llm-error>" in out.out
        assert "<task>transcript_harvest</task>" in out.out
        assert "[worker-llm] transcript_harvest" in out.err
        # No regex fallback: nothing was POSTed.
        assert captured == []
        # Sha NOT recorded (next Stop re-attempts, regression retry).
        assert not isolated_harvest_cache.exists() or (
            json.loads(isolated_harvest_cache.read_text()) == {}
        )


# ---------------------------------------------------------------------------
# MERGE mode
# ---------------------------------------------------------------------------


class TestMergeMode:
    def test_merge_both_succeed_content_hash_dedup(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        mock_git_context,
        isolated_harvest_cache,
        posted_candidates,
        transcript_with_regex_candidate,
    ):
        """Both harvesters return the same content -> one POST (dedup)."""
        worker_llm_config["worker_llm_transcript_harvest_mode"] = "merge"

        # Worker returns the SAME content the regex block has.
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 200,
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            '[{"type":"feedback",'
                                            '"content":"User corrected X.",'
                                            '"tags":["worker-tag"]}]'
                                        )
                                    }
                                }
                            ]
                        },
                        "delay_s": 0.0,
                        "raise_on_send": None,
                    },
                )()
            ]
        )
        captured, _ = posted_candidates

        spellbook_hook._handle_stop(
            {
                "transcript_path": str(transcript_with_regex_candidate),
                "cwd": "/repo/proj",
            }
        )

        assert len(captured) == 1, captured
        # Dedup rule: worker wins (richer schema).
        assert captured[0]["content"] == "User corrected X."
        assert captured[0]["tags"] == "worker-tag"

    def test_merge_distinct_contents_both_posted(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        mock_git_context,
        isolated_harvest_cache,
        posted_candidates,
        transcript_with_regex_candidate,
    ):
        worker_llm_config["worker_llm_transcript_harvest_mode"] = "merge"

        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 200,
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            '[{"type":"project",'
                                            '"content":"worker-only-distinct"}]'
                                        )
                                    }
                                }
                            ]
                        },
                        "delay_s": 0.0,
                        "raise_on_send": None,
                    },
                )()
            ]
        )
        captured, _ = posted_candidates

        spellbook_hook._handle_stop(
            {
                "transcript_path": str(transcript_with_regex_candidate),
                "cwd": "/repo/proj",
            }
        )

        contents = sorted(c["content"] for c in captured)
        assert contents == ["User corrected X.", "worker-only-distinct"]

    def test_merge_worker_error_still_posts_regex_and_records_sha(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        mock_git_context,
        isolated_harvest_cache,
        posted_candidates,
        transcript_with_regex_candidate,
        capsys,
    ):
        """Worker error in merge mode -> regex candidates still post, error
        block injected, sha recorded (regex already made progress).
        """
        worker_llm_config["worker_llm_transcript_harvest_mode"] = "merge"
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 0,
                        "body": "",
                        "delay_s": 0.0,
                        "raise_on_send": httpx.ConnectError("refused"),
                    },
                )()
            ]
        )
        captured, _ = posted_candidates

        spellbook_hook._handle_stop(
            {
                "transcript_path": str(transcript_with_regex_candidate),
                "cwd": "/repo/proj",
            }
        )

        out = capsys.readouterr()
        # Error block emitted (loss-of-fidelity signal).
        assert "<worker-llm-error>" in out.out
        # Regex candidate still posted.
        assert len(captured) == 1
        assert captured[0]["content"] == "User corrected X."
        # Sha recorded: re-running should be a no-op.
        assert isolated_harvest_cache.exists()
        sha_map = json.loads(isolated_harvest_cache.read_text())
        assert str(transcript_with_regex_candidate) in sha_map
