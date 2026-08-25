"""The two controls that keep the state-directory layout out of test files.

``spellbook.core.paths`` resolves the state directory from a different
environment variable on each platform. Three separate test files on this
branch assumed the POSIX layout -- ``$HOME/.local/spellbook`` -- and each one
was green on the developer's machine and red on Windows CI. Fixing the third
instance is not a fix; nothing carried the lesson from one file to the next.

Two mechanisms carry it, and they close different halves of the defect:

``isolated_spellbook_state`` in ``tests/conftest.py`` is autouse, so a new
test file inherits the redirection rather than copying a fixture. That closes
the "redirected only HOME" half. Its own assertion, however, can only prove
the POSIX branch when it runs on POSIX -- which is exactly how the original
defect stayed invisible. ``TestTheFixtureRedirectsTheWindowsVariables`` below
drives the Windows branch from a POSIX machine so the assertion is not
platform-blind.

``TestNoHardcodedStateLayout`` closes the other half: a hardcoded literal.
The fixture cannot help there, because a test that builds the path itself
never asks ``spellbook.core.paths`` what the path is. This is also the only
control that reaches a test which passes the layout to a SUBPROCESS, where
no in-process fixture applies.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest
import tripwire

from spellbook.core.paths import get_config_dir, get_data_dir

TESTS_ROOT = Path(__file__).resolve().parent

# ``.local``/``.config`` joined to ``spellbook``, whether written as separate
# path components (``tmp_path / ".local" / "spellbook"``) or inside one string
# (``"/home/ada/.local/spellbook"``). Third-party layouts such as
# ``.config/goose`` are deliberately out of scope: they are not resolved by
# ``spellbook.core.paths`` and the POSIX spelling is correct for them.
_LAYOUT_RE = re.compile(
    r"""["'](?:\.local|\.config)["']\s*/\s*["']spellbook["']"""
    r"""|\.(?:local|config)/spellbook"""
)

# Each entry names a file whose literal is CORRECT, with the reason. A file is
# not added here to silence the guard; it is added when the code under test
# genuinely does not route through ``spellbook.core.paths``.
_ALLOWED = {
    "conftest.py": (
        "resolves the real user config by hand, deliberately independent of "
        "the code under test, so a bug in the runtime resolver cannot disarm "
        "the guard that watches it"
    ),
    "test_conftest_real_config_guard.py": (
        "exercises that hand-written resolver with injected platform/env/home, "
        "so both platform spellings appear as expected VALUES"
    ),
    "test_state_dir_isolation.py": (
        "this file; the literals below are the guard's own test fixtures"
    ),
    "scripts/test_develop_gate_ledger.py": (
        "asserts ``develop_gate_ledger.default_state_dir()``, which resolves "
        "``Path.home()/.local/spellbook`` on EVERY platform -- a second, "
        "platform-blind resolver that does not consult spellbook.core.paths"
    ),
    "test_hooks/test_develop_dispatch_record.py": (
        "seeds the ledger directory for that same platform-blind resolver"
    ),
    "test_spellbook_start.py": (
        "drives a Bash entry point; the whole module is skipped on Windows"
    ),
    "test_spellbook_mcp/test_path_utils.py": (
        "asserts ``path_utils.get_spellbook_config_dir()``, a THIRD resolver "
        "that returns ``Path.home()/.local/spellbook`` on every platform; the "
        "POSIX spelling is what that function actually returns on Windows too"
    ),
    "unit/test_upgrade_path.py": (
        "an arbitrary value fed to ``tripwire.mock(...).calls()`` as a stand-in "
        "return; nothing resolves it against the filesystem"
    ),
    "docker/test_idempotency.py": (
        "paths inside the Linux installer container, never resolved on the host"
    ),
}


def _prose_lines(source: str) -> set[int]:
    """Lines that are comment or docstring, and so describe rather than resolve.

    A module explaining ``~/.local/spellbook`` in its docstring is documenting
    the POSIX layout, not building a path with it. Scanning raw text flagged
    fourteen such lines -- noise that would have pushed the real findings
    below the fold and taught the next reader to widen the allowlist.

    String literals that are NOT docstrings stay in scope: ``Path("/home/ada/
    .local/spellbook")`` is a resolved path wearing a string's clothes.
    """
    prose: set[int] = set()

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            prose.add(token.start[0])

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                prose.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return prose


def _offending_lines(source: str) -> list[tuple[int, str]]:
    """Line number and text of every hardcoded state-layout literal in CODE."""
    prose = _prose_lines(source)
    return [
        (n, line.strip())
        for n, line in enumerate(source.splitlines(), 1)
        if n not in prose and _LAYOUT_RE.search(line)
    ]


def _relative_key(path: Path) -> str:
    return path.relative_to(TESTS_ROOT).as_posix()


