"""Tests for ``spellbook.worker_llm.prompts``."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from spellbook.worker_llm import prompts as wl_prompts


def _fake_cfg(allow_overrides: bool) -> SimpleNamespace:
    return SimpleNamespace(allow_prompt_overrides=allow_overrides)


def test_load_transcript_harvest_returns_package_default(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(True)
    )
    text, override_loaded = wl_prompts.load("transcript_harvest")
    assert override_loaded is False
    # The shipped default contains the anti-drift line.
    assert "MUST start with [" in text
    assert "end with ]" in text


def test_load_memory_rerank_returns_default(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(True)
    )
    text, override_loaded = wl_prompts.load("memory_rerank")
    assert override_loaded is False
    assert "relevance_0_1" in text


def test_load_roundtable_voice_returns_default(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(True)
    )
    text, override_loaded = wl_prompts.load("roundtable_voice")
    assert override_loaded is False
    assert "under 200 words" in text


def test_load_tool_safety_returns_default(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(True)
    )
    text, override_loaded = wl_prompts.load("tool_safety")
    assert override_loaded is False
    assert '"OK"' in text
    assert '"WARN"' in text
    assert '"BLOCK"' in text


def test_override_loaded_when_present_and_allowed(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(True)
    )
    published: list = []
    monkeypatch.setattr(
        wl_prompts,
        "publish_override_loaded",
        lambda task, path: published.append((task, path)),
    )
    override_file = tmp_path / "transcript_harvest.md"
    override_file.write_text("OVERRIDDEN BODY")
    text, override_loaded = wl_prompts.load("transcript_harvest")
    assert text == "OVERRIDDEN BODY"
    assert override_loaded is True
    assert published == [("transcript_harvest", str(override_file))]


def test_override_disabled_flag_skips_override(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(False)
    )
    published: list = []
    monkeypatch.setattr(
        wl_prompts,
        "publish_override_loaded",
        lambda task, path: published.append((task, path)),
    )
    (tmp_path / "transcript_harvest.md").write_text("OVERRIDDEN")
    text, override_loaded = wl_prompts.load("transcript_harvest")
    assert text != "OVERRIDDEN"
    assert override_loaded is False
    assert published == []


def test_override_absent_uses_default(monkeypatch, tmp_path):
    monkeypatch.setattr(wl_prompts, "OVERRIDE_PROMPT_DIR", tmp_path)
    monkeypatch.setattr(
        wl_prompts, "get_worker_config", lambda: _fake_cfg(True)
    )
    # No override file in tmp_path.
    _, override_loaded = wl_prompts.load("tool_safety")
    assert override_loaded is False


def test_unknown_task_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        wl_prompts.load("nonexistent_task")
    assert str(excinfo.value) == "Unknown worker-llm task: nonexistent_task"


def test_override_directory_is_home_local_worker_prompts():
    # Sanity check on the module constant — tests elsewhere monkeypatch it.
    expected = Path.home() / ".local" / "spellbook" / "worker_prompts"
    assert wl_prompts.OVERRIDE_PROMPT_DIR == expected


def test_default_directory_points_at_package():
    expected = Path(wl_prompts.__file__).parent / "default_prompts"
    assert wl_prompts.DEFAULT_PROMPT_DIR == expected
