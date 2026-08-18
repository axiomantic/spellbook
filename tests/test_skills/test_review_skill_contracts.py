"""Static contract guards for the three review skills and their phase commands.

These skills are prose consumed by a model, so their invariants have no compiler
and no runtime. Every regression they have suffered was the same shape: a rule
stated in one document and silently contradicted in a sibling. A hardcoded
``origin/main`` reappears in one command; a ``SEVERITY_ORDER`` dict loses a key
in one of the two places it is written; one skill's severity vocabulary is
migrated and its sibling is not; a trigger phrase is added to two skills at once
so routing becomes ambiguous.

Each guard below is a cheap static assertion over the document text. They are
deliberately mechanical: a contract that is only stated in prose is a contract
that drifts.

No mocking is involved -- these read the real repository files.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

CODE_REVIEW_SKILL = REPO_ROOT / "skills" / "code-review" / "SKILL.md"
ADVANCED_SKILL = REPO_ROOT / "skills" / "advanced-code-review" / "SKILL.md"
DISTILLING_SKILL = REPO_ROOT / "skills" / "distilling-prs" / "SKILL.md"
REPORT_COMMAND = REPO_ROOT / "commands" / "advanced-code-review-report.md"
GIVE_COMMAND = REPO_ROOT / "commands" / "code-review-give.md"

# The review-vocabulary pattern files. `code-review-taxonomy.md` calls itself
# "the authoritative reference for all code review classification" and
# `agents/code-reviewer.md` points agents at it -- yet it sat OUTSIDE this guard
# set through the severity migration and kept prescribing Title-Case `Critical`
# and "bugs are Critical" long after the canon said otherwise.
REVIEW_PATTERN_FILES = (
    REPO_ROOT / "patterns" / "code-review-taxonomy.md",
    REPO_ROOT / "patterns" / "code-review-antipatterns.md",
    REPO_ROOT / "patterns" / "code-review-formats.md",
    REPO_ROOT / "patterns" / "agent-schema.md",
)

REVIEW_SKILLS = (CODE_REVIEW_SKILL, ADVANCED_SKILL, DISTILLING_SKILL)

# Every file `_guarded_files()` must return, pinned BY NAME. A `>= 5` floor over
# a globbed set is not a guard: renaming three command files silently shrank the
# parametrised suite from 20 tests to 17 and stayed green. Renaming a file must
# now break this list loudly.
EXPECTED_GUARDED_FILES = (
    "commands/advanced-code-review-context.md",
    "commands/advanced-code-review-plan.md",
    "commands/advanced-code-review-report.md",
    "commands/advanced-code-review-review.md",
    "commands/advanced-code-review-verify.md",
    "commands/code-review-audit.md",
    "commands/code-review-give.md",
    "patterns/agent-schema.md",
    "patterns/code-review-antipatterns.md",
    "patterns/code-review-formats.md",
    "patterns/code-review-taxonomy.md",
    "skills/advanced-code-review/SKILL.md",
    "skills/code-review/SKILL.md",
)


def _guarded_files() -> list[Path]:
    """Every document whose base must be DETECTED rather than written down."""
    files: list[Path] = []
    for skill_dir in (REPO_ROOT / "skills" / "code-review", REPO_ROOT / "skills" / "advanced-code-review"):
        files.extend(sorted(skill_dir.rglob("*.md")))
    files.extend(sorted((REPO_ROOT / "commands").glob("advanced-code-review-*.md")))
    files.extend(sorted((REPO_ROOT / "commands").glob("code-review-audit.md")))
    files.append(GIVE_COMMAND)
    files.extend(REVIEW_PATTERN_FILES)
    return files


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


# ---------------------------------------------------------------------------
# (a) No hardcoded base literal
# ---------------------------------------------------------------------------

# `origin/main` or `origin/master` as a ref, and `base = "main"` style
# assignments. Both are ways of writing down an answer that `branch-context.sh`
# is supposed to DETECT and report the provenance of.
BASE_LITERAL_PATTERNS = (
    re.compile(r"origin/(main|master)\b"),
    re.compile(r"""base\s*=\s*["'](main|master)["']"""),
    # A BARE ref in a diff/merge-base position. `git diff main...HEAD` is the
    # exact hazard the docstring above describes, and the `origin/` prefix is
    # not what makes it wrong -- writing the answer down is. The optional
    # `<remote>/` group catches `upstream/main` and any other remote too.
    re.compile(r"""\bgit\s+diff\s+(?:-{1,2}\S+\s+)*(?:[\w.-]+/)?(main|master)\b"""),
    re.compile(r"""\bmerge-base\s+(?:-{1,2}\S+\s+)*(?:[\w.-]+/)?(main|master)\b"""),
)


