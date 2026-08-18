"""Keep the documented ``resolved_via`` vocabulary in step with its producer.

``scripts/branch-context.sh`` is the PRODUCER of the ``resolved_via`` token
vocabulary: it is the thing that decides which strings can ever appear on a
``resolved_via=`` line. Several skills, commands, and templates then repeat that
vocabulary in prose -- alternation lists, schema tables, worked examples.

Nothing connected the two. A token renamed in the script, or a fifth one added,
left every prose copy silently wrong: no error, no failing gate, just documents
describing a vocabulary the script no longer speaks. That is the silent-failure
shape -- "correct" and "never updated" render identically.

Derivation method: the token set is parsed from the ``RESOLUTION_METHOD="..."``
ASSIGNMENTS, not from the ``# One of: a | b | c`` comment above them.

The assignments are what the script can actually EMIT; the comment is prose and
can drift independently of the code -- it is a second copy of the vocabulary, not
a source for it. It already spans two lines with a parenthetical aside, so
parsing it is fragile as well as circular. Most importantly, a token introduced
by a new assignment whose author forgot the comment would be INVISIBLE to a
comment-based parse, and that is precisely the drift this test exists to catch.
Parsing the comment would move the drift surface rather than remove it.

Two properties are asserted against every documenting file:

* **No unknown token.** A ``resolved_via`` value named in prose must be one the
  script can emit.
* **No incomplete enumeration.** Where a file ENUMERATES the vocabulary -- a
  passage naming two or more distinct tokens -- it must name them all. A passage
  mentioning a single token is a worked example, not an enumeration, and is left
  alone.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SH_SCRIPT = REPO_ROOT / "scripts" / "branch-context.sh"
PY_SCRIPT = REPO_ROOT / "scripts" / "branch-context.py"

# Roots scanned for prose that documents the vocabulary. Files are DISCOVERED by
# content, never listed by name: a new document that repeats the vocabulary is
# covered the day it is written, without editing this test.
DOC_ROOTS = ("skills", "commands")
DOC_SUFFIXES = (".md", ".tpl")

# `RESOLUTION_METHOD="pr-base-ref"`, wherever it sits on the line -- three of the
# five are guarded (`[[ -n "$MERGE_TARGET" ]] && RESOLUTION_METHOD="..."`), so
# this deliberately does NOT anchor to the start of the line. The empty
# initialiser is excluded by requiring a leading letter.
_SH_ASSIGNMENT = re.compile(r'RESOLUTION_METHOD="([a-z][a-z0-9-]*)"')
_PY_ASSIGNMENT = re.compile(r'resolution_method = "([a-z][a-z0-9-]*)"')

# A token named as a `resolved_via` VALUE in prose, in the shapes documents use:
#   resolved_via=pr-base-ref      resolved via pr-base-ref
#   "resolved_via": "pr-base-ref" `resolved_via` is `fallback-literal`
#
# The value must be HYPHENATED. Every token in this vocabulary is, and the
# requirement keeps the pattern off type annotations and subscripts that sit in
# the same position (`resolved_via: str`, `ctx["resolved_via"]`). A rename to a
# single unhyphenated word escapes this check but is still caught by the
# enumeration-completeness test below.
_DOCUMENTED_VALUE = re.compile(
    r"""resolved[ _]via`?"?\s*(?:[=:]|\bis\b|\bas\b)\s*["`]?([a-z]+(?:-[a-z0-9]+)+)""",
    re.IGNORECASE,
)


def _script_tokens() -> frozenset[str]:
    """The token set derived from the producer's assignments."""
    tokens = frozenset(_SH_ASSIGNMENT.findall(SH_SCRIPT.read_text(encoding="utf-8")))
    assert tokens, (
        f"Derived an EMPTY token set from {SH_SCRIPT.name}. The assignment shape "
        f"changed and this test silently stopped checking anything."
    )
    return tokens


def _doc_files() -> list[Path]:
    return sorted(
        path
        for root in DOC_ROOTS
        for path in (REPO_ROOT / root).rglob("*")
        if path.suffix in DOC_SUFFIXES and path.is_file()
    )


def _paragraphs(text: str) -> list[tuple[int, str]]:
    """Split into blank-line-separated blocks, each tagged with its 1-based start line.

    Enumerations are matched per paragraph rather than per line because real ones
    wrap: an alternation list routinely spans two prose lines or several table
    rows, and a line-based check would read each fragment as a separate,
    always-incomplete enumeration.
    """
    blocks: list[tuple[int, str]] = []
    start, buf = 1, []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not buf:
                start = lineno
            buf.append(line)
        elif buf:
            blocks.append((start, " ".join(buf)))
            buf = []
    if buf:
        blocks.append((start, " ".join(buf)))
    return blocks


def test_producer_assignments_yield_a_token_set():
    """The derivation itself works -- guards against a no-op test."""
    assert len(_script_tokens()) >= 2


def test_shell_and_python_producers_agree():
    """Parity: the .py resolver must speak the same vocabulary as the .sh."""
    py_tokens = frozenset(_PY_ASSIGNMENT.findall(PY_SCRIPT.read_text(encoding="utf-8")))
    assert py_tokens == _script_tokens(), (
        f"branch-context.sh and branch-context.py disagree on the resolved_via "
        f"vocabulary. Only in .sh: {sorted(_script_tokens() - py_tokens)}; "
        f"only in .py: {sorted(py_tokens - _script_tokens())}"
    )


def test_no_document_names_an_unknown_resolved_via_token():
    tokens = _script_tokens()
    offenders: list[str] = []
    for path in _doc_files():
        text = path.read_text(encoding="utf-8")
        for match in _DOCUMENTED_VALUE.finditer(text):
            value = match.group(1).lower()
            # Skip template placeholders and prose connectives.
            if value.startswith("$") or value in {"and", "or", "the", "a", "an"}:
                continue
            if value not in tokens:
                lineno = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {value!r}")
    assert not offenders, (
        "Documents name resolved_via values that scripts/branch-context.sh "
        f"cannot emit (script emits {sorted(tokens)}):\n  " + "\n  ".join(offenders)
    )


def test_every_enumeration_of_the_vocabulary_is_complete():
    tokens = _script_tokens()
    offenders: list[str] = []
    for path in _doc_files():
        text = path.read_text(encoding="utf-8")
        for lineno, block in _paragraphs(text):
            present = {t for t in tokens if t in block}
            if len(present) < 2:
                continue  # a worked example, not an enumeration
            missing = tokens - present
            if missing:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: missing {sorted(missing)}"
                )
    assert not offenders, (
        "Passages enumerate the resolved_via vocabulary but omit tokens that "
        f"scripts/branch-context.sh can emit (script emits {sorted(tokens)}):\n  "
        + "\n  ".join(offenders)
    )
