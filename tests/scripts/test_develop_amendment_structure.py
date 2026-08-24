"""Structural guards for four develop-flow amendments.

Each amendment made a claim that spans more than one place in the tree.
Presence alone is not the invariant -- a paragraph that says anything at
all satisfies a presence check -- so every test here pins a relationship:
two locations that must agree, a quotation that must resolve to its
source, or a derived token set that must be fully enumerated.

``test_can_still_fail_appears_in_envelope_and_dispatch_template``
    ``CAN_STILL_FAIL`` is required of every dispatch. It is only actually
    required if the copy-paste dispatch template carries it too; a field
    that exists solely in the canonical envelope is one an orchestrator
    pasting the template never sends.

``test_carried_figures_appears_in_guidance_and_dispatch_template``
    Same two-location shape for the carried-figures line.

``test_can_still_fail_quotes_a_real_checkability_rule``
    The ``CAN_STILL_FAIL`` prose quotes a Checkability rule verbatim and
    claims to promote it. The quotation must resolve to an actual
    numbered item in the Checkability list.

``test_calibration_item_cross_reference_resolves``
    The instrument-calibration item claims the file-reading rule module
    names the ``git grep`` hazard for one tool. That cross-module claim
    must hold.

``test_aggregation_enumerates_every_non_passing_verdict``
    The real invariant of the §4.4 and §4.6.1 gates: the verdict tokens
    are DERIVED from each protocol's own lists, and every token that is
    not named passing must appear in that gate's blocking enumeration. A
    future list in either section whose failing verdict was never added
    to the enumeration fails here.

``test_gate_list_count_matches_the_protocol``
    ``Overall: COMPLETE`` requires a passing verdict "in all five lists",
    in both gates. A written-out count is a liability unless a mechanism
    reads it.

``test_imperative_coverage_defines_a_passing_and_a_failing_token``
    The amendment is only a gate if its failing token is blocking, and
    every token it declares must be classified passing or blocking.

``test_demonstrated_and_traced_coverage_are_distinguished``
    Imperative coverage has a strong procedure and a weak one. Collapsing
    them back into one ``COVERED`` token is the defect the split fixed.

``test_artifact_verification_items_declare_their_provenance``
    Every per-phase verification item declares whether a mechanism decides
    it (``[CHECKED]``) or a party asserts it (``[SELF]``). A bare ``- [ ]``
    box reads as a check while being neither.

Stated blind spot: these tests prove the wiring of each amendment, never
that the prose it wires is good advice.
"""

import os
import re
from pathlib import Path

import pytest

# $SPELLBOOK_TEST_ROOT redirects the sources these tests read. It exists so
# the RED half of each structural claim can be demonstrated against a
# mutated scratch copy without ever mutating the repository's own files.
REPO_ROOT = Path(os.environ.get("SPELLBOOK_TEST_ROOT") or Path(__file__).resolve().parents[2])
DEVELOP_SKILL = REPO_ROOT / "commands" / "develop-configure.md"
EXECUTE_COMMAND = REPO_ROOT / "commands" / "feature-implement-execute.md"
FILE_READING_RULE = REPO_ROOT / "rules" / "82-file-reading.md"

NUMBER_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
}


def _read(path: Path) -> str:
    assert path.is_file(), f"missing source file: {path}"
    return path.read_text(encoding="utf-8")


def _slice(text: str, start_pattern: str, end_pattern: str) -> str:
    start = re.search(start_pattern, text, re.MULTILINE)
    assert start, f"section start not found: {start_pattern!r}"
    end = re.search(end_pattern, text[start.end() :], re.MULTILINE)
    assert end, f"section end not found: {end_pattern!r}"
    return text[start.end() : start.end() + end.start()]


@pytest.fixture(scope="module")
def develop_text() -> str:
    return _read(DEVELOP_SKILL)


@pytest.fixture(scope="module")
def execute_text() -> str:
    return _read(EXECUTE_COMMAND)


@pytest.fixture(scope="module")
def canonical_envelope(develop_text: str) -> str:
    """The `Subagent -> Orchestrator` return envelope block."""
    return _slice(
        develop_text,
        r"^### Subagent .* Orchestrator \(in every return summary\)$",
        r"^### ",
    )


