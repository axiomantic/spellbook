"""Every documented invocation of the gate-ledger CLI must be accepted by it.

The recurring defect this guards: an artifact changes and a consumer
elsewhere does not follow -- here, argparse gains or keeps a requirement
that the prose documenting the command does not satisfy. A review round
cannot durably catch that; this test can, because it EXECUTES every
invocation the documentation prints.

Two failure kinds must be told apart, and the difference is the whole
design of the check:

* ARGPARSE REJECTION -- the CLI refuses to parse the documented command
  line at all (missing required flag, invalid choice, unrecognized
  argument). That is the drift this test exists to catch, and it always
  prints a ``usage:`` block to stderr because argparse's error path does.
* SEMANTIC REFUSAL -- the CLI parses the command and then declines for a
  correct reason (``--status failed`` with no ``--open-findings``,
  closing a blocker that was never opened). That is the CLI working as
  designed on a synthetic argument set, so it must NOT fail this test.
  These print ``error: ...`` with no ``usage:`` block.

Nothing is skipped silently. A documented invocation whose placeholders
this module cannot resolve fails the test with the offending text, so an
extraction gap surfaces as red rather than as a shrinking sample.
"""

import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_REL = "scripts/develop_gate_ledger.py"
CLI_PATH = REPO_ROOT / CLI_REL

# docs/ is a generated mirror of these sources; scanning it would only
# re-test the same strings. Freshness of that mirror is a separate check.
SCAN_DIRS = ("commands", "skills", "rules", "agents")

# The documented invocations are illustrative, so they carry placeholders.
# Substituting realistic values keeps the hard cases IN the sample; a check
# that skipped every line with a placeholder would test almost nothing.
PLACEHOLDER_VALUES = {
    "<id>": "B1",
    "<ids>": "F1",
    "<wave_id>": "3a",
    "<group_id>": "G1",
    "<field>": "current_phase",
    "<value>": "4",
    "<text>": "documented invocation smoke test",
    "<why>": "documented invocation smoke test",
    "<reason>": "documented invocation smoke test",
    "<path>": "ledger.json",
    # A real DISPATCH_SKILLS member. The `dispatches` query exits 1 when
    # nothing matches, which this harness accepts -- it discriminates argparse
    # drift (a "usage:" block) from a semantic no-match, and a fresh temp
    # ledger legitimately has no dispatches recorded.
    "<skill>": "dehallucination",
}

# Uppercase metavars used as flag values in prose (e.g. `[--timestamp ISO]`).
METAVAR_VALUES = {
    "ISO": "2026-08-17T00:00:00+00:00",
}

# A bare `...` stands for "a value of the right shape"; the right shape
# depends on which flag it follows.
ELLIPSIS_VALUES = {
    "--gates": "4.4,4.5",
    "--open-findings": "F1,F2",
    "--open-rows": "W3a-2,W3a-5",
}

FENCED_BLOCK = re.compile(r"^[ \t]*(`{3,})[^\n]*\n(.*?)^[ \t]*\1", re.DOTALL | re.MULTILINE)
INLINE_SPAN = re.compile(r"(?<!`)`([^`]+)`(?!`)", re.DOTALL)


class ExtractionError(Exception):
    """A documented invocation could not be turned into a command line."""


def _markdown_files() -> list[Path]:
    files = []
    for rel in SCAN_DIRS:
        files.extend(sorted((REPO_ROOT / rel).rglob("*.md")))
    return files


def _candidate_snippets(text: str) -> list[str]:
    """Return code snippets that mention the CLI, one per logical command."""
    snippets = []

    fenced_spans = []
    for match in FENCED_BLOCK.finditer(text):
        fenced_spans.append(match.span())
        block = match.group(2)
        # Shell line continuations make one command out of several lines.
        block = re.sub(r"\\\n\s*", " ", block)
        for line in block.splitlines():
            if CLI_REL in line or "develop_gate_ledger.py" in line:
                snippets.append(line)

    for match in INLINE_SPAN.finditer(text):
        if any(start <= match.start() < end for start, end in fenced_spans):
            continue
        span = match.group(1)
        if "develop_gate_ledger.py" in span:
            snippets.append(" ".join(span.split()))

    return snippets


