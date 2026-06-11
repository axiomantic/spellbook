"""Tests for the pure develop remaining-gates derivation helper (IMP-6).

The helper ``derive_remaining_gates`` is the single executable form of the
design's review-floor and flag-gated-depth policy:

- Design §3.2 — tiered review floor (full floor on flagged paths; lighter floor
  on the zero-flag fast path).
- Design §3.3 — flag-gated depth gates (research/design/infra mapped gates).
- Design §3.4 — TDD-first waiver on the fast path.
- Design §2.1 — flag → phase mapping (used to order gates by phase progression).

These tests assert the COMPLETE newline-joined scalar string for each case
(CRIT-1: the output is always a scalar, never a list), exercising all four
§5.6.5 cases: fast-path lighter floor with TDD waived, fully-flagged full floor
with depth gates, needs_design-only, and pruning.
"""

from functools import lru_cache
from pathlib import Path

from spellbook.sessions.develop_gates import derive_remaining_gates

_ROOT = Path(__file__).parent.parent

# Source fixtures are read lazily via cached reader functions so pytest
# collection performs no file I/O; each file is read at most once per run.


@lru_cache(maxsize=None)
def FEATURE_RESEARCH() -> str:
    return (_ROOT / "commands" / "feature-research.md").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def FEATURE_DISCOVER() -> str:
    return (_ROOT / "commands" / "feature-discover.md").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def FEATURE_DESIGN() -> str:
    return (_ROOT / "commands" / "feature-design.md").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def FEATURE_IMPLEMENT() -> str:
    return (_ROOT / "commands" / "feature-implement.md").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def DEVELOP_SKILL() -> str:
    return (_ROOT / "skills" / "develop" / "SKILL.md").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def CODE_REVIEW_GIVE() -> str:
    return (_ROOT / "commands" / "code-review-give.md").read_text(encoding="utf-8")


def _flags(research=False, design=False, infrastructure=False):
    return {
        "needs_research": research,
        "needs_design": design,
        "needs_infrastructure": infrastructure,
    }


def test_remaining_gates_derivation_from_flags():
    # --- Case 1: fast path (zero flags), tests exist -> lighter floor, TDD waived.
    fast_tests_exist = derive_remaining_gates(
        need_flags=_flags(),
        current_phase="fast-path",
        tests_exist=True,
    )
    assert fast_tests_exist == "code review\ngreen-mirage\ntest suite"

    # --- Case 1b: fast path (zero flags), NO tests -> in-scalar sentinel verbatim.
    fast_no_tests = derive_remaining_gates(
        need_flags=_flags(),
        current_phase="fast-path",
        tests_exist=False,
    )
    assert fast_no_tests == (
        "code review\ngreen-mirage\ntest suite (n/a — no tests cover touched code)"
    )

    # --- Case 2: fully flagged -> full floor + all flag-gated depth gates,
    # ordered by workflow phase progression (Phase 1 -> Phase 4).
    fully_flagged = derive_remaining_gates(
        need_flags=_flags(research=True, design=True, infrastructure=True),
        current_phase="2",
        tests_exist=True,
    )
    assert fully_flagged == (
        "research-quality\n"
        "discovery completeness\n"
        "dehallucination\n"
        "devil's advocate\n"
        "design review\n"
        "assumption verification\n"
        "impl-plan review\n"
        "TDD-first\n"
        "code review\n"
        "test suite\n"
        "green-mirage\n"
        "fact-checking"
    )

    # --- Case 3: needs_design only -> full floor + design-gated depth gates,
    # but NONE of the research-gated gates (research-quality, discovery,
    # dehallucination). devil's advocate, impl-plan review and fact-checking
    # still fire because needs_design alone triggers them (§3.3).
    design_only = derive_remaining_gates(
        need_flags=_flags(design=True),
        current_phase="2",
        tests_exist=True,
    )
    assert design_only == (
        "devil's advocate\n"
        "design review\n"
        "assumption verification\n"
        "impl-plan review\n"
        "TDD-first\n"
        "code review\n"
        "test suite\n"
        "green-mirage\n"
        "fact-checking"
    )

    # --- Case 3b: needs_infrastructure implies needs_design (§2.2). With ONLY
    # the infra flag set, the design-gated depth gates must still fire (the
    # implication is honored inside the helper, not pre-expanded by the caller),
    # while the research-gated gates stay absent.
    infra_only = derive_remaining_gates(
        need_flags=_flags(infrastructure=True),
        current_phase="2",
        tests_exist=True,
    )
    assert infra_only == (
        "devil's advocate\n"
        "design review\n"
        "assumption verification\n"
        "impl-plan review\n"
        "TDD-first\n"
        "code review\n"
        "test suite\n"
        "green-mirage\n"
        "fact-checking"
    )

    # --- Case 4: pruning. Re-derivation with a set of completed gates REPLACES
    # the scalar with those gates removed (ties to CRIT-1 replace-not-append).
    pruned = derive_remaining_gates(
        need_flags=_flags(design=True),
        current_phase="4",
        tests_exist=True,
        completed_gates=(
            "devil's advocate",
            "design review",
            "assumption verification",
            "impl-plan review",
            "TDD-first",
        ),
    )
    assert pruned == ("code review\ntest suite\ngreen-mirage\nfact-checking")