@pytest.fixture(scope="module")
def dispatch_template(develop_text: str) -> str:
    """The copy-paste Task() dispatch template an orchestrator pastes."""
    return _slice(
        develop_text,
        r"^### What To Do Instead$",
        r"^\*\*OpenCode:\*\*",
    )


@pytest.fixture(scope="module")
def dispatch_guidance(develop_text: str) -> str:
    """The numbered dispatch-prompt guidance preceding the envelope."""
    return _slice(
        develop_text,
        r"^4\. \*\*Forbidden phrasing\.\*\*",
        r"^### Subagent .* Orchestrator",
    )


@pytest.fixture(scope="module")
def per_task_audit(execute_text: str) -> str:
    """Section 4.4, the per-task Implementation Completion Verification."""
    return _slice(
        execute_text,
        r"^### 4\.4 Implementation Completion Verification$",
        r"^### 4\.5 ",
    )


@pytest.fixture(scope="module")
def comprehensive_audit(execute_text: str) -> str:
    """Section 4.6.1, the after-all-tasks Comprehensive Implementation Audit."""
    return _slice(
        execute_text,
        r"^#### 4\.6\.1 Comprehensive Implementation Audit$",
        r"^#### 4\.6\.2 ",
    )


# Every gate that derives an overall result from per-item verdicts. The count
# fixture names the unit the gate's "in all N lists" clause is counting: 4.4
# counts its `Verdict:` lines, 4.6.1 counts its numbered Phases.
AGGREGATING_GATES = [
    pytest.param("per_task_audit", r"^\s*4\. Verdict: ", id="4.4"),
    pytest.param("comprehensive_audit", r"^\s*### Phase \d+", id="4.6.1"),
]


# ---- two-location amendments --------------------------------------------


def test_can_still_fail_appears_in_envelope_and_dispatch_template(
    canonical_envelope: str, dispatch_template: str
) -> None:
    assert "CAN_STILL_FAIL" in canonical_envelope
    assert "CAN_STILL_FAIL" in dispatch_template


def test_carried_figures_appears_in_guidance_and_dispatch_template(
    dispatch_guidance: str, dispatch_template: str, develop_text: str
) -> None:
    assert "CARRIED" in dispatch_guidance
    assert "CARRIED FIGURES:" in dispatch_template
    # The guidance says to state it "verbatim"; the template is what gets
    # pasted, so the template must carry the literal instruction, not a
    # reference to one.
    assert "Re-derive" in dispatch_template or "re-derive" in dispatch_template


# ---- quotation and cross-reference claims -------------------------------


def test_can_still_fail_quotes_a_real_checkability_rule(develop_text: str) -> None:
    promotion = re.search(
        r"`CAN_STILL_FAIL` is required[^\n]*(?:\n[^\n]*){0,4}?"
        r"Checkability rule \"([^\"]+)\"",
        develop_text,
    )
    assert promotion, "CAN_STILL_FAIL no longer names the Checkability rule it promotes"
    quoted = " ".join(promotion.group(1).split()).rstrip(".")

    checkability = _slice(
        develop_text,
        r"^### Checkability \(before every review gate\)$",
        r"^\*\*Scope\.\*\*",
    )
    items = re.findall(r"^\d+\. \*\*([^*]+)\*\*", checkability, re.MULTILINE)
    normalized = {" ".join(item.split()).rstrip(".").lower() for item in items}
    assert quoted.lower() in normalized, (
        f"CAN_STILL_FAIL quotes {quoted!r}, which is not a Checkability item; "
        f"items are {sorted(normalized)}"
    )


