"""Tests for ``fence_for`` in scripts/generate_docs.py.

Every generated docs page wraps a raw source body in a fenced block so that
XML-style tags (``<CRITICAL>``, ``<RULE>``) are shown rather than swallowed as
HTML. CommonMark requires that wrapper to be strictly LONGER than the longest
fence inside it, so the width is a property of the body.

The invariant worth guarding is one-directional. A fence that is too LONG is
merely noisy -- that is what the old hardcoded ten backticks was. A fence that
is too SHORT silently truncates the page at the first inner fence, and the
generator writes 200+ files in one pass, so an off-by-one here corrupts the
docs site wholesale rather than visibly failing.
"""

from pathlib import Path

import pytest
from generate_docs import fence_for


def longest_run(text: str) -> int:
    """Longest backtick run that starts a line, mirroring the CommonMark rule."""
    best = 0
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if len(line) - len(stripped) <= 3 and stripped.startswith("```"):
            run = len(stripped) - len(stripped.lstrip("`"))
            best = max(best, run)
    return best


# ---- the floor -----------------------------------------------------------


def test_body_with_no_fences_gets_the_minimum():
    """agents/MODEL_ROUTING.md is exactly this case, and it was the one that
    made the hardcoded ten backticks visibly absurd."""
    assert fence_for("# Title\n\nJust prose.\n") == "```"


def test_empty_body_gets_the_minimum():
    assert fence_for("") == "```"


def test_inline_code_spans_do_not_raise_the_fence():
    """Backticks inside a line are code spans, not fences."""
    assert fence_for("Use `config_get` and ``x`` here.\n") == "```"


# ---- escalation ----------------------------------------------------------


@pytest.mark.parametrize(
    "inner,expected",
    [(3, 4), (4, 5), (5, 6), (10, 11)],
)
def test_fence_is_one_longer_than_the_longest_inner_run(inner, expected):
    body = f"before\n{'`' * inner}python\ncode\n{'`' * inner}\nafter\n"
    assert fence_for(body) == "`" * expected


def test_longest_run_wins_not_the_last_one():
    body = "`````a\nx\n`````\n\n```b\ny\n```\n"
    assert fence_for(body) == "``````"


def test_indented_fence_up_to_three_spaces_counts():
    """CommonMark treats up to three leading spaces as still a fence."""
    assert fence_for("   ````x\ny\n   ````\n") == "`````"


# ---- the invariant -------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "",
        "no fences at all\n",
        "```\nplain\n```\n",
        "````\nnested\n````\n",
        "```mermaid\ngraph TD\n```\n\n`````\nouter\n`````\n",
        "   ```\nindented\n   ```\n",
        "text with ``inline`` spans\n",
    ],
)
def test_result_always_exceeds_the_longest_inner_run(body):
    """The one-directional guarantee: never too short, whatever the body."""
    assert len(fence_for(body)) > longest_run(body)


@pytest.mark.parametrize(
    "body",
    ["", "prose\n", "```\nx\n```\n", "`````\nx\n`````\n"],
)
def test_result_is_never_shorter_than_three(body):
    assert len(fence_for(body)) >= 3


def test_result_is_only_backticks():
    assert set(fence_for("```\nx\n```\n")) == {"`"}


# ---- the real corpus -----------------------------------------------------


def test_every_shipped_source_body_round_trips():
    """Run the real inputs the generator sees. A body whose computed fence is
    not longer than its own longest run would truncate that page on write."""
    repo = Path(__file__).resolve().parents[2]
    sources = [
        *(repo / "rules").glob("*.md"),
        *(repo / "agents").glob("*.md"),
        *(repo / "commands").glob("*.md"),
    ]
    assert sources, "no source files found; the glob is wrong"

    for path in sources:
        body = path.read_text(encoding="utf-8")
        assert len(fence_for(body)) > longest_run(body), path
