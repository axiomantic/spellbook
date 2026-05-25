"""Grep gate: forbid tier-classifier tokens and removed execution-mode vocabulary.

Implements the §10.2 / IMP-4 widened verification gate from the develop-rework
design. Greps the whole ``skills/`` + ``commands/`` + ``agents/`` tree for two
classes of forbidden tokens and FAILS on any non-allowlisted match:

(a) Tier-as-classifier tokens:  ``\\b(TRIVIAL|SIMPLE|STANDARD|COMPLEX)\\b``
    (case-sensitive uppercase -- lowercase prose excluded by the pattern).
(b) Removed execution-mode vocabulary:
    ``\\b(work_items|sub_orchestrators|execution_mode)\\b``.

Allowlisting is CONTENT/SYMBOL-anchored (design N-2): each allowlist entry pairs
a path glob with an anchor substring that must appear on the matched line. Line
numbers are never used as anchors -- they rot as files change.

The reproducible checker lives in ``scripts/check_removed_mode_tokens.py``; this
test loads it and asserts both directions of the contract:
  - the gate PASSES on the current clean worktree (allowlisted occurrences
    tolerated), and
  - the gate FAILS when a forbidden, non-allowlisted token is planted in a
    ``skills/`` / ``commands/`` / ``agents/`` file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_removed_mode_tokens.py"


def _load_checker():
    """Load the checker module from scripts/ (not an installed package)."""
    spec = importlib.util.spec_from_file_location("check_removed_mode_tokens", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_removed_mode_tokens"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _load_checker()


# ---------------------------------------------------------------------------
# (1) Clean-tree contract: zero non-allowlisted violations.
# ---------------------------------------------------------------------------


def test_clean_worktree_has_zero_nonallowlisted_violations(checker):
    """The shipped tree contains only allowlisted occurrences -> gate passes.

    Asserts EXACT emptiness of the violation list (Full Assertion Principle):
    any non-allowlisted tier token or removed-mode token anywhere under
    skills/ + commands/ + agents/ would surface here as a Violation and fail
    this assertion with an actionable file:line message.
    """
    violations = checker.find_violations(REPO_ROOT)
    assert violations == [], "Non-allowlisted forbidden tokens found:\n" + "\n".join(
        checker.format_violation(v) for v in violations
    )


# ---------------------------------------------------------------------------
# (2) Planted-violation contract: a forbidden token in a non-allowlisted
#     skills/ file MUST be detected, for each forbidden token.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "token_class"),
    [
        ("TRIVIAL", "tier"),
        ("SIMPLE", "tier"),
        ("STANDARD", "tier"),
        ("COMPLEX", "tier"),
        ("work_items", "removed-mode"),
        ("sub_orchestrators", "removed-mode"),
        ("execution_mode", "removed-mode"),
    ],
)
def test_planted_token_in_skills_is_detected(checker, tmp_path, token, token_class):
    """Each forbidden token planted in a non-allowlisted file is reported.

    Builds a minimal fake repo root (skills/<dir>/SKILL.md) containing exactly
    one forbidden token on a known line, runs the checker against that root,
    and asserts the COMPLETE violation it must report -- path, 1-based line
    number, the offending token, the full source line, and the class. Asserts
    EXACTLY one violation so a planted token cannot be silently double-counted
    or accompanied by spurious extras.
    """
    skills_dir = tmp_path / "skills" / "planted-skill"
    skills_dir.mkdir(parents=True)
    skill_file = skills_dir / "SKILL.md"
    # One blank line, then the offending line, so the reported lineno is 2.
    source_line = f"This routing uses {token} as a classifier."
    skill_file.write_text(f"# Planted\n{source_line}\n", encoding="utf-8")
    # commands/ and agents/ exist but are clean.
    (tmp_path / "commands").mkdir()
    (tmp_path / "agents").mkdir()

    violations = checker.find_violations(tmp_path)

    expected = checker.Violation(
        path="skills/planted-skill/SKILL.md",
        lineno=2,
        token=token,
        token_class=token_class,
        line=source_line,
    )
    assert violations == [expected]


def test_planted_token_in_commands_is_detected(checker, tmp_path):
    """A removed-mode token planted in commands/ is reported (not just skills/)."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "agents").mkdir()
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    cmd_file = commands_dir / "feature-config.md"
    source_line = "FOR item IN work_items[priority]: do thing"
    cmd_file.write_text(f"{source_line}\n", encoding="utf-8")

    violations = checker.find_violations(tmp_path)

    assert violations == [
        checker.Violation(
            path="commands/feature-config.md",
            lineno=1,
            token="work_items",
            token_class="removed-mode",
            line=source_line,
        )
    ]


