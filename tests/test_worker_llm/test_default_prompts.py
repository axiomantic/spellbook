"""Tests asserting the shipped default prompts are present and complete."""

from pathlib import Path

import pytest

from spellbook.worker_llm.prompts import DEFAULT_PROMPT_DIR


@pytest.mark.parametrize(
    "name",
    [
        "roundtable_voice",
        "tool_safety",
    ],
)
def test_prompt_present_and_substantive(name):
    p = DEFAULT_PROMPT_DIR / f"{name}.md"
    assert p.exists(), p
    text = p.read_text(encoding="utf-8")
    assert len(text) > 400


def test_roundtable_has_word_cap():
    text = (DEFAULT_PROMPT_DIR / "roundtable_voice.md").read_text(
        encoding="utf-8"
    )
    assert "200 words" in text


def test_roundtable_mentions_justice_section():
    text = (DEFAULT_PROMPT_DIR / "roundtable_voice.md").read_text(
        encoding="utf-8"
    )
    assert "Justice" in text
    assert "Binding Decision: APPROVE or ITERATE" in text


def test_tool_safety_lists_three_verdicts():
    text = (DEFAULT_PROMPT_DIR / "tool_safety.md").read_text(encoding="utf-8")
    for v in ('"OK"', '"WARN"', '"BLOCK"'):
        assert v in text


def test_default_prompt_dir_contains_only_expected_files():
    names = sorted(p.name for p in DEFAULT_PROMPT_DIR.iterdir() if p.is_file())
    assert names == [
        "roundtable_voice.md",
        "tool_safety.md",
    ]


def test_default_prompt_dir_is_a_directory():
    assert isinstance(DEFAULT_PROMPT_DIR, Path)
    assert DEFAULT_PROMPT_DIR.is_dir()
