"""The autonomous-mode skill's claims about code must resolve against code.

A skill that points at a mechanism is only useful while the pointer is
live. Two ways it dies quietly: the file or symbol it names gets renamed,
or the skill copies a value out of the code so the copy can drift.

These tests are driven FROM the code, never from the prose. Every expected
string is imported (``AUTONOMOUS_ESCAPE_PHRASES``, ``PHILOSOPHIES``) or
resolved on the filesystem, so a rename in Python turns them red without
anyone editing this file. Nothing here asserts that a sentence exists.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "autonomous-mode" / "SKILL.md"

HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

from spellbook.core.autonomous import PHILOSOPHIES  # noqa: E402

# A backticked repo-relative source path, e.g. `spellbook/core/autonomous.py`.
_CITED_PATH_RE = re.compile(
    r"`((?:spellbook|hooks|installer|rules|scripts|skills|commands)/[\w./-]+"
    r"\.(?:py|md|json|sh))`"
)
# A backticked screaming-snake identifier, e.g. `BLOCK_WINDOW_SECONDS`.
# The underscore requirement keeps prose emphasis (ALLOW, BLOCK) out.
_CITED_SYMBOL_RE = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")


@pytest.fixture(scope="module")
def skill_text() -> str:
    if not SKILL_PATH.is_file():
        pytest.fail(f"skill not found: {SKILL_PATH}")
    return SKILL_PATH.read_text(encoding="utf-8")


def test_cited_paths_exist(skill_text: str) -> None:
    """Every source file the skill sends a reader to is really there."""
    cited = sorted(set(_CITED_PATH_RE.findall(skill_text)))
    assert cited, "skill cites no source file; it should point at the mechanism"
    missing = [p for p in cited if not (REPO_ROOT / p).is_file()]
    assert missing == []


def test_cited_symbols_are_defined_in_a_cited_file(skill_text: str) -> None:
    """Every constant the skill names is findable at a path the skill names."""
    cited_paths = sorted(set(_CITED_PATH_RE.findall(skill_text)))
    haystack = "\n".join(
        (REPO_ROOT / p).read_text(encoding="utf-8")
        for p in cited_paths
        if (REPO_ROOT / p).is_file()
    )
    symbols = sorted(set(_CITED_SYMBOL_RE.findall(skill_text)))
    assert symbols, "skill names no constant; it should point at where values live"
    unresolved = [s for s in symbols if s not in haystack]
    assert unresolved == []


def test_escape_phrases_are_not_retyped_into_prose(skill_text: str) -> None:
    """The literals live in the hook. A prose copy would drift from it."""
    lowered = skill_text.lower()
    copied = [p for p in spellbook_hook.AUTONOMOUS_ESCAPE_PHRASES if p in lowered]
    assert copied == []


def test_philosophy_meanings_are_not_duplicated(skill_text: str) -> None:
    """``PHILOSOPHIES`` is the one home for what each id means."""
    normalized = " ".join(skill_text.split()).lower()
    duplicated = [
        pid
        for pid, meaning in PHILOSOPHIES.items()
        if " ".join(meaning.split()).lower() in normalized
    ]
    assert duplicated == []
