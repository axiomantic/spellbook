"""Unit tests for skills/dedupe/scripts/dedupe.py.

Loads the helper as a module via importlib (without executing main) and
exercises each subcommand against seeded fixture corpora. Default suite --
no integration marker; pure stdlib, no QMD/Serena.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
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


# ---------------------------------------------------------------------------
# Task 2: stdlib-only import check (encodes the no-new-deps + M5 constraint:
# no spellbook.*, no third-party). Parses dedupe.py's own import statements via
# ast and verifies every imported top-level module is part of the standard
# library (sys.stdlib_module_names is the source of truth, so os/types/dataclasses
# and any future stdlib addition are accepted automatically) while a
# spellbook.* or third-party import would FAIL the test.
# ---------------------------------------------------------------------------


def _imported_roots() -> tuple[set[str], bool]:
    source = HELPER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    roots: set[str] = set()
    has_relative = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # level == 0 means absolute import; relative imports (level > 0)
            # have no module root to allowlist and are never stdlib.
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
            elif node.level > 0:
                has_relative = True
    return roots, has_relative


def test_dedupe_imports_stdlib_only():
    """dedupe.py must import ONLY stdlib modules: no spellbook.*, no third-party."""
    imported_roots, has_relative = _imported_roots()

    assert "argparse" in imported_roots, (
        "no imports parsed — HELPER_PATH or _imported_roots likely broken"
    )

    assert not has_relative, (
        "dedupe.py must not use relative imports (must be importlib-loadable standalone)"
    )

    forbidden = {root for root in imported_roots if root.startswith("spellbook")}
    assert not forbidden, f"dedupe.py must not import spellbook.*: {sorted(forbidden)}"

    non_stdlib = {root for root in imported_roots if root not in sys.stdlib_module_names}
    assert not non_stdlib, (
        "dedupe.py imported non-stdlib modules "
        f"(no new runtime deps allowed): {sorted(non_stdlib)}"
    )


# ---------------------------------------------------------------------------
# Task 3: inline Jaccard signal + normalization (plan §"Task 3" Step 1).
# The edge-case contract mirrors spellbook/forged/context_filtering.py
# similarity() (lines 354-394) EXACTLY:
#   - BOTH post-filter token sets empty  -> 1.0
#   - EXACTLY ONE post-filter set empty  -> 0.0
#   - else                               -> intersection / union
# _tokens intentionally OMITS the len(w) > 2 short-word filter (that filter
# lives in _extract_keywords, NOT in similarity()), so short words are RETAINED.
# ---------------------------------------------------------------------------


def test_jaccard_identical_is_one(dedupe):
    assert dedupe.jaccard("the quick brown fox", "the quick brown fox") == 1.0


def test_jaccard_disjoint_is_zero(dedupe):
    # No shared non-stop-word tokens -> intersection empty -> 0.0.
    assert dedupe.jaccard("alpha beta gamma", "delta epsilon zeta") == 0.0


def test_jaccard_both_empty_is_one(dedupe):
    assert dedupe.jaccard("", "") == 1.0


def test_jaccard_one_empty_is_zero(dedupe):
    assert dedupe.jaccard("something here", "") == 0.0
    assert dedupe.jaccard("", "something here") == 0.0


def test_jaccard_both_all_stop_words_is_one(dedupe):
    # Both reduce to empty token sets AFTER stop-word filtering -> mirrors the
    # similarity() post-filter both-empty branch -> 1.0 (not a pre-filter empty).
    assert dedupe.jaccard("the and or", "of to in") == 1.0


def test_jaccard_one_all_stop_words_is_zero(dedupe):
    # One side reduces to empty after stop-word filtering, the other does not
    # -> mirrors the similarity() post-filter exactly-one-empty branch -> 0.0.
    assert dedupe.jaccard("the and or", "alpha beta gamma") == 0.0
    assert dedupe.jaccard("alpha beta gamma", "the and or") == 0.0


def test_jaccard_partial_overlap_exact_ratio(dedupe):
    # tokens(a) = {alpha, beta, gamma, delta}; tokens(b) = {alpha, beta, gamma, omega}
    # (no stop words present). intersection = {alpha, beta, gamma} = 3;
    # union = {alpha, beta, gamma, delta, omega} = 5 -> 3/5 = 0.6.
    score = dedupe.jaccard("alpha beta gamma delta", "alpha beta gamma omega")
    assert score == 3 / 5


def test_jaccard_stop_words_filtered(dedupe):
    # "the cat" and "a cat" share only the non-stop-word token {cat}; the stop
    # words "the"/"a" are filtered out, so both reduce to {cat} -> identical -> 1.0.
    assert dedupe.jaccard("the cat", "a cat") == 1.0


def test_jaccard_short_words_retained(dedupe):
    # Short words (<=2 chars) are NOT stop words here and must be RETAINED by
    # _tokens (the len(w) > 2 filter lives in _extract_keywords, not here).
    # tokens(a) = {go, ox}; tokens(b) = {go, ax}. intersection = {go} = 1;
    # union = {go, ox, ax} = 3 -> 1/3. If short words were dropped both sets
    # would be empty and this would wrongly be 1.0.
    assert dedupe.jaccard("go ox", "go ax") == 1 / 3


def test_tokens_retains_short_words(dedupe):
    # Direct check of _tokens: a 2-char non-stop word is kept verbatim.
    assert dedupe._tokens("go ox now") == {"go", "ox", "now"}


def test_tokens_drops_stop_words(dedupe):
    # Stop words removed; remaining (including short ones) retained.
    assert dedupe._tokens("the go and ox") == {"go", "ox"}


def test_normalize_lowercases_and_collapses_ws(dedupe):
    assert dedupe.normalize("  The   QUICK  fox  ") == "the quick fox"


def test_normalize_strips_emphasis(dedupe):
    assert dedupe.normalize("**bold** and _italic_ text") == "bold and italic text"
    assert "*" not in dedupe.normalize("**bold** and _italic_ text")
    assert "_" not in dedupe.normalize("**bold** and _italic_ text")


def test_normalize_strips_backticks(dedupe):
    assert dedupe.normalize("run `git push` now") == "run git push now"
