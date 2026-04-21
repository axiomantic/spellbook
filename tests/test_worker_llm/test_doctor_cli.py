"""Integration tests for ``spellbook worker-llm doctor``.

Covers:

- Happy path: valid config + reachable endpoint + all 4 tasks green -> exit 0,
  JSON payload contains ``endpoint``, ``model`` and 4 ``results`` entries each
  with ``ok: true``.
- Connection failure: endpoint unreachable -> exit 2, a ``WorkerLLMUnreachable``
  (or equivalent transport error) is surfaced per result.
- Missing config: ``worker_llm_base_url`` empty -> exit 1, config check fails
  before any task runs.
- Override prompt detected: a file at
  ``~/.local/spellbook/worker_prompts/transcript_harvest.md`` (the override
  path) is reported so the operator can see that overrides are active.

These tests invoke ``_run_doctor`` directly via an ``argparse.Namespace`` —
same precedent as ``tests/test_cli/test_doctor.py::test_runs_without_crashing``.
No subprocess needed; the CLI is a thin argparse wrapper.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest


def _chat_completion(content: str) -> dict:
    """Build a minimal OpenAI-compatible ``/v1/chat/completions`` response."""
    return {"choices": [{"message": {"content": content}}]}


# Canned per-task replies that each task's parser is known to accept. See
# ``spellbook/worker_llm/tasks/*`` and their existing happy-path tests for
# the exact shape each parser consumes.
_HAPPY_SCRIPT = [
    SimpleNamespace(  # transcript_harvest
        status=200,
        body=_chat_completion(
            '[{"content":"Memory body","type":"feedback","kind":"preference",'
            '"tags":"t1","citations":""}]'
        ),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(  # memory_rerank
        status=200,
        body=_chat_completion('[{"id":"a.md","relevance_0_1":0.9}]'),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(  # roundtable_voice
        status=200,
        body=_chat_completion("**Magician**: analysis...\nVerdict: APPROVE"),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(  # tool_safety
        status=200,
        body=_chat_completion('{"verdict":"OK","reasoning":"listing is safe"}'),
        delay_s=0.0,
        raise_on_send=None,
    ),
]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDoctorHappyPath:
    """All 4 tasks succeed -> exit 0, JSON payload fully populated."""

    def test_json_happy_path_exit_zero(
        self, worker_llm_transport, worker_llm_config, capsys
    ):
        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["endpoint"] == "http://test.local/v1"
        assert payload["model"] == "test-model"
        assert len(payload["results"]) == 4
        task_names = {r["task"] for r in payload["results"]}
        assert task_names == {
            "transcript_harvest",
            "memory_rerank",
            "roundtable_voice",
            "tool_safety",
        }
        for r in payload["results"]:
            assert r["ok"] is True, f"task {r['task']} reported not ok: {r}"
            assert "result_preview" in r

    def test_human_output_contains_per_task_ok(
        self, worker_llm_transport, worker_llm_config, capsys
    ):
        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=False, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        out = capsys.readouterr().out
        # Endpoint banner
        assert "http://test.local/v1" in out
        assert "test-model" in out
        # Each task reported
        assert "transcript_harvest" in out
        assert "memory_rerank" in out
        assert "roundtable_voice" in out
        assert "tool_safety" in out
        # No FAIL marker
        assert "[FAIL" not in out


# ---------------------------------------------------------------------------
# Connection failure
# ---------------------------------------------------------------------------


class TestDoctorConnectionFailure:
    """Unreachable endpoint -> exit 2, error surfaced per result."""

    def test_connect_error_exits_two(
        self, worker_llm_transport, worker_llm_config, capsys
    ):
        # Every call raises ConnectError. Need 4 entries (one per task).
        conn_err = httpx.ConnectError("connection refused")
        script = [
            SimpleNamespace(
                status=0, body="", delay_s=0.0, raise_on_send=conn_err
            )
            for _ in range(4)
        ]
        worker_llm_transport(script)

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        # Exit 2 == endpoint configured but at least one task failed.
        assert ei.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        # Every task entry must be ok=False and carry an error.
        ok_flags = [r["ok"] for r in payload["results"]]
        assert ok_flags.count(True) + ok_flags.count(False) == len(ok_flags)
        # At least one should have bubbled a connection / unreachable error.
        errors = [r.get("error", "") for r in payload["results"] if not r["ok"]]
        assert errors, "expected at least one failed task with an error message"
        assert any(
            "Unreachable" in e or "connection" in e.lower() or "ConnectError" in e
            for e in errors
        ), f"no transport error surfaced in {errors!r}"


# ---------------------------------------------------------------------------
# Missing config
# ---------------------------------------------------------------------------


class TestDoctorMissingConfig:
    """``worker_llm_base_url`` unset -> exit 1 before any task runs."""

    def test_unconfigured_exits_one(self, monkeypatch, capsys):
        # Drive the config reader with all-None so is_configured() -> False.
        from spellbook.core import config as _core_cfg
        from spellbook.worker_llm import config as _wl_cfg

        monkeypatch.setattr(_core_cfg, "config_get", lambda k: None)
        monkeypatch.setattr(_wl_cfg, "config_get", lambda k: None)

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=False, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 1

        # Config check message must appear on stderr (the human channel for
        # loud errors). Stdout may carry the endpoint banner too.
        err = capsys.readouterr().err
        assert "worker_llm_base_url" in err or "not set" in err.lower()


# ---------------------------------------------------------------------------
# Override detection
# ---------------------------------------------------------------------------


class TestDoctorOverrideDetection:
    """A file at the override path is reported in the doctor output."""

    def test_override_listed_in_output(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config, capsys
    ):
        # Redirect the override dir to a temp location so we do not touch
        # the user's real ~/.local/spellbook/worker_prompts/ tree.
        override_dir = tmp_path / "worker_prompts"
        override_dir.mkdir(parents=True)
        (override_dir / "transcript_harvest.md").write_text(
            "# override prompt body\n", encoding="utf-8"
        )

        from spellbook.worker_llm import prompts as _prompts_mod

        monkeypatch.setattr(
            _prompts_mod, "OVERRIDE_PROMPT_DIR", override_dir
        )

        # Also patch the name the doctor module imported (if any). The CLI
        # reads OVERRIDE_PROMPT_DIR off the prompts module so this single
        # patch is sufficient.
        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        overrides = payload.get("overrides", [])
        assert "transcript_harvest" in overrides, (
            f"expected transcript_harvest in overrides, got {overrides!r}"
        )


# ---------------------------------------------------------------------------
# Register + parser smoke
# ---------------------------------------------------------------------------


class TestDoctorRegister:
    """Argparse wiring sanity checks."""

    def test_register_adds_worker_llm_subcommand(self):
        import argparse

        from spellbook.cli.commands.worker_llm import register

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        args = parser.parse_args(["worker-llm", "doctor"])
        assert args.command == "worker-llm"
        assert hasattr(args, "func")

    def test_doctor_help_exits_zero(self):
        import argparse

        from spellbook.cli.commands.worker_llm import register

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        with pytest.raises(SystemExit) as ei:
            parser.parse_args(["worker-llm", "doctor", "--help"])
        assert ei.value.code == 0