def test_standards_discovery_divisor_bumped_to_13():
    # Post-edit denominator forms PRESENT.
    assert "/ 13" in FEATURE_DISCOVER()                         # completeness_score divisor
    assert "(13 Validation Functions)" in FEATURE_DISCOVER()    # §1.5.5 heading
    assert "[N]/13 items complete" in FEATURE_DISCOVER()        # DISPLAY format
    assert "all 13 validation functions" in FEATURE_DISCOVER()  # §invariant line
    assert "13/13 validation functions" in FEATURE_DISCOVER()   # discover checklist
    assert "13/13 validation functions" in DEVELOP_SKILL()      # SKILL checklist
    assert "13 validation functions" in DEVELOP_SKILL()         # SKILL phase-map line
    assert "100% (13/13)" in DEVELOP_SKILL()                    # SKILL quality-gate table

    # Pre-edit denominator forms ABSENT (NEW pattern — not in the presence-only precedent).
    # Each absence assertion is annotated with the EXACT denominator site it pins, so a
    # future incidental substring elsewhere in the file cannot silently satisfy/break it.
    assert "/ 12" not in FEATURE_DISCOVER()                       # pins completeness_score divisor `(checked_count / 12)`
    assert "(12 Validation Functions)" not in FEATURE_DISCOVER()  # pins §1.5.5 heading `(12 Validation Functions)`
    assert "[N]/12 items complete" not in FEATURE_DISCOVER()      # pins DISPLAY-format `Completeness Score: [X]% ([N]/12 items complete)`
    assert "all 12 validation functions" not in FEATURE_DISCOVER() # pins invariant line `Proceed to design only when all 12 validation functions pass`
    assert "12/12 validation functions" not in FEATURE_DISCOVER() # pins discover checklist `Completeness Score = 100% (12/12 validation functions)`
    assert "12/12 validation functions" not in DEVELOP_SKILL()    # pins SKILL checklist `Completeness score = 100% (12/12 validation functions)`
    assert "12 validation functions" not in DEVELOP_SKILL()       # pins SKILL phase-map `1.5.5: GATE: Completeness Score = 100% (12 validation functions)`
    assert "100% (12/12)" not in DEVELOP_SKILL()                  # pins SKILL quality-gate table cell `| 100% (12/12) | User consent |`


def test_function_index_comment_count_is_13():
    # 12 existing FUNCTION comments + the new // FUNCTION 13:. The // FUNCTION 12:
    # index comment is PRESERVED (deliberately NOT asserted absent).
    assert FEATURE_DISCOVER().count("// FUNCTION ") == 13
    assert "// FUNCTION 12: Need-flags consistent with discovered scope" in FEATURE_DISCOVER()
    assert "// FUNCTION 13: Project standards discovered" in FEATURE_DISCOVER()


def test_standards_discovery_contract_markers_present():
    # §1.2.5 heading in feature-research.
    assert "1.2.5 Project Development-Guidance Discovery" in FEATURE_RESEARCH()
    assert "project_standards" in FEATURE_RESEARCH()
    # 13th validation function in feature-discover.
    assert "standards_discovered" in FEATURE_DISCOVER()
    # 13th DISPLAY-FORMAT checklist row in feature-discover (Task 5 Step 4 — the
    # operator-visible gate row; guards F4 — the row was previously untested).
    assert "[✓/✗] Project standards discovered" in FEATURE_DISCOVER()
    # Belt-and-suspenders: the DISPLAY-FORMAT block must carry >= 13 [✓/✗] rows
    # (12 pre-existing + the new standards row). Counts the checklist glyph directly.
    assert FEATURE_DISCOVER().count("[✓/✗]") >= 13
    # project_standards in the DesignContext block of SKILL.md.
    assert "project_standards" in DEVELOP_SKILL()
    # Binding Project Standards block in feature-implement §4.3 AND feature-design §2.1.
    assert "Binding Project Standards" in FEATURE_IMPLEMENT()
    assert "Binding Project Standards" in FEATURE_DESIGN()
    # Standards Conformance audit section in feature-implement §4.6.1.
    assert "Standards Conformance" in FEATURE_IMPLEMENT()
    # §4.6.1 audit Inputs block now hands the dispatched subagent the binding
    # standards (guards C-1 — Phase 5's BLOCKING gate was a no-op without them).
    # The "INCLUDING any adjudication blocks" phrasing is unique to the §4.6.1
    # Inputs paste, distinct from the §4.5 per-task review paste.
    assert "Binding project standards: [paste design_context.project_standards.binding_rules, INCLUDING any adjudication blocks" in FEATURE_IMPLEMENT()
    # feature-design §2.0 fallback sweep.
    assert "Fallback Sweep" in FEATURE_DESIGN()
    # operator-adjudication escape valve markers.
    assert "rule_overridden" in FEATURE_IMPLEMENT()
    assert "rule_not_applicable" in FEATURE_IMPLEMENT()
    # code-review-give consumes project_standards.
    assert "project_standards" in CODE_REVIEW_GIVE()
    # fast-path WAIVER note in SKILL.md (Task 10 — design §5.6 / Acceptance #9).
    assert "WAIVED on the fast path" in DEVELOP_SKILL()
