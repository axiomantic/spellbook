"""Parser for a spellbook implementation plan.

A task block is an H3 heading (`### Task N: Name`), then line-scoped fields
(`Depends:`, `Check:`, `Schema:`), then one block-scoped field (`Files:`, a
bullet list). This is the inverse of nmg2-tools/planlint/document.py, where
`Check:` is the block-scoped field and `Files:` is a single line — the
ARCHITECTURE (one block-scoped field per task) is kept; WHICH field is
block-scoped is swapped, because writing-plans already writes `Files:` as a
multi-line bullet list and `Check:` as one line.

The backtick scanner below is ported unchanged in behavior from
nmg2-tools/planlint/document.py:206-266. A fenced block is a REGION and
yields no inline spans. An inline span never crosses a line break. An
unmatched backtick is literal text and is REPORTED (see rules/structure.py),
not silently absorbed.
"""

import dataclasses
import pathlib
import re

# A task header is an H3 heading. This is what writing-plans already emits:
#     ### Task 4: Rule registry
TASK_HEADER = re.compile(r"^###\s+Task\s+(?P<number>\d+)\s*:\s*(?P<name>.+?)\s*$")

# The canonical identifier of a task. `Task 4`. Used in Depends:, in every
# Finding.task, and as the graph node key.
TASK_IDENT = re.compile(r"^Task\s+(?P<number>\d+)$")

# A reference to a task anywhere in prose or in a Depends: item.
TASK_REF = re.compile(r"\bTask\s+(?P<number>\d+)\b")

# `Task 3 to Task 6` is four idents, not two.
TASK_RANGE = re.compile(r"^Task\s+(?P<low>\d+)\s+to\s+Task\s+(?P<high>\d+)$")

# A field label. writing-plans writes labels in bold; a plain label is
# accepted too, so a hand-written plan is not rejected on markup alone.
FIELD = re.compile(
    r"^\s*(?:\*\*)?(?P<field>Files|Depends|Check|Schema)\s*:(?:\*\*)?\s?(?P<value>.*)$"
)

# A Files: bullet. `- Create: `path``, `- Modify: `path:12-30``,
# `- Test: `path``, optionally followed by `(owner: Task 3)`.
FILES_ENTRY = re.compile(
    r"^\s*[-*]\s+(?P<verb>Create|Modify|Test|Delete)\s*:\s*(?P<rest>.+?)\s*$"
)
OWNER_ANNOTATION = re.compile(r"\(\s*owner\s*:\s*(?P<owner>Task\s+\d+)\s*\)\s*$")

# A path may carry a line range: `path/to/file.py:123-145`.
LINE_RANGE_SUFFIX = re.compile(r":(?P<start>\d+)(?:-(?P<end>\d+))?$")

FENCE = re.compile(r"^\s*```")
HEADING = re.compile(r"^(?P<hashes>#{1,6}) +(?P<text>.+?)\s*$")

# A `**Step N: Title**` line and its `Run:` line.
STEP_HEADER = re.compile(r"^\*\*Step\s+(?P<number>\d+)\s*:\s*(?P<title>.+?)\*\*\s*$")
RUN_LINE = re.compile(r"^Run:\s*(?P<value>.*)$")

SCHEMA_MARKER = "planlint-v1"
SCHEMA_LEGACY = "legacy"

# The FAMILY of values that opt a plan into the linter. Deliberately wider than
# SCHEMA_MARKER: `api.declares_schema` gates on the family, not on one version,
# so a plan declaring `planlint-v2` is admitted and then JUDGED by
# rules/schema.py's `schema-unknown-version` rule. Gating on the exact marker
# instead would send every future version down the "legacy plan" path, where no
# rule runs — which would make the forward-compatibility alarm unreachable and
# hand an unrecognized schema the same silent pass a legacy plan gets.
SCHEMA_FAMILY = re.compile(r"^planlint-[a-z0-9]+$")

NONE_WORDS = frozenset({"none", "nothing", "n/a", "na", "-", "—"})


def strip_markup(text):
    """Remove bold markers and backticks, and collapse whitespace."""
    text = text.replace("**", "")
    text = text.replace("`", "")
    return " ".join(text.split())


# ------------------------------------------------------- the backtick scanner
# Ported from nmg2-tools/planlint/document.py:206-266. See module docstring.