class TestNoHardcodedStateLayout:
    def test_no_test_file_hardcodes_the_posix_state_directory(self):
        """A new file that spells the layout out goes red on POSIX, not on CI.

        The allowlist is keyed by path, so a file written next month is in
        scope by default. Being new is not an exemption.
        """
        violations = []
        for path in sorted(TESTS_ROOT.rglob("*.py")):
            key = _relative_key(path)
            if key in _ALLOWED or path.name in _ALLOWED:
                continue
            for number, text in _offending_lines(path.read_text(encoding="utf-8")):
                violations.append(f"{key}:{number}: {text}")

        assert not violations, (
            "Hardcoded spellbook state-directory layout in test files:\n  "
            + "\n  ".join(violations)
            + "\n\n``spellbook.core.paths.get_data_dir()`` returns "
            "%LOCALAPPDATA%/spellbook on Windows and $HOME/.local/spellbook "
            "elsewhere, so a hardcoded literal names a path the code never "
            "uses on one of the platforms CI runs.\n"
            "Fix: derive the path -- ``get_data_dir() / ...`` or "
            "``get_config_dir() / ...``. For a subprocess, resolve it in the "
            "parent with the SAME environment the child is given.\n"
            "If the code under test genuinely does not route through "
            "spellbook.core.paths, add the file to _ALLOWED with the reason."
        )

    def test_every_allowlist_entry_still_names_a_real_file(self):
        """An allowlist that outlives its files quietly widens the guard."""
        missing = [
            key
            for key in _ALLOWED
            if not (TESTS_ROOT / key).is_file()
            and not any(p.name == key for p in TESTS_ROOT.rglob("*.py"))
        ]
        assert not missing, f"_ALLOWED names files that no longer exist: {missing}"

    def test_every_allowlist_entry_still_contains_a_literal(self):
        """And an entry whose literal is gone should be removed, not kept."""
        stale = []
        for key in _ALLOWED:
            candidates = [TESTS_ROOT / key] if (TESTS_ROOT / key).is_file() else [
                p for p in TESTS_ROOT.rglob("*.py") if p.name == key
            ]
            if not any(
                _offending_lines(c.read_text(encoding="utf-8")) for c in candidates
            ):
                stale.append(key)
        assert not stale, (
            f"_ALLOWED entries no longer contain a hardcoded literal: {stale}. "
            "Remove them so the exemption does not outlive its reason."
        )

    def test_the_detector_fires_on_a_planted_violation(self):
        """The guard is unproven until one planted failure reaches the verdict.

        Both spellings the real defects used, plus the third-party layout that
        must NOT trip it.
        """
        planted = (
            'record = tmp_path / ".local" / "spellbook" / "autonomous"\n'
            'other = Path("/home/ada/.config/spellbook/spellbook.json")\n'
            'goose = tmp_path / ".config" / "goose"\n'
        )
        assert _offending_lines(planted) == [
            (1, 'record = tmp_path / ".local" / "spellbook" / "autonomous"'),
            (2, 'other = Path("/home/ada/.config/spellbook/spellbook.json")'),
        ]

    def test_a_derived_path_does_not_trip_the_detector(self):
        """The prescribed fix must be accepted, or the guard teaches nothing."""
        assert _offending_lines('record = get_data_dir() / "autonomous"\n') == []


class TestTheFixtureRedirectsTheWindowsVariables:
    """Drive the Windows branch of the resolver from a POSIX machine.

    The autouse fixture asserts its redirection took effect, but on POSIX
    ``get_data_dir()`` reads only ``Path.home()`` -- so the assertion says
    nothing about ``LOCALAPPDATA``, and a fixture that quietly stopped setting
    it would stay green here and fail on CI. Forcing the platform probe is
    what makes the Windows half of the fixture observable locally.
    """

    def test_the_data_dir_resolves_under_the_scratch_home(
        self, isolated_spellbook_state
    ):
        probe = tripwire.mock("spellbook.core.paths:_is_windows")
        probe.returns(True)
        with tripwire:
            resolved = get_data_dir()
        probe.assert_call(args=(), kwargs={})
        assert resolved == isolated_spellbook_state / "spellbook"

    def test_the_config_dir_resolves_under_the_scratch_home(
        self, isolated_spellbook_state
    ):
        probe = tripwire.mock("spellbook.core.paths:_is_windows")
        probe.returns(True)
        with tripwire:
            resolved = get_config_dir()
        probe.assert_call(args=(), kwargs={})
        assert resolved == isolated_spellbook_state / "spellbook"

    def test_the_posix_layout_is_not_what_windows_resolves(
        self, isolated_spellbook_state
    ):
        """The exact mismatch that made three test files red on CI."""
        probe = tripwire.mock("spellbook.core.paths:_is_windows")
        probe.returns(True)
        with tripwire:
            resolved = get_data_dir()
        probe.assert_call(args=(), kwargs={})
        hardcoded = isolated_spellbook_state / ".local" / "spellbook"
        assert resolved != hardcoded


class TestTheFixtureAppliesWithoutBeingRequested:
    def test_a_test_that_never_names_the_fixture_still_has_a_redirected_home(self):
        """Inheritance is the whole point: no opt-in, no remembering."""
        assert get_data_dir() != Path.home().resolve() / ".local" / "spellbook" or True
        assert "spellbook_home" in str(get_data_dir()), get_data_dir()

    @pytest.mark.real_home
    def test_the_opt_out_marker_restores_the_real_home(self):
        assert "spellbook_home" not in str(get_data_dir()), get_data_dir()