def _to_argv(snippet: str) -> list[str] | None:
    """Turn a documented snippet into concrete CLI arguments.

    Returns None for a bare reference to the script path (prose naming the
    file, not invoking it). Raises ExtractionError for anything else this
    module cannot resolve -- never a silent skip.
    """
    snippet = snippet.strip().strip("`").rstrip(".;,")
    try:
        tokens = shlex.split(snippet)
    except ValueError as exc:
        raise ExtractionError(f"cannot tokenize: {snippet!r} ({exc})") from exc

    script_index = None
    for index, token in enumerate(tokens):
        if token.strip("[]").endswith("develop_gate_ledger.py"):
            script_index = index
            break
    if script_index is None:
        raise ExtractionError(f"no script token found in: {snippet!r}")

    args = [token.strip("[]") for token in tokens[script_index + 1:]]
    args = [token for token in args if token]
    if not args:
        # Prose naming the file, e.g. "implemented in `scripts/....py`".
        return None

    resolved: list[str] = []
    previous_flag: str | None = None
    for token in args:
        if token == "...":
            if previous_flag is None or previous_flag not in ELLIPSIS_VALUES:
                raise ExtractionError(
                    f"'...' after {previous_flag!r} has no realistic value mapped: {snippet!r}"
                )
            resolved.append(ELLIPSIS_VALUES[previous_flag])
            previous_flag = None
            continue

        if token.startswith("<") and token.endswith(">"):
            if token not in PLACEHOLDER_VALUES:
                raise ExtractionError(f"unmapped placeholder {token!r} in: {snippet!r}")
            resolved.append(PLACEHOLDER_VALUES[token])
            previous_flag = None
            continue

        alternation = token.strip("{}")
        if "|" in alternation:
            resolved.append(alternation.split("|")[0])
            previous_flag = None
            continue

        if token.startswith("--"):
            if "=" in token:
                raise ExtractionError(f"'--flag=value' form is unhandled: {snippet!r}")
            resolved.append(token)
            previous_flag = token
            continue

        if previous_flag is not None and token.isupper():
            if token not in METAVAR_VALUES:
                raise ExtractionError(f"unmapped metavar {token!r} in: {snippet!r}")
            resolved.append(METAVAR_VALUES[token])
            previous_flag = None
            continue

        if re.fullmatch(r"[<>{}\[\]]+", token):
            raise ExtractionError(f"unparsed placeholder syntax {token!r} in: {snippet!r}")

        resolved.append(token)
        previous_flag = None

    return resolved


def _documented_invocations() -> list[tuple[str, str, list[str]]]:
    found = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        if "develop_gate_ledger.py" not in text:
            continue
        for snippet in _candidate_snippets(text):
            argv = _to_argv(snippet)
            if argv is None:
                continue
            found.append((str(path.relative_to(REPO_ROOT)), snippet, argv))
    return found


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    """Run one invocation against a throwaway ledger directory.

    SPELLBOOK_DEV_DIR is always set to a fresh temp directory, so no run
    can reach the developer's real ~/.local/spellbook state, and no run
    can see state left by a sibling invocation.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, SPELLBOOK_DEV_DIR=tmp)
        return subprocess.run(
            [sys.executable, str(CLI_PATH), *argv],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
            timeout=60,
        )


def test_extraction_finds_the_documented_invocations():
    """Guard the sample size: an empty scan would otherwise pass green."""
    invocations = _documented_invocations()
    assert len(invocations) >= 8, (
        "extraction found only "
        f"{len(invocations)} documented invocations of {CLI_REL}; the scan or the "
        "snippet patterns have regressed"
    )


@pytest.mark.parametrize(
    ("source", "snippet", "argv"),
    [pytest.param(*item, id=f"{item[0]}::{item[2][0]}") for item in _documented_invocations()],
)
def test_documented_invocation_is_accepted_by_the_cli(source, snippet, argv):
    result = _run(argv)
    if result.returncode == 0:
        return

    # argparse always prints a usage block when it rejects a command line;
    # the CLI's own semantic refusals print only "error: ...". That is the
    # discriminator between drift (a bug) and a correct refusal of the
    # synthetic argument values this test supplies.
    combined = result.stdout + result.stderr
    assert "usage:" not in combined, (
        f"{source} documents an invocation the CLI's argparse rejects.\n"
        f"  documented: {snippet}\n"
        f"  ran:        {' '.join(shlex.quote(a) for a in argv)}\n"
        f"  exit:       {result.returncode}\n"
        f"  stderr:     {result.stderr.strip()}"
    )
