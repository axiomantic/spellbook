"""Unit tests for skills/dedupe/scripts/dedupe.py.

Loads the helper as a module via importlib (without executing main) and
exercises each subcommand against seeded fixture corpora. Default suite --
no integration marker; pure stdlib, no QMD/Serena.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

HELPER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "dedupe" / "scripts" / "dedupe.py"
)
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dedupe"


@pytest.fixture
def dedupe():
    spec = importlib.util.spec_from_file_location("_dedupe_helper_test", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(module, *argv: str) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = module.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Task 1: skeleton smoke tests (plan §"Task 1" Step 1)
# ---------------------------------------------------------------------------


def test_module_loads_and_exposes_main(dedupe):
    assert callable(dedupe.main)


def test_no_args_returns_zero_with_usage(dedupe):
    rc, stdout, _ = _run(dedupe)
    assert rc == 0
    assert "dedupe" in stdout.lower()


def test_unknown_subcommand_is_error(dedupe):
    rc, _, _ = _run(dedupe, "bogus-subcommand")
    assert rc != 0


# ---------------------------------------------------------------------------
# Task 1: the four subcommands are registered and dispatchable, each emitting
# a valid JSON shell ({"version": SCHEMA_VERSION}) and returning 0 (stubs).
# ---------------------------------------------------------------------------


def test_schema_version_constant(dedupe):
    assert dedupe.SCHEMA_VERSION == "1"


@pytest.mark.parametrize(
    "argv",
    [
        ("expand-group", "--seed", "alpha"),
        ("detect", "--seed", "alpha"),
        ("external-callers",),
        ("verify",),
    ],
    ids=["expand-group", "detect", "external-callers", "verify"],
)
def test_subcommand_registered_and_emits_version_shell(dedupe, argv):
    """Each subcommand parses and dispatches to a stub that emits {"version": "1"}."""
    rc, stdout, _ = _run(dedupe, *argv)
    assert rc == 0
    assert json.loads(stdout) == {"version": "1"}


# ---------------------------------------------------------------------------
# Task 1: resolve_corpus contract (the single source of truth for the
# corpus/seed file set -- plan §"--corpus contract").
# ---------------------------------------------------------------------------


def _md(path: Path, name: str) -> Path:
    f = path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# heading\n\nbody text\n", encoding="utf-8")
    return f


def test_resolve_corpus_flat_dir_of_md_files(dedupe, tmp_path):
    """A directory entry is walked recursively for *.md and returns the
    de-duplicated, sorted list of resolved file paths."""
    a = _md(tmp_path, "file_a.md")
    b = _md(tmp_path, "file_b.md")
    nested = _md(tmp_path, "sub/nested.md")
    (tmp_path / "ignore.txt").write_text("not markdown\n", encoding="utf-8")

    result = dedupe.resolve_corpus(str(tmp_path))

    assert result == sorted([a.resolve(), b.resolve(), nested.resolve()])


def test_resolve_corpus_comma_separated_list_of_files(dedupe, tmp_path):
    """A comma-separated list of explicit file paths resolves to exactly those
    files (mixing files is allowed), de-duplicated and sorted."""
    a = _md(tmp_path, "file_a.md")
    b = _md(tmp_path, "file_b.md")
    _md(tmp_path, "file_c.md")  # NOT listed -> must NOT appear

    arg = f"{a},{b}"
    result = dedupe.resolve_corpus(arg)

    assert result == sorted([a.resolve(), b.resolve()])


def test_resolve_corpus_mixes_dir_and_file_entries(dedupe, tmp_path):
    """Mixing dir and file entries is allowed (dirA,fileB.md)."""
    dir_a = tmp_path / "dirA"
    inner = _md(dir_a, "inner.md")
    file_b = _md(tmp_path, "file_b.md")

    arg = f"{dir_a},{file_b}"
    result = dedupe.resolve_corpus(arg)

    assert result == sorted([inner.resolve(), file_b.resolve()])


def test_resolve_corpus_skips_non_md_file_entries(dedupe, tmp_path):
    """Explicit non-*.md file entries are skipped (must end .md)."""
    a = _md(tmp_path, "file_a.md")
    txt = tmp_path / "notes.txt"
    txt.write_text("plain text\n", encoding="utf-8")

    arg = f"{a},{txt}"
    result = dedupe.resolve_corpus(arg)

    assert result == [a.resolve()]


def test_resolve_corpus_dedupes_overlapping_entries(dedupe, tmp_path):
    """A file reachable via both a dir walk and an explicit entry appears once."""
    a = _md(tmp_path, "file_a.md")

    arg = f"{tmp_path},{a}"
    result = dedupe.resolve_corpus(arg)

    assert result == [a.resolve()]


def test_resolve_corpus_default_glob_under_spellbook_dir(dedupe, tmp_path, monkeypatch):
    """DEFAULT (no --corpus) = safe-wide globs under $SPELLBOOK_DIR:
    skills/**/SKILL.md + commands/**/*.md + CLAUDE.md + skills/shared-references/*.md."""
    skill = _md(tmp_path, "skills/alpha/SKILL.md")
    command = _md(tmp_path, "commands/beta.md")
    claude = _md(tmp_path, "CLAUDE.md")
    shared = _md(tmp_path, "skills/shared-references/gamma.md")
    # Files that must NOT be swept by the default globs:
    _md(tmp_path, "skills/alpha/references/extra.md")  # not SKILL.md, not shared-references
    _md(tmp_path, "docs/unrelated.md")

    monkeypatch.setenv("SPELLBOOK_DIR", str(tmp_path))
    result = dedupe.resolve_corpus(None)

    expected = sorted(
        [skill.resolve(), command.resolve(), claude.resolve(), shared.resolve()]
    )
    assert result == expected