def _pair_fence_markers(markers):
    """Pair one segment's fence-marker line indexes into `(open, close)`
    tuples, plus the one leftover index if the count is odd (`None` if even).

    Markers pair CONSECUTIVELY -- `markers[1]` closes `markers[0]`,
    `markers[3]` closes `markers[2]`, and so on -- except that on an ODD
    count the FIRST marker is set aside as the leftover before consecutive
    pairing runs, rather than the last. This is the deliberate resolution of
    an otherwise irreducible ambiguity: with only bare ``` lines as signal,
    nothing in the text says which single marker among an odd group is "the
    one with no partner" -- pairing consecutively from the front (leftover
    last) and pairing consecutively from the back (leftover first) are
    BOTH valid non-crossing matchings, and no amount of "smarter" greedy
    pairing resolves that in general.

    Leftover-first is chosen because it is what `fenced_line_indexes`'s
    contract requires: "nothing below a broken fence is hidden from any
    lint." A fence marker that opens and is never really closed is a
    document defect near where it sits; a SEPARATE, well-formed fence pair
    that happens to follow it later is unrelated content the defect must not
    swallow. Leftover-last (the naive whole-segment toggle this replaced)
    does the opposite: it lets the broken opener consume the well-formed
    pair's own opening marker as a phantom close, hiding everything between
    them -- including real `Depends:`/`Check:` field text -- and then blames
    the well-formed pair's genuine closing marker as "the" unclosed one.
    Leftover-first keeps the well-formed pair intact and correctly blames
    the marker that is actually alone.

    This does not resolve every possible odd-count arrangement (a
    well-formed pair immediately followed by a later, truly trailing,
    never-closed marker is the mirror case, and is not what this document
    family's fences are expected to look like -- see the module docstring).
    It is chosen because it is the shape the real, reported defect takes.
    """
    if len(markers) % 2:
        leftover, markers = markers[0], markers[1:]
    else:
        leftover = None
    pairs = [(markers[i], markers[i + 1]) for i in range(0, len(markers), 2)]
    return pairs, leftover


def _fence_segments(lines):
    """Group fence-marker line indexes into segments split at `TASK_HEADER`
    lines, and pair each segment's markers via `_pair_fence_markers`.

    A fence is never expected to span a task boundary in this document
    family, so a `### Task N: ...` header always closes out whatever segment
    came before it -- pending pairing is resolved right there, whether or
    not the segment's marker count is even -- rather than letting the
    segment's markers reach across the header looking for a partner.

    Yields `(pairs, leftover)` per segment, in document order.
    """
    markers = []
    for index, line in enumerate(lines):
        if TASK_HEADER.match(line):
            if markers:
                yield _pair_fence_markers(markers)
                markers = []
            continue
        if FENCE.match(line):
            markers.append(index)
    if markers:
        yield _pair_fence_markers(markers)


def unclosed_fence_index(lines):
    """The 0-based index of the first fence marker with no partner, or
    `None` if every fence marker pairs off.

    Reads the document exactly like `fenced_line_indexes`/`_scan_fences`
    (same segmentation, same `_pair_fence_markers` leftover rule), so
    `rules/structure.py` reports the same line those two treat as broken.
    """
    for _pairs, leftover in _fence_segments(lines):
        if leftover is not None:
            return leftover
    return None


def fenced_line_indexes(lines):
    """The index of every line inside a CLOSED fence, both markers included.

    A fence with no partner is absent from the result on purpose. `_scan_fences`
    reads the document the same way, so the two agree, and nothing below a
    broken fence is hidden from any lint.

    Markers are grouped into per-task segments and paired by
    `_fence_segments`/`_pair_fence_markers`: consecutively, except that an
    odd-count segment sets its FIRST marker aside as the unpaired one rather
    than its last. A plain whole-segment open/close TOGGLE that always
    leaves the LAST marker unpaired is not enough -- if an opener is never
    really closed and a SEPARATE, well-formed fence pair follows later IN
    THE SAME TASK BODY (no task header between them), that toggle pairs the
    broken opener with the next fence's OPENING marker instead of
    recognizing the opener as unpaired, which marks everything between them
    (real field text, anything) as "inside a fence" by mistake, and leaves
    the well-formed pair's genuine closing marker dangling as if IT were the
    broken one. See `_pair_fence_markers`'s docstring for why leftover-first
    is the chosen resolution.

    A pending, unclosed open is also abandoned (dropped, not paired with
    anything) the moment a `### Task N: ...` header is seen -- a fence is
    never expected to span a task boundary in this document family, so
    crossing one is exactly the signal that the pending opener was never
    going to be genuinely closed.
    """
    inside = set()
    for pairs, _leftover in _fence_segments(lines):
        for open_at, close_at in pairs:
            inside.update(range(open_at, close_at + 1))
    return inside