def test_calibration_item_cross_reference_resolves(develop_text: str) -> None:
    checkability = _slice(
        develop_text,
        r"^### Checkability \(before every review gate\)$",
        r"^\*\*Scope\.\*\*",
    )
    calibration = re.search(
        r"^\d+\. \*\*Calibrate an instrument[^\n]*(?:\n(?!\d+\. |\*\*)[^\n]*)*",
        checkability,
        re.MULTILINE,
    )
    assert calibration, "the instrument-calibration Checkability item is gone"
    body = calibration.group(0)

    assert "known-positive" in body and "known-negative" in body, (
        "calibration item no longer names the two inputs an instrument is "
        "calibrated against"
    )
    assert "file-reading" in body, (
        "calibration item no longer names the rule module it generalizes"
    )
    rule_text = _read(FILE_READING_RULE)
    assert "git grep" in rule_text, (
        "develop's calibration item claims the file-reading rule module names "
        "the `git grep` hazard; it no longer does"
    )


# ---- derived verdict-token coverage -------------------------------------


TOKEN = re.compile(r"\b[A-Z][A-Z_]+\b")


def _verdict_lists(section: str) -> list[list[str]]:
    return [
        [token.strip() for token in line.split("|")]
        for line in re.findall(r"^\s*4\. Verdict: (.+)$", section, re.MULTILINE)
    ]


def _declared_tokens(section: str) -> set[str]:
    """Every verdict token a section's own protocol or report format emits.

    Two shapes carry a vocabulary: an alternation of caps tokens (a
    ``Verdict:``/``Mark:``/``Overall:`` line, or a report field offering a
    choice), and a failure marker naming its token directly (``✗ TOKEN``).
    Bracketed placeholders and parentheticals are stripped first -- they hold
    prose, not vocabulary. Deriving the set this way means a list added later
    is picked up without editing this test.
    """
    tokens: set[str] = set()
    for line in section.splitlines():
        bare = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", line)
        if "|" in bare:
            found = set(TOKEN.findall(bare))
            if len(found) >= 2:
                tokens |= found
            continue
        marker = re.search(r"✗\s+([A-Z][A-Z_]+)\b", bare)
        if marker:
            tokens.add(marker.group(1))
    return tokens


def _passing_tokens(section: str) -> set[str]:
    sentence = re.search(r"The passing verdicts are ([^.]+)\.", section)
    assert sentence, "Gate Behavior no longer names the passing verdicts"
    return set(TOKEN.findall(sentence.group(1)))


def _blocking_tokens(section: str) -> set[str]:
    sentence = re.search(
        r"Any other verdict\s*—\s*(.+?)\s*—\s*is a BLOCKING",
        section,
        re.DOTALL,
    )
    assert sentence, "Gate Behavior no longer enumerates the blocking verdicts"
    return set(TOKEN.findall(sentence.group(1)))


@pytest.mark.parametrize(("fixture_name", "list_pattern"), AGGREGATING_GATES)
def test_aggregation_enumerates_every_non_passing_verdict(
    request: pytest.FixtureRequest, fixture_name: str, list_pattern: str
) -> None:
    section: str = request.getfixturevalue(fixture_name)
    declared = _declared_tokens(section)
    assert declared, "no verdict vocabulary found in this gate"

    passing = _passing_tokens(section)
    blocking = _blocking_tokens(section)

    assert passing <= declared, f"passing verdicts not declared by any list: {passing - declared}"
    escaped = declared - passing - blocking
    assert not escaped, (
        f"verdicts that force no gate outcome: {sorted(escaped)} -- add them to "
        "the Gate Behavior enumeration"
    )
    phantom = blocking - declared
    assert not phantom, f"Gate Behavior enumerates verdicts no list produces: {sorted(phantom)}"


@pytest.mark.parametrize(("fixture_name", "list_pattern"), AGGREGATING_GATES)
def test_gate_list_count_matches_the_protocol(
    request: pytest.FixtureRequest, fixture_name: str, list_pattern: str
) -> None:
    section: str = request.getfixturevalue(fixture_name)
    claim = re.search(r"requires\s+a\s+passing\s+verdict\s+in\s+all\s+(\w+)\s+lists", section)
    assert claim, "Gate Behavior no longer states how many lists must pass"
    word = claim.group(1).lower()
    assert word in NUMBER_WORDS, f"unrecognized count word: {word!r}"
    actual = len(re.findall(list_pattern, section, re.MULTILINE))
    assert NUMBER_WORDS[word] == actual, f"claims {word} lists, protocol has {actual}"