def test_guarded_file_set_is_exactly_the_expected_documents():
    """The guarded set is pinned BY NAME, not by a floor.

    ``len(files) >= 5`` passed while three of the eight members silently
    disappeared: the parametrised guards below simply generated fewer cases and
    the suite stayed green. Every member is named here, so a rename, a move or a
    deletion fails THIS test instead of quietly shrinking the coverage.
    """
    files = _guarded_files()
    assert sorted(_rel(p) for p in files) == sorted(EXPECTED_GUARDED_FILES), (
        "the guarded document set drifted; update EXPECTED_GUARDED_FILES "
        "deliberately if a document was genuinely renamed"
    )
    for path in files:
        assert path.is_file(), f"{_rel(path)} is guarded but does not exist"


@pytest.mark.parametrize("path", _guarded_files(), ids=_rel)
def test_no_hardcoded_base_literal(path: Path):
    """The merge target is DETECTED by branch-context.sh, never written down.

    A literal `origin/main` silently reviews the wrong range on any repo whose
    default branch is `master`, on any stacked branch, and on any fork whose
    parent is `upstream`. The script exists to resolve this and to REPORT how it
    resolved it; a literal bypasses both.
    """
    text = path.read_text(encoding="utf-8")
    for pattern in BASE_LITERAL_PATTERNS:
        found = pattern.findall(text)
        assert not found, (
            f"{_rel(path)} hardcodes a base literal {found!r}. "
            "Shell out to scripts/branch-context.sh and use its detected merge target."
        )


# ---------------------------------------------------------------------------
# (b) The two SEVERITY_ORDER dicts must agree key for key
# ---------------------------------------------------------------------------

SEVERITY_ORDER_RE = re.compile(r"SEVERITY_ORDER\s*=\s*\{(.*?)\}", re.DOTALL)
SEVERITY_ENTRY_RE = re.compile(r"""["'](\w+)["']\s*:\s*(\d+)""")


def _parse_severity_order(path: Path) -> dict[str, int]:
    match = SEVERITY_ORDER_RE.search(path.read_text(encoding="utf-8"))
    assert match, f"{_rel(path)} declares no SEVERITY_ORDER dict"
    entries = SEVERITY_ENTRY_RE.findall(match.group(1))
    assert entries, f"{_rel(path)}: SEVERITY_ORDER parsed to zero entries"
    return {name: int(rank) for name, rank in entries}


def test_severity_order_dicts_agree_key_for_key():
    """The plan command and the report command declare ONE contract in two places.

    A key present in one and missing in the other routes those findings through
    the `.get(..., 99)` fallback in the consumer, where they sort last and vanish
    from `review-summary.json`'s `by_severity` -- silently, with no error.

    The declaring copy lives in ``commands/advanced-code-review-plan.md``; it was
    written in the parent skill until the skill was slimmed to a pointer. What
    the guard protects is the AGREEMENT of two independently edited copies, not
    the identity of the file holding either one.
    """
    plan_order = _parse_severity_order(PLAN_COMMAND)
    report_order = _parse_severity_order(REPORT_COMMAND)

    assert plan_order.keys() == report_order.keys(), (
        "SEVERITY_ORDER key sets diverged.\n"
        f"  only in {_rel(PLAN_COMMAND)}: {sorted(plan_order.keys() - report_order.keys())}\n"
        f"  only in {_rel(REPORT_COMMAND)}: {sorted(report_order.keys() - plan_order.keys())}"
    )
    assert plan_order == report_order, (
        f"SEVERITY_ORDER ranks diverged.\n  plan:   {plan_order}\n  report: {report_order}"
    )