def _scan_line(line, offset, spans, unmatched):
    """Pair the backticks of ONE line. Whatever is left over is literal."""
    ticks = [index for index, char in enumerate(line) if char == "`"]
    position = 0
    while position + 1 < len(ticks):
        opener, closer = ticks[position], ticks[position + 1]
        if closer == opener + 1:
            unmatched.append(offset + opener)
            position += 1
            continue
        spans.append((offset + opener, offset + closer, line[opener + 1:closer]))
        position += 2
    for leftover in ticks[position:]:
        unmatched.append(offset + leftover)


def inline_code_spans(text):
    """`(spans, unmatched)` for a run of text.

    A span is `(opening tick offset, closing tick offset, the text between)`.
    `unmatched` carries the offset of every backtick with no partner on its own
    line, which is what `rules/structure.py` reports rather than absorbing.
    """
    lines = text.split("\n")
    fenced = fenced_line_indexes(lines)
    spans = []
    unmatched = []
    offset = 0
    for index, line in enumerate(lines):
        if index not in fenced:
            _scan_line(line, offset, spans, unmatched)
        offset += len(line) + 1
    return spans, unmatched


def backticked(text):
    """Every inline backticked name, in order. The fence-aware `findall`."""
    return [inner for _, _, inner in inline_code_spans(text)[0]]


# ------------------------------------------------------------------ dataclasses


@dataclasses.dataclass(frozen=True)
class FilesEntry:
    """One bullet of the block-scoped `Files:` field."""

    verb: str
    path: str
    raw: str
    line_start: int = 0
    line_end: int = 0
    owner: str = ""
    line: int = 0


@dataclasses.dataclass(frozen=True)
class Step:
    """One `**Step N: Title**` block inside a task body."""

    number: int
    title: str
    line: int
    body_text: str
    run_command: str = ""
    run_line: int = 0


@dataclasses.dataclass
class TaskBlock:
    ident: str
    number: int
    name: str
    line: int
    section: str
    header_text: str = ""
    body_text: str = ""

    files_text: str = ""
    files_line: int = 0        # 1-based line of the `**Files:**` LABEL
    files_block_line: int = 0  # 1-based line of the FIRST line of the bullet block

    depends_text: str = ""
    depends_line: int = 0
    check_text: str = ""
    check_line: int = 0
    schema_text: str = ""
    schema_line: int = 0

    steps: tuple = ()

    @property
    def files_entries(self):
        """One FilesEntry per bullet, each carrying ITS OWN document line.

        `FilesEntry.line` must point at the bullet, not at the `**Files:**`
        label. Three rules report at it — `modify-path-missing`,
        `create-path-exists`, `shared-path-without-owner` — and all three name
        a specific path, so a reader who follows the reported line to the label
        finds a line that does not mention the path the finding is about. On a
        task with six bullets, every one of those findings would point at the
        same wrong line.

        The offset arithmetic below is only correct because `_fill_fields`
        keeps the block CONTIGUOUS (blank lines inside it are preserved in
        `files_text` rather than dropped). An earlier draft skipped blanks
        while collecting and then indexed as though it had not, which made the
        error grow by one for every blank line above the bullet.
        """
        entries = []
        for line_offset, raw_line in enumerate(self.files_text.split("\n")):
            match = FILES_ENTRY.match(raw_line)
            if not match:
                continue
            rest = match.group("rest")
            owner_match = OWNER_ANNOTATION.search(rest)
            owner = owner_match.group("owner") if owner_match else ""
            if owner_match:
                rest = rest[: owner_match.start()].strip()
            names = backticked(rest)
            if not names:
                continue
            raw = names[0]
            path = raw
            line_start = line_end = 0
            range_match = LINE_RANGE_SUFFIX.search(raw)
            if range_match:
                path = raw[: range_match.start()]
                line_start = int(range_match.group("start"))
                line_end = int(range_match.group("end") or line_start)
            entries.append(
                FilesEntry(
                    verb=match.group("verb"),
                    path=path,
                    raw=raw,
                    line_start=line_start,
                    line_end=line_end,
                    owner=owner,
                    line=self.files_block_line + line_offset,
                )
            )
        return tuple(entries)

    @property
    def check_command(self):
        spans, unmatched = inline_code_spans(self.check_text)
        if len(spans) != 1 or unmatched:
            return ""
        start, end, inner = spans[0]
        stripped = self.check_text.strip()
        if self.check_text[start:end + 1] != stripped:
            return ""
        return inner

    @property
    def declared_dependencies(self):
        from spellbook.planlint import graph  # local import: avoids a cycle,
        # since graph.py imports TASK_IDENT/TASK_REF/TASK_RANGE from this
        # module. See registry.py Task 4 for why the cycle would otherwise
        # exist: document -> graph -> document.

        edges, _ = graph.parse_depends(self.depends_text, graph.DEPENDS)
        return tuple(edges)