def test_imperative_coverage_defines_a_passing_and_a_failing_token(
    per_task_audit: str,
) -> None:
    section = _slice(per_task_audit, r"^    ### 5\. Imperative Coverage$", r"^    ## Output Format$")
    verdicts = re.findall(r"^\s*4\. Verdict: (.+)$", section, re.MULTILINE)
    assert len(verdicts) == 1, "Imperative Coverage no longer declares exactly one verdict line"
    tokens = [token.strip() for token in verdicts[0].split("|")]
    assert len(tokens) >= 2, f"expected at least a passing and a failing token, got {tokens}"

    passing = _passing_tokens(per_task_audit)
    blocking = _blocking_tokens(per_task_audit)
    assert set(tokens) & passing, f"{tokens} has no passing token"
    assert len(set(tokens) & blocking) == 1, f"{tokens} has no single blocking token"
    unclassified = set(tokens) - passing - blocking
    assert not unclassified, f"verdicts classified neither way: {sorted(unclassified)}"


def test_demonstrated_and_traced_coverage_are_distinguished(
    per_task_audit: str,
) -> None:
    """The strong and weak imperative-coverage procedures stay distinct.

    Collapsing them back to one token would restore the defect this split
    fixed: a traced imperative reported with the same word as a demonstrated
    one. Both tokens must be declared passing, and the weak one must carry the
    sentence saying what it does NOT establish.
    """
    section = _slice(per_task_audit, r"^    ### 5\. Imperative Coverage$", r"^    ## Output Format$")
    tokens = _verdict_lists(section)[0]
    assert "COVERED_DEMONSTRATED" in tokens
    assert "COVERED_TRACED" in tokens
    assert _passing_tokens(per_task_audit) >= {"COVERED_DEMONSTRATED", "COVERED_TRACED"}
    assert "COVERED" not in _passing_tokens(per_task_audit), (
        "the undifferentiated COVERED token is back; it is what let a traced "
        "imperative be reported as a demonstrated one"
    )
    assert re.search(r"does\s+NOT\s+establish", section), (
        "the TRACED procedure no longer states its limit"
    )


def test_artifact_verification_items_declare_their_provenance() -> None:
    """Every artifact-verification item says whether a mechanism decides it.

    A bare `- [ ]` box reads as a check. Many of these items are asserted by
    the party that would have skipped the step. The marker is the whole repair:
    it must be present on every item, so a new item cannot be added in the
    ambiguous old shape.

    The dispatch items are now `[CHECKED]` against a ledger the agent does not
    author (the `PostToolUse` hook on `Task` writes it). That upgrade is only
    honest while the legend keeps saying what the record does NOT prove, so the
    final assertion pins the limit rather than the old "nothing is recorded"
    claim -- which this change made false.
    """
    section = _slice(
        DEVELOP_SKILL.read_text(encoding="utf-8"),
        r"^## MANDATORY: Artifact Verification Per Phase$",
        r"^## MANDATORY: Artifact Verification Protocol$",
    )
    items = re.findall(r"^- \[([^\]]*)\]", section, re.MULTILINE)
    assert items, "no artifact-verification items found"
    unmarked = [item for item in items if item not in ("CHECKED", "SELF")]
    assert not unmarked, (
        f"items with no provenance marker: {unmarked!r} -- every item must be "
        "[CHECKED] (a command decides it) or [SELF] (a self-assertion)"
    )
    assert "SELF" in items and "CHECKED" in items, (
        "both markers must appear; a section that is all one marker means the "
        "distinction stopped being drawn"
    )
    # \s+ between words, not a literal space: the legend is prose wrapped at
    # ~80 columns, so any of these phrases may straddle a newline. A literal
    # space would make this assertion fail on a reflow and pass only by
    # accident of where the wrap happened to land.
    assert re.search(r"does\s+not\s+close\s+the\s+hole", section), (
        "the legend no longer states that a recorded dispatch is not proof the "
        "work was done; a [CHECKED] dispatch item read without that limit "
        "claims more than the record supports"
    )
    assert re.search(r"proves\s+a\s+dispatch\s+HAPPENED", section), (
        "the legend no longer names what the dispatch record actually proves"
    )