def test_severity_order_includes_question():
    """QUESTION is the key that has actually gone missing before. Pin it by name."""
    for path in (PLAN_COMMAND, REPORT_COMMAND):
        assert "QUESTION" in _parse_severity_order(path), (
            f"{_rel(path)}: SEVERITY_ORDER dropped QUESTION"
        )



def test_retired_severities_are_not_emitted_by_any_review_document():
    """IMPORTANT and MINOR are retired; SEVERITY_ORDER has no such keys.

    They previously survived in one sibling's output format string after the
    others were migrated, which is exactly how the QUESTION bug reached
    production -- through a different door.
    """
    retired = re.compile(r"\b(IMPORTANT|MINOR|SUGGESTION)\b")
    offenders = {}
    for path in _guarded_files() + [REPO_ROOT / "agents" / "code-reviewer.md"]:
        text = path.read_text(encoding="utf-8")
        # Only the emittable-severity contexts matter: a heading format string
        # or a bare severity token in a findings template.
        for line in text.splitlines():
            if "severity" not in line.lower() and not line.lstrip().startswith("###"):
                continue
            if retired.search(line) and "retired" not in line.lower():
                offenders.setdefault(_rel(path), []).append(line.strip())
    assert not offenders, (
        "Retired severity names appear in an emittable position. "
        f"The consumer's SEVERITY_ORDER lacks them, so they vanish: {offenders}"
    )


# ---------------------------------------------------------------------------
# (a2) An empty coverage manifest must never certify
# ---------------------------------------------------------------------------

REVIEW_COMMAND = REPO_ROOT / "commands" / "advanced-code-review-review.md"
PLAN_COMMAND = REPO_ROOT / "commands" / "advanced-code-review-plan.md"


def _load_reconcile_namespace() -> dict:
    blocks = [
        b
        for b in PY_BLOCK_RE.findall(REVIEW_COMMAND.read_text(encoding="utf-8"))
        if "def reconcile_coverage" in b
    ]
    assert len(blocks) == 1, (
        f"expected exactly one reconcile_coverage code block, found {len(blocks)}"
    )
    ns: dict = {}
    exec(compile(blocks[0], str(REVIEW_COMMAND), "exec"), ns)
    return ns


EMPTY_MANIFEST = {"units": [], "total_files": 0, "total_hunks": 0, "total_lines": 0}


def test_empty_manifest_is_a_hard_error_not_a_clean_review():
    """``complete: not gaps`` is TRUE over an empty manifest.

    Zero units means zero gaps means "complete", so a review that enumerated
    NOTHING certified itself: "Hunks reviewed: 0/0, Coverage gaps: none,
    complete: true". This was live, not hypothetical -- a branch with zero
    commits makes ``files-committed`` return nothing, and the manifest built
    from it is empty while 125 files sit unreviewed.

    A review that read nothing must not certify. It must ERROR.
    """
    ns = _load_reconcile_namespace()
    with pytest.raises(ns["EmptyManifestError"]) as excinfo:
        ns["reconcile_coverage"](dict(EMPTY_MANIFEST))
    assert "E_EMPTY_MANIFEST" in str(excinfo.value)


def test_reconcile_still_certifies_a_genuinely_complete_review():
    """The zero-hunk guard must not break the normal N-of-N path."""
    ns = _load_reconcile_namespace()
    manifest = {
        "units": [{"id": "u1", "file": "a.py", "lines": 10, "reviewed": True,
                   "skipped_reason": None}],
        "total_files": 1,
        "total_hunks": 1,
        "total_lines": 10,
    }
    result = ns["reconcile_coverage"](manifest)
    assert result["complete"] is True
    assert result["hunks"] == "1/1"


def test_reconcile_discloses_an_unreviewed_hunk():
    ns = _load_reconcile_namespace()
    manifest = {
        "units": [
            {"id": "u1", "file": "a.py", "lines": 10, "reviewed": True, "skipped_reason": None},
            {"id": "u2", "file": "b.py", "lines": 5, "reviewed": False, "skipped_reason": None},
        ],
        "total_files": 2,
        "total_hunks": 2,
        "total_lines": 15,
    }
    result = ns["reconcile_coverage"](manifest)
    assert result["complete"] is False
    assert result["gaps"] == [{"id": "u2", "reason": "NOT REVIEWED"}]


