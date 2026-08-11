"""Non-empty and runnable `Check:` — four rule IDs, four distinct fixes.

check-empty, check-not-a-command, check-placeholder: ERROR (fully decidable).
check-not-runnable: WARNING (a heuristic; a heuristic that blocks gets
disabled, one that warns gets read — design §4.4).

The linter never EXECUTES a `Check:` command. Running an arbitrary command
out of a document during a lint is a code-execution surface. "Is this
command runnable" is answered structurally only.
"""

import re

from spellbook.planlint.document import NONE_WORDS
from spellbook.planlint.finding import ERROR, WARNING, Finding, guard_no_input

EMITS = frozenset(
    {"check-empty", "check-not-a-command", "check-placeholder", "check-not-runnable"}
)

PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"<[^>]+>"),
    re.compile(r"\[[^\]]+\]"),
    re.compile(r"(?<!\.)\.\.\.(?!\.)"),
    re.compile(r"\bpath/to/"),
    re.compile(r"\bexact/path/"),
    re.compile(r"\btest_name\b"),
)

LEADING_RUNNER = re.compile(r"^(?:uv run|npx|poetry run|pnpm|make)\s+")
LEADING_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S+\s+")

PROSE_OPENERS = frozenset(
    {
        "the", "a", "an", "it", "this", "that", "should", "ensure", "confirm",
        "manually", "visually", "check", "look", "open", "see",
    }
)


def run(ctx):
    doc = ctx.doc
    findings = []

    for task in doc.tasks:
        # Inlined deliberately. This was a `_strip_check_markup(task)` helper
        # whose entire body was `task.check_text.strip()` — a name promising
        # markup removal over code that removes only whitespace. A reader
        # trusting the name would assume backticks and bold markers were
        # already gone, which is the opposite of true: the backticks are what
        # `task.check_command` reads to decide the value is one code span, and
        # stripping them here would break that. No helper, no false promise.
        raw = task.check_text.strip()
        if not raw or raw.lower().rstrip(".") in NONE_WORDS:
            findings.append(
                Finding(
                    rule="check-empty",
                    message=(
                        "the `Check:` field is absent or empty; a task with no "
                        "proving command has no definition of done"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.check_line or task.line,
                    severity=ERROR,
                )
            )
            continue

        command = task.check_command
        if not command:
            findings.append(
                Finding(
                    rule="check-not-a-command",
                    message=(
                        "the `Check:` value is not EXACTLY one inline code span "
                        "covering the whole value"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.check_line or task.line,
                    evidence=f"Check: {raw}",
                    severity=ERROR,
                )
            )
            continue

        if any(p.search(command) for p in PLACEHOLDER_PATTERNS):
            findings.append(
                Finding(
                    rule="check-placeholder",
                    message=(
                        "the `Check:` command still carries template placeholder "
                        "text, so the task has no command that can prove its work"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.check_line or task.line,
                    evidence=f"Check: `{command}`",
                    severity=ERROR,
                )
            )
            continue

        stripped = LEADING_ASSIGNMENT.sub("", command).strip()
        stripped = LEADING_RUNNER.sub("", stripped).strip()
        first_token = stripped.split(" ", 1)[0].lower() if stripped else ""
        if first_token in PROSE_OPENERS:
            findings.append(
                Finding(
                    rule="check-not-runnable",
                    message=(
                        "the `Check:` command opens with a word from a closed "
                        "prose-opener list and is likely a description, not a "
                        "runnable command"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=task.check_line or task.line,
                    evidence=f"Check: `{command}`",
                    severity=WARNING,
                )
            )

    return guard_no_input(
        "checks", findings, len(doc.tasks), "task blocks", "checks lint"
    )