def test_planted_token_in_agents_is_detected(checker, tmp_path):
    """A tier token planted in agents/ is reported (agents/ is in scope)."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "commands").mkdir()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_file = agents_dir / "implementer.md"
    source_line = "Only escalate when the task is COMPLEX enough."
    agent_file.write_text(f"{source_line}\n", encoding="utf-8")

    violations = checker.find_violations(tmp_path)

    assert violations == [
        checker.Violation(
            path="agents/implementer.md",
            lineno=1,
            token="COMPLEX",
            token_class="tier",
            line=source_line,
        )
    ]


# ---------------------------------------------------------------------------
# (3) Allowlist semantics: content-anchored, path-scoped, and NEVER blanket
#     for work_items / sub_orchestrators outside their anchored exceptions.
# ---------------------------------------------------------------------------


def test_lowercase_prose_is_not_flagged(checker, tmp_path):
    """Lowercase 'complex'/'simple'/'standard' prose must NOT trip the tier gate.

    The uppercase word-boundary pattern excludes ordinary prose; this guards
    against a future regression to a case-insensitive match.
    """
    skills_dir = tmp_path / "skills" / "prose-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "This is a complex, simple, standard sentence about work items.\n",
        encoding="utf-8",
    )
    (tmp_path / "commands").mkdir()
    (tmp_path / "agents").mkdir()

    assert checker.find_violations(tmp_path) == []


def test_anchored_allowlist_suppresses_only_matching_line(checker, tmp_path):
    """An allowlist entry suppresses ONLY lines bearing its anchor substring.

    Same file, same token: the line carrying the anchor is suppressed, a
    second line with the same token but WITHOUT the anchor still fails. This
    proves the allowlist is line-content-anchored, not file-wide blanket.
    """
    debugging_dir = tmp_path / "skills" / "debugging"
    debugging_dir.mkdir(parents=True)
    # Line 1 carries the real allowlist anchor "If SIMPLE:"; line 2 is a
    # non-anchored SIMPLE that must still be reported.
    (debugging_dir / "SKILL.md").write_text(
        "**If SIMPLE:** handle the easy bug path\nPick the SIMPLE tier and proceed.\n",
        encoding="utf-8",
    )
    (tmp_path / "commands").mkdir()
    (tmp_path / "agents").mkdir()

    violations = checker.find_violations(tmp_path)

    assert violations == [
        checker.Violation(
            path="skills/debugging/SKILL.md",
            lineno=2,
            token="SIMPLE",
            token_class="tier",
            line="Pick the SIMPLE tier and proceed.",
        )
    ]


def test_work_items_anchored_exception_is_line_scoped(checker, tmp_path):
    """The fixing-tests work_items loop-var exception is anchored, not blanket.

    The real tree's only legitimate work_items occurrence is the pseudocode
    loop ``FOR item IN work_items[priority]`` in fixing-tests/SKILL.md (a
    pre-existing local loop variable, unrelated to develop's removed routing).
    The anchor is the literal ``work_items[priority]``. A different work_items
    use in the same file (e.g. describing the removed execution mode) must
    still fail.
    """
    ft_dir = tmp_path / "skills" / "fixing-tests"
    ft_dir.mkdir(parents=True)
    (ft_dir / "SKILL.md").write_text(
        "    FOR item IN work_items[priority]:\nUse the work_items execution mode here.\n",
        encoding="utf-8",
    )
    (tmp_path / "commands").mkdir()
    (tmp_path / "agents").mkdir()

    violations = checker.find_violations(tmp_path)

    assert violations == [
        checker.Violation(
            path="skills/fixing-tests/SKILL.md",
            lineno=2,
            token="work_items",
            token_class="removed-mode",
            line="Use the work_items execution mode here.",
        )
    ]
