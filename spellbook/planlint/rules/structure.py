"""Structure hygiene — unmatched-backtick, unclosed-fence.

Both ERROR. A document a lint cannot read correctly is not a document that
passed. See design §4.1 for the defect this module exists to catch (source
defect L-5: a whole-body backtick-pairing regex inverted every pairing after
the first fence, and the warning count fell while text was added).
"""

from spellbook.planlint.document import inline_code_spans, unclosed_fence_index
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
    """`(line, ambiguous_lines)` for the first segment with an odd fence-
    marker count, or `(0, None)` if every segment pairs off evenly.

    Delegates to `document.unclosed_fence_index`. `line` is 1-based and
    always set when a defect exists -- it is where the finding attaches.
    `ambiguous_lines` is `None` for the trivial single-marker case (that
    ONE line unambiguously IS the unclosed fence); for a segment with 3+
    markers it is the 1-based line of every marker in that segment, because
    with only marker positions as signal, which single one is "the" broken
    marker is not knowable -- see `document._pair_fence_markers`'s
    docstring. `run()` uses the distinction to decide whether it may accuse
    one line or must report the ambiguity itself.
    """
    info = unclosed_fence_index(doc.lines)
    if info is None:
        return 0, None
    ambiguous_lines = (
        tuple(index + 1 for index in info.markers)
        if info.markers is not None
        else None
    )
    return info.anchor + 1, ambiguous_lines


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

    opened, ambiguous_lines = unclosed_fence_line(doc)
    if opened and ambiguous_lines is None:
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
    elif opened:
        lines_text = ", ".join(str(line) for line in ambiguous_lines)
        findings.append(
            Finding(
                rule="unclosed-fence",
                message=(
                    "a section has an odd, ambiguous number of fence markers; "
                    "marker position alone cannot say which one is unclosed, so "
                    "none of them are treated as a matched pair"
                ),
                section=doc.section_at_line(opened),
                line=opened,
                evidence=(
                    f"{len(ambiguous_lines)} fence markers in this section "
                    f"(lines {lines_text}); cannot determine which is unclosed"
                ),
                severity=ERROR,
            )
        )

    return guard_no_input(
        "structure", findings, len(doc.tasks), "task bodies", "structure lint"
    )
