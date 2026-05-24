"""Pure derivation of develop's remaining quality-gate list.

This module is the single executable form of the develop skill's review policy:

- Design §3.2 — tiered review floor. The **full floor** (TDD-first, code review,
  test suite, green-mirage) runs on every flagged path; the **lighter floor**
  (code review, green-mirage, conditional test suite, TDD-first waived) runs on
  the zero-flag fast path.
- Design §3.3 — flag-gated depth gates layered on top of the floor, each firing
  only when the flag that produced an artifact-to-challenge is set.
- Design §3.4 — TDD-first is waived on the fast path.
- Design §2.1 — flag → phase mapping; used here only to order the emitted gates
  by workflow phase progression (Phase 1 -> Phase 4) so the scalar is stable.

The function is PURE: no DB access, no I/O, no filesystem probing. ``tests_exist``
is an input the caller (develop, in Phase 0 before the fast-path ledger write)
computes from its own touched-file analysis and passes in; the helper trusts it.

The return value is ALWAYS a single ``"\\n"``-joined scalar string (CRIT-1),
never a list. This is the representation that defeats ``_deep_merge``'s
list-append behavior when the ledger round-trips through workflow_state.

The documented develop derivation rules (skill Task 16) mirror this helper so
the documented behavior and the tested behavior cannot diverge.
"""

from collections.abc import Iterable, Mapping

# Sentinel emitted in place of the plain "test suite" gate on the fast path when
# no tests cover the touched code. It is a line WITHIN the scalar (never a
# companion field) so "not applicable" is explicit and never silently dropped.
# The em-dash is intentional and must match design §3.2 exactly.
TEST_SUITE_NA_SENTINEL = "test suite (n/a — no tests cover touched code)"


def _need(need_flags: Mapping[str, bool], key: str) -> bool:
    return bool(need_flags.get(key, False))


def derive_remaining_gates(
    need_flags: Mapping[str, bool],
    current_phase: str,
    tests_exist: bool,
    completed_gates: Iterable[str] = (),
) -> str:
    """Compute the remaining-gates scalar from need-flags and fast-path state.

    Args:
        need_flags: Mapping with boolean ``needs_research``, ``needs_design``,
            and ``needs_infrastructure`` keys (missing keys default to False).
            Per §2.2, ``needs_infrastructure`` implies ``needs_design``; this
            implication is honored here so callers need not pre-expand it.
        current_phase: The develop phase label (e.g. ``"fast-path"``, ``"2"``,
            ``"4"``). Accepted for ledger provenance / future ordering; the gate
            SET is determined by the flags, not the phase.
        tests_exist: Whether tests already cover the touched code. Computed by
            the caller; trusted as input to keep this function pure.
        completed_gates: Gate names already completed; re-derivation REPLACES the
            scalar with these removed (pruning, §5.6.5 case 4).

    Returns:
        A ``"\\n"``-joined scalar string of the gate names still to run. Never a
        list (CRIT-1).
    """
    needs_research = _need(need_flags, "needs_research")
    # §2.2: needs_infrastructure implies needs_design.
    needs_design = _need(need_flags, "needs_design") or _need(need_flags, "needs_infrastructure")
    needs_infrastructure = _need(need_flags, "needs_infrastructure")

    flagged = needs_research or needs_design or needs_infrastructure

    gates: list[str] = []

    if not flagged:
        # Zero flags -> the lighter floor (§3.2). Code review + green-mirage
        # always run; test suite runs only when tests exist (otherwise the
        # not-applicable sentinel is recorded, never silently dropped); TDD-first
        # is WAIVED (§3.4) so it is omitted entirely.
        gates.append("code review")
        gates.append("green-mirage")
        gates.append("test suite" if tests_exist else TEST_SUITE_NA_SENTINEL)
    else:
        # Flagged path -> flag-gated depth gates (§3.3) layered above the full
        # floor (§3.2), emitted in workflow phase progression order (§2.1).

        # Phase 1 — research-gated depth (§3.3).
        if needs_research:
            gates.append("research-quality")  # Phase 1.4
            gates.append("discovery completeness")  # Phase 1.5.5
            gates.append("dehallucination")  # Phase 1.5.7

        # Phase 1.6 — devil's advocate fires for needs_design OR needs_research.
        if needs_design or needs_research:
            gates.append("devil's advocate")

        # Phase 2 — design-gated depth (§3.3).
        if needs_design:
            gates.append("design review")  # Phase 2.2
            gates.append("assumption verification")  # Phase 2.5

        # Phase 3.2 — impl-plan review fires for needs_design OR needs_infrastructure.
        if needs_design or needs_infrastructure:
            gates.append("impl-plan review")

        # Phase 4 — the full review floor (§3.2), in sub-phase order:
        # TDD-first (4.3), code review (4.5), test suite (4.6.2),
        # green-mirage (4.6.3).
        gates.append("TDD-first")
        gates.append("code review")
        gates.append("test suite")
        gates.append("green-mirage")

        # Phase 4.6.4/4.6.5 — fact-checking fires for needs_research OR needs_design.
        if needs_research or needs_design:
            gates.append("fact-checking")

    completed = set(completed_gates)
    remaining = [g for g in gates if g not in completed]
    return "\n".join(remaining)
