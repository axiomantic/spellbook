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

from spellbook.sessions.develop_gates import derive_remaining_gates


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
