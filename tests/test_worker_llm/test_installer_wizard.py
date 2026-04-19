"""Integration tests for the ``spellbook install`` worker-LLM wizard step.

Scenarios:

- Wizard + doctor end-to-end: user says yes, picks the detected endpoint,
  picks a model, enables one feature. Resulting config passes ``is_configured``
  and the doctor (stubbed to run against a fake endpoint) reports all-green.
- Wizard with no probe hits: user enters manual URL; wizard still writes
  config for base_url / model / features.
- Wizard declined: user says no; no config keys are written, feature flags
  remain at defaults.

The wizard is implemented as ``spellbook.cli.commands.install._run_worker_llm_wizard``
so the test can drive it directly without spinning up the full installer.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest


def _chat_completion(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


_HAPPY_SCRIPT = [
    SimpleNamespace(
        status=200,
        body=_chat_completion(
            '[{"content":"Body","type":"feedback","kind":"preference",'
            '"tags":"t","citations":""}]'
        ),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(
        status=200,
        body=_chat_completion('[{"id":"a.md","relevance":0.9}]'),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(
        status=200,
        body=_chat_completion("**Magician**: ok\nVerdict: APPROVE"),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(
        status=200,
        body=_chat_completion('{"verdict":"OK","reasoning":"safe"}'),
        delay_s=0.0,
        raise_on_send=None,
    ),
]


@pytest.fixture
def stub_probe(monkeypatch):
    """Patch ``probe_all`` with a controllable replacement.

    Returns a callable ``install(endpoints: list[DetectedEndpoint]) -> None``
    so each test scopes its own probe result.
    """
    import asyncio

    from spellbook.worker_llm import probe as _probe_mod

    def _install(endpoints):
        async def _fake():
            return endpoints

        # Patch the call site (install.py imports probe_all directly).
        monkeypatch.setattr(_probe_mod, "probe_all", lambda timeout_total_s=2.0: _fake())

    return _install


@pytest.fixture
def captured_config(monkeypatch):
    """Intercept ``config_set`` calls so tests can assert what was written.

    Returns the list of (key, value) tuples in call order.
    """
    calls: list[tuple[str, object]] = []

    def _fake_config_set(key, value):
        calls.append((key, value))
        return {"status": "ok"}

    from spellbook.core import config as _core_cfg

    monkeypatch.setattr(_core_cfg, "config_set", _fake_config_set)
    return calls


@pytest.fixture
def scripted_input(monkeypatch):
    """Drive ``builtins.input`` from a queue of canned responses.

    Returns a callable ``set_answers(answers: list[str])`` so the test can
    program the wizard's Q&A sequence in order.
    """

    queue: list[str] = []

    def _input(prompt: str = "") -> str:
        if not queue:
            raise AssertionError(
                f"scripted_input exhausted; unexpected prompt: {prompt!r}"
            )
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", _input)

    def _set_answers(answers):
        queue.clear()
        queue.extend(answers)

    return _set_answers


# ---------------------------------------------------------------------------
# Wizard declined
# ---------------------------------------------------------------------------


class TestWizardDeclined:
    """User says no at the first prompt -> nothing written."""

    def test_no_config_written_when_declined(
        self, stub_probe, captured_config, scripted_input, monkeypatch
    ):
        from spellbook.worker_llm.probe import DetectedEndpoint

        stub_probe(
            [
                DetectedEndpoint(
                    base_url="http://localhost:11434/v1",
                    label="Ollama",
                    models=["qwen2.5-coder:7b"],
                    reachable=True,
                )
            ]
        )
        scripted_input(["n"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        from spellbook.cli.commands.install import _run_worker_llm_wizard

        _run_worker_llm_wizard()

        # Absolutely no config_set calls when the user declines.
        assert captured_config == []


# ---------------------------------------------------------------------------
# Wizard with probe hits
# ---------------------------------------------------------------------------


class TestWizardWithProbeHits:
    """Probe finds an endpoint; user picks it, picks a model, enables a feature."""

    def test_writes_config_and_doctor_green(
        self,
        stub_probe,
        captured_config,
        scripted_input,
        monkeypatch,
        worker_llm_transport,
    ):
        from spellbook.worker_llm.probe import DetectedEndpoint

        stub_probe(
            [
                DetectedEndpoint(
                    base_url="http://localhost:11434/v1",
                    label="Ollama",
                    models=["qwen2.5-coder:7b", "llama3:8b"],
                    reachable=True,
                )
            ]
        )
        # Answers (in order):
        # 1. Enable worker LLM? -> y
        # 2. Pick endpoint (index 1 in 1-based menu) -> 1
        # 3. Pick model -> 1
        # 4. API key (blank) -> ""
        # 5. Enable transcript_harvest? -> y
        # 6. Enable tool_safety? -> n
        # 7. Enable memory_rerank? -> n
        # 8. Enable read_claude_memory? -> n
        # 9. Run doctor now? -> n
        scripted_input(["y", "1", "1", "", "y", "n", "n", "n", "n"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        from spellbook.cli.commands.install import _run_worker_llm_wizard

        _run_worker_llm_wizard()

        # Verify the written keys cover the essential set.
        keys_written = {k for (k, _v) in captured_config}
        assert "worker_llm_base_url" in keys_written
        assert "worker_llm_model" in keys_written
        assert "worker_llm_feature_transcript_harvest" in keys_written

        # Base URL and model must match the selection.
        by_key = dict(captured_config)
        assert by_key["worker_llm_base_url"] == "http://localhost:11434/v1"
        assert by_key["worker_llm_model"] == "qwen2.5-coder:7b"
        assert by_key["worker_llm_feature_transcript_harvest"] is True
        # Declined features are still explicitly set to False so there is no
        # ambiguity between "user said no" and "user was never asked".
        assert by_key["worker_llm_feature_tool_safety"] is False
        assert by_key["worker_llm_feature_memory_rerank"] is False

        # Now verify doctor would be green against that config.
        from spellbook.core import config as _core_cfg
        from spellbook.worker_llm import config as _wl_cfg

        by_key_all = {
            "worker_llm_base_url": by_key["worker_llm_base_url"],
            "worker_llm_model": by_key["worker_llm_model"],
        }

        def _fake_config_get(k):
            return by_key_all.get(k)

        monkeypatch.setattr(_core_cfg, "config_get", _fake_config_get)
        monkeypatch.setattr(_wl_cfg, "config_get", _fake_config_get)

        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        import io
        import sys as _sys

        saved_stdout = _sys.stdout
        _sys.stdout = io.StringIO()
        try:
            with pytest.raises(SystemExit) as ei:
                _run_doctor(args)
            assert ei.value.code == 0
            out = _sys.stdout.getvalue()
        finally:
            _sys.stdout = saved_stdout
        payload = json.loads(out)
        assert all(r["ok"] for r in payload["results"])


# ---------------------------------------------------------------------------
# Wizard with no probe hits
# ---------------------------------------------------------------------------


class TestWizardNoProbeHits:
    """No endpoints detected; user types a manual URL and continues."""

    def test_manual_url_still_writes_config(
        self, stub_probe, captured_config, scripted_input, monkeypatch
    ):
        stub_probe([])  # Zero detected
        # Answers:
        # 1. Enable worker LLM? -> y
        # 2. Manual URL prompt -> http://remote.host:9999/v1
        # 3. Model prompt -> mistral:latest
        # 4. API key -> secret-key
        # 5..8. All features -> n
        # 9. Run doctor now? -> n
        scripted_input(
            [
                "y",
                "http://remote.host:9999/v1",
                "mistral:latest",
                "secret-key",
                "n",
                "n",
                "n",
                "n",
                "n",
            ]
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        from spellbook.cli.commands.install import _run_worker_llm_wizard

        _run_worker_llm_wizard()

        by_key = dict(captured_config)
        assert by_key["worker_llm_base_url"] == "http://remote.host:9999/v1"
        assert by_key["worker_llm_model"] == "mistral:latest"
        assert by_key["worker_llm_api_key"] == "secret-key"
        # All features default off.
        assert by_key["worker_llm_feature_transcript_harvest"] is False
        assert by_key["worker_llm_feature_tool_safety"] is False
        assert by_key["worker_llm_feature_memory_rerank"] is False


# ---------------------------------------------------------------------------
# Non-tty guard
# ---------------------------------------------------------------------------


class TestNonTtyGuard:
    """Wizard is a noop on non-interactive stdin (CI, piped installs)."""

    def test_noninteractive_is_noop(
        self, stub_probe, captured_config, monkeypatch
    ):
        stub_probe([])
        # isatty False -> wizard MUST NOT prompt (would hang CI).
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def _explode(*_args, **_kwargs):
            raise AssertionError("input() must not be called when stdin is not a tty")

        monkeypatch.setattr("builtins.input", _explode)

        from spellbook.cli.commands.install import _run_worker_llm_wizard

        _run_worker_llm_wizard()
        assert captured_config == []