class PlanDocument:
    """A spellbook implementation plan, parsed."""

    def __init__(self, lines, name):
        self.name = name
        self.lines = lines
        self.tasks = []
        self._by_ident = {}
        self._fences = []
        self._headings = []
        self.schema_text = ""
        self.schema_line = 0
        self._parse()

    @classmethod
    def from_text(cls, text, name="<text>"):
        return cls(text.splitlines(), name)

    @classmethod
    def from_path(cls, path):
        path = pathlib.Path(path)
        return cls(path.read_text(encoding="utf-8").splitlines(), str(path))

    def task(self, ident):
        return self._by_ident.get(ident)

    def has_task(self, ident):
        return ident in self._by_ident

    @property
    def idents(self):
        return frozenset(self._by_ident)

    @property
    def declares_planlint_schema(self):
        """True when this plan declares THIS version. Reads `schema_text` ONLY.

        NOT the call-site gate, and not a synonym for one. `api.declares_schema`
        admits the whole `planlint-*` FAMILY so that an unrecognized version is
        linted and reported by `rules/schema.py` rather than silently skipped;
        this property answers the narrower question "is this exactly the version
        the current rule pack was written for?". Do not use it to decide whether
        to run the linter — that decision belongs to `api.declares_schema` alone,
        and `test_planlint_schema_census.py` records which functions make it.
        """
        return self.schema_text == SCHEMA_MARKER

    def section_at_line(self, line):
        """The nearest enclosing heading text at 1-based document `line`,
        markup stripped; `""` before the first heading.

        This is the PUBLIC accessor for heading context. Rules that need the
        section for a document line (rules/structure.py's `unclosed-fence`,
        which reports a line that belongs to no task block) call this rather
        than reaching into `_headings`, which is private and whose tuple shape
        is not part of any contract.
        """
        return self._section_at(line - 1)

    # ----------------------------------------------------------------- parse

    def _parse(self):
        self._scan_fences()
        self._scan_headings()
        self._scan_tasks()
        for task in self.tasks:
            self._scan_steps(task)
        self._resolve_plan_schema()

    def _scan_fences(self):
        """See `fenced_line_indexes`'s and `_pair_fence_markers`'s
        docstrings for why a plain whole-segment toggle is not enough: a
        pending, unclosed open must not be able to steal a later, unrelated
        fence's opening marker as its own phantom close, whether that later
        fence sits across a task header or later in the SAME task body."""
        for pairs, _leftover in _fence_segments(self.lines):
            for open_at, close_at in pairs:
                self._fences.append({"start": open_at, "end": close_at})

    def _in_fence(self, index):
        for fence in self._fences:
            if fence["start"] <= index <= fence["end"]:
                return fence
        return None

    def _scan_headings(self):
        for index, line in enumerate(self.lines):
            if self._in_fence(index):
                continue
            match = HEADING.match(line)
            if match:
                self._headings.append((index, match.group("text")))

    def _section_at(self, index):
        found = ""
        for line_index, text in self._headings:
            if line_index <= index:
                found = strip_markup(text)
            else:
                break
        return found

    def _scan_tasks(self):
        starts = []
        for index, line in enumerate(self.lines):
            if self._in_fence(index):
                continue
            match = TASK_HEADER.match(line)
            if match:
                starts.append((index, match))

        for position, (index, match) in enumerate(starts):
            end = starts[position + 1][0] if position + 1 < len(starts) else len(self.lines)
            for heading_index, _ in self._headings:
                if index < heading_index < end:
                    end = heading_index
                    break
            task = TaskBlock(
                ident=f"Task {match.group('number')}",
                number=int(match.group("number")),
                name=match.group("name").strip(),
                header_text=self.lines[index].strip(),
                line=index + 1,
                section=self._section_at(index),
                body_text="\n".join(self.lines[index:end]),
            )
            self._fill_fields(task, index, end)
            self.tasks.append(task)
            self._by_ident[task.ident] = task

    def _fill_fields(self, task, start, end):
        """Line-scoped fields take the rest of their own line. `Files:` opens
        a BLOCK that runs until the first line that is neither blank nor a
        FILES_ENTRY bullet."""
        index = start
        while index < end:
            if self._in_fence(index):
                index += 1
                continue
            match = FIELD.match(self.lines[index])
            if not match:
                index += 1
                continue
            field = match.group("field")
            value = match.group("value").strip()
            if field == "Files":
                task.files_line = index + 1
                # The Files: label line itself never carries a bullet; the
                # block begins on the NEXT line.
                task.files_block_line = index + 2
                # A blank line inside the block is KEPT, not skipped. `block`
                # is indexed positionally by `files_entries` to recover each
                # bullet's document line, so it has to stay contiguous with the
                # source; dropping blanks here would shift every bullet below
                # one of them. A kept blank line never matches FILES_ENTRY, so
                # it costs one skipped iteration and nothing else.
                block = []
                cursor = index + 1
                while cursor < end:
                    line = self.lines[cursor]
                    if not line.strip():
                        block.append(line)
                        cursor += 1
                        continue
                    if FILES_ENTRY.match(line):
                        block.append(line)
                        cursor += 1
                        continue
                    break
                task.files_text = "\n".join(block)
                index = cursor
                continue
            elif field == "Depends":
                task.depends_text = value
                task.depends_line = index + 1
            elif field == "Check":
                task.check_text = value
                task.check_line = index + 1
            elif field == "Schema":
                task.schema_text = value
                task.schema_line = index + 1
            index += 1

    def _scan_steps(self, task):
        steps = []
        lines = task.body_text.split("\n")
        starts = []
        for offset, line in enumerate(lines):
            match = STEP_HEADER.match(line.strip())
            if match:
                starts.append((offset, match))
        for position, (offset, match) in enumerate(starts):
            end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
            body = lines[offset:end]
            run_command = ""
            run_line = 0
            for body_offset, body_line in enumerate(body):
                run_match = RUN_LINE.match(body_line.strip())
                if run_match:
                    run_line = task.line + offset + body_offset
                    value = run_match.group("value")
                    spans, unmatched = inline_code_spans(value)
                    if len(spans) == 1 and not unmatched:
                        start, end, inner = spans[0]
                        if value[start:end + 1] == value.strip():
                            run_command = inner
                    break
            steps.append(
                Step(
                    number=int(match.group("number")),
                    title=match.group("title").strip(),
                    line=task.line + offset,
                    body_text="\n".join(body),
                    run_command=run_command,
                    run_line=run_line,
                )
            )
        task.steps = tuple(steps)

    def _resolve_plan_schema(self):
        """The plan-level `Schema:` if present before the first task header,
        else the first task with a non-empty `Schema:` value. See design
        §3.1.2's judgment call: either reading opts a plan in."""
        first_task_line = self.tasks[0].line - 1 if self.tasks else len(self.lines)
        for index in range(first_task_line):
            if self._in_fence(index):
                continue
            match = FIELD.match(self.lines[index])
            if match and match.group("field") == "Schema":
                self.schema_text = match.group("value").strip()
                self.schema_line = index + 1
                return
        for task in self.tasks:
            if task.schema_text:
                self.schema_text = task.schema_text
                self.schema_line = task.schema_line
                return