def test_e_no_diff_is_keyed_on_the_committed_endpoint():
    """``files_changed`` is the WORKING-TREE count; E_NO_DIFF must not use it.

    The preflight reads ``branch-context.sh json``. Keying E_NO_DIFF on
    ``files_changed`` lets a branch with zero commits and a dirty tree look
    reviewable, which is precisely how the empty manifest gets built.
    """
    text = PLAN_COMMAND.read_text(encoding="utf-8")
    assert "files_changed_committed" in text, (
        "the plan command must read the committed file count from the json endpoint"
    )
    no_diff_row = next(
        line for line in text.splitlines() if line.startswith("| E_NO_DIFF ")
    )
    assert "files_changed_committed" in no_diff_row, (
        f"E_NO_DIFF is not keyed on the committed endpoint: {no_diff_row}"
    )


# ---------------------------------------------------------------------------
# (b2) The merge gate must FAIL CLOSED
# ---------------------------------------------------------------------------

TAXONOMY = REPO_ROOT / "patterns" / "code-review-taxonomy.md"

PY_BLOCK_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _load_verdict_namespace() -> dict:
    """Execute the ``determine_verdict`` code block out of the report command.

    The gate is prose-embedded Python. Asserting on its TEXT (``"case-insensitive
    appears somewhere"``) is not a guard -- it is a spell check. Executing it is
    the only way to pin the behaviour that decides whether a finding blocks.
    """
    blocks = [b for b in PY_BLOCK_RE.findall(REPORT_COMMAND.read_text(encoding="utf-8"))
              if "def determine_verdict" in b]
    assert len(blocks) == 1, (
        f"expected exactly one determine_verdict code block, found {len(blocks)}"
    )
    ns: dict = {}
    exec(compile(blocks[0], str(REPORT_COMMAND), "exec"), ns)
    return ns


@pytest.mark.parametrize(
    "severity",
    ["CRITICAL", "Critical", "critical", "  Critical  ", "HIGH", "High", "high"],
    ids=repr,
)
def test_verdict_blocks_regardless_of_severity_casing(severity: str):
    """A blocking finding must block however its producer spelled it.

    The gate used exact-uppercase membership (``if "CRITICAL" in severities``).
    ``patterns/code-review-taxonomy.md`` -- which ``agents/code-reviewer.md``
    calls the authoritative classification reference -- wrote its severities in
    Title Case. An agent that followed the taxonomy emitted ``"Critical"``, the
    gate matched nothing, and returned APPROVE with "No blocking issues found."
    A critical finding merged silently.
    """
    ns = _load_verdict_namespace()
    assert ns["determine_verdict"]([{"severity": severity}]) == "REQUEST_CHANGES"


def test_verdict_fails_closed_on_an_unrecognised_severity():
    """An unknown severity is NOT evidence of harmlessness.

    Falling through to APPROVE means any producer speaking a vocabulary the gate
    does not know gets waved through. The gate cannot rank it, so it blocks.
    """
    ns = _load_verdict_namespace()
    assert ns["determine_verdict"]([{"severity": "SHOWSTOPPER"}]) == "REQUEST_CHANGES"
    assert ns["determine_verdict"]([{"severity": "IMPORTANT"}]) == "REQUEST_CHANGES"


def test_verdict_still_approves_a_genuinely_clean_review():
    """Failing closed must not mean failing always -- the gate must still open."""
    ns = _load_verdict_namespace()
    assert ns["determine_verdict"]([]) == "APPROVE"
    assert ns["determine_verdict"]([{"severity": "PRAISE"}, {"severity": "NIT"}]) == "APPROVE"
    assert ns["determine_verdict"]([{"severity": "MEDIUM"}]) == "COMMENT"
    assert ns["determine_verdict"](
        [{"severity": "CRITICAL", "verification_status": "REFUTED"}]
    ) == "APPROVE"


