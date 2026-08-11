"""Structure hygiene — unmatched-backtick, unclosed-fence.

Both ERROR. A document a lint cannot read correctly is not a document that
passed. See design §4.1 for the defect this module exists to catch (source
defect L-5: a whole-body backtick-pairing regex inverted every pairing after
the first fence, and the warning count fell while text was added).
"""

from spellbook.planlint.document import FENCE, TASK_HEADER, inline_code_spans
from spellbook.planlint.finding import ERROR, Finding, guard_no_input

EMITS = frozenset({"unmatched-backtick", "unclosed-fence"})


def _line_at(text, offset):
    return text.count("\n", 0, offset) + 1


def unmatched_backticks(task):
    """`{line number in the document: count}` for one task body."""
    _, unmatched = inline_code_spans(task.body_text)
    out = {}
    for offset in unmatched:
        line = task.line + _line_at(task.body_text, offset) - 1
        out[line] = out.get(line, 0) + 1
    return out


def unclosed_fence_line(doc):
    """The 1-based line of a fence with no partner, or 0.

    Must agree with `document._scan_fences`/`fenced_line_indexes`: a pending,
    unclosed open is abandoned the moment a task header is seen, rather than
    being paired with whatever fence marker happens to come next. Without
    this, a genuinely broken fence followed later by a separate, well-formed
    pair would report the well-formed pair's CLOSING marker as unclosed
    instead of the real defect -- the exact real bug reported.
    """
    open_at = 0
    for index, line in enumerate(doc.lines):
        if open_at and TASK_HEADER.match(line):
            return open_at
        if FENCE.match(line):
            open_at = 0 if open_at else index + 1
    return open_at


def run(ctx):
    doc = ctx.doc
    findings = []

    for task in doc.tasks:
        counts = unmatched_backticks(task)
        body = task.body_text.split("\n")
        for line in sorted(counts):
            count = counts[line]
            written = body[line - task.line]
            findings.append(
                Finding(
                    rule="unmatched-backtick",
                    message=(
                        "a task body carries a backtick with no partner on its own "
                        "line; a reader and the linter read two different documents"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=line,
                    evidence=(
                        f"line {line} carries {count} backtick"
                        f"{'' if count == 1 else 's'} with no partner: `{written}`"
                    ),
                    severity=ERROR,
                )
            )

    opened = unclosed_fence_line(doc)
    if opened:
        findings.append(
            Finding(
                rule="unclosed-fence",
                message=(
                    "a fenced block is opened and never closed; every fenced-block "
                    "boundary below this line is the wrong one"
                ),
                section=doc.section_at_line(opened),
                line=opened,
                evidence=(
                    f"line {opened} opens a fenced block and no line below it closes it"
                ),
                severity=ERROR,
            )
        )

    return guard_no_input(
        "structure", findings, len(doc.tasks), "task bodies", "structure lint"
    )