def test_taxonomy_pattern_file_teaches_bugs_are_high():
    """The authoritative taxonomy must agree with the canon it is cited against.

    It said "**Critical** | Bugs, security vulnerabilities..." while the skill
    and ``Severity`` both said bugs are HIGH, never CRITICAL. An agent following
    the taxonomy produced findings the gate could not rank.
    """
    text = TAXONOMY.read_text(encoding="utf-8")
    assert "Bugs are HIGH" in text, (
        "patterns/code-review-taxonomy.md must state the bugs-are-HIGH rule verbatim"
    )
    assert not re.search(r"\|\s*\*\*Critical\*\*\s*\|\s*Bugs", text), (
        "the taxonomy still classifies bugs as CRITICAL"
    )


@pytest.mark.parametrize(
    "token", ["Critical", "High", "Medium", "Low", "Nit", "Praise"], ids=str
)
def test_taxonomy_severity_tokens_are_uppercase(token: str):
    """Severity tokens are matched exactly by the gate, so casing is a contract."""
    text = TAXONOMY.read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in text.splitlines()
        if re.search(rf"\*\*{token}\*\*", line)
    ]
    assert not offenders, (
        f"patterns/code-review-taxonomy.md writes {token!r} in Title Case as an "
        f"emittable severity token: {offenders}"
    )


# ---------------------------------------------------------------------------
# (c) The anti-bypass sentence is present in all three skill descriptions
# ---------------------------------------------------------------------------

ANTI_BYPASS = (
    "Never bypass the review skills for a raw Explore dispatch, even when the "
    "user's concerns seem narrow or specific."
)


def _frontmatter_description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{_rel(path)} has no YAML frontmatter"
    desc = re.search(r'^description:\s*"(.*)"\s*$', match.group(1), re.MULTILINE)
    assert desc, f"{_rel(path)} frontmatter has no quoted description"
    return desc.group(1)


@pytest.mark.parametrize("path", REVIEW_SKILLS, ids=_rel)
def test_anti_bypass_sentence_present(path: Path):
    """Each review skill's description must carry the anti-bypass sentence.

    The routing failure it prevents is dispatching a bare Explore agent instead
    of a review skill when the user's ask sounds narrow. Dropping the sentence
    from any one of the three reopens that path via that skill's description.
    """
    assert ANTI_BYPASS in _frontmatter_description(path), (
        f"{_rel(path)} description is missing the anti-bypass sentence:\n  {ANTI_BYPASS}"
    )


# ---------------------------------------------------------------------------
# (d) The three trigger sets must be pairwise disjoint
# ---------------------------------------------------------------------------

TRIGGER_QUOTE_RE = re.compile(r"'([^']+)'")


def _triggers(path: Path) -> set[str]:
    """Extract the quoted trigger phrases from the `Triggers:` clause.

    The clause runs from `Triggers:` to the `NOT for:` that follows it, so the
    counter-examples listed under `NOT for:` are not mistaken for triggers.
    """
    desc = _frontmatter_description(path)
    start = desc.index("Triggers:")
    end = desc.index("NOT for:", start)
    return {t.strip().lower() for t in TRIGGER_QUOTE_RE.findall(desc[start:end])}


def test_each_skill_declares_triggers():
    """A disjointness guard over empty sets passes vacuously. Pin non-emptiness."""
    for path in REVIEW_SKILLS:
        assert len(_triggers(path)) >= 3, f"{_rel(path)} declares too few triggers"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (CODE_REVIEW_SKILL, ADVANCED_SKILL),
        (CODE_REVIEW_SKILL, DISTILLING_SKILL),
        (ADVANCED_SKILL, DISTILLING_SKILL),
    ],
    ids=lambda p: _rel(p),
)
def test_trigger_sets_are_disjoint(left: Path, right: Path):
    """A phrase claimed by two skills makes routing ambiguous.

    These three skills partition the review space: lightweight-on-request,
    default branch review, and triage. A shared trigger means the model picks by
    chance, which is how an unspecified-scope 'code review' silently degrades to
    the lightweight pass.
    """
    overlap = _triggers(left) & _triggers(right)
    assert not overlap, (
        f"{_rel(left)} and {_rel(right)} both claim the trigger(s) {sorted(overlap)}. "
        "Each phrase must route to exactly one skill."
    )
