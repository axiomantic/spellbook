---
description: "Phase 2 of implementing-features: Create and review design document"
---

# /feature-design

Phase 2 of the implementing-features workflow. Run after `/feature-discover` completes.

**Prerequisites:** Phase 1.5 complete, SESSION_CONTEXT.design_context populated.

<CRITICAL>
## Prerequisite Verification

Before ANY Phase 2 work begins, run this verification:

```bash
# ══════════════════════════════════════════════════════════════
# PREREQUISITE CHECK: feature-design (Phase 2)
# ══════════════════════════════════════════════════════════════

PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')

echo "=== Phase 2 Prerequisites ==="

# CHECK 1: Complexity tier must be STANDARD or COMPLEX
echo "Required: complexity_tier in (standard, complex)"
echo "Current tier: [SESSION_PREFERENCES.complexity_tier]"
# If tier is TRIVIAL or SIMPLE, this phase should NOT be running.

# CHECK 2: Understanding document must exist (Phase 1.5 artifact)
echo "Required: Understanding document exists"
ls ~/.local/spellbook/docs/$PROJECT_ENCODED/understanding/ 2>/dev/null || echo "FAIL: No understanding document found"

# CHECK 3: Completeness score must be 100%
echo "Required: Phase 1.5 completeness score = 100%"
echo "Verify: SESSION_CONTEXT.design_context populated with no TBD values"

# CHECK 4: Devil's advocate was dispatched
echo "Required: Devil's advocate review completed"
```

**If ANY check fails:** STOP. Do not proceed. Return to the appropriate phase.

**Anti-rationalization reminder:** If you are tempted to skip this check because
"the feature is well-understood" or "we can design without the full discovery,"
that is Pattern 6 (Phase Collapse). Each phase produces distinct artifacts for
distinct reasons. The understanding document IS the input to design. Without it,
design is guesswork.
</CRITICAL>

## Invariant Principles

1. **Discovery precedes design** - Design only after design_context is complete; never design without research findings
2. **Synthesis mode for subagents** - Brainstorming subagent receives complete context; no interactive discovery in design phase
3. **Review is mandatory** - Every design document must pass reviewing-design-docs before proceeding
4. **Approval gates respect mode** - Interactive mode pauses for user; autonomous mode auto-fixes all findings

---

## Phase 2: Design

<CRITICAL>
Phase behavior depends on escape hatch:
- **No escape hatch:** Run full Phase 2
- **Design doc with "review first":** Skip 2.1, start at 2.2
- **Design doc with "treat as ready":** Skip entire Phase 2
- **Impl plan escape hatch:** Skip entire Phase 2
</CRITICAL>

### 2.1 Create Design Document

<RULE>Subagent MUST invoke brainstorming in SYNTHESIS MODE.</RULE>

```
Task (or subagent simulation):
  description: "Create design document"
  prompt: |
    First, invoke the brainstorming skill using the Skill tool.
    Then follow its complete workflow.

    IMPORTANT: This is SYNTHESIS MODE - all discovery is complete.
    DO NOT ask questions. Use the comprehensive context below.

    ## Autonomous Mode Context

    **Mode:** AUTONOMOUS - Proceed without asking questions
    **Protocol:** See patterns/autonomous-mode-protocol.md
    **Circuit breakers:** Only pause for security-critical or contradictory requirements

    ## Pre-Collected Discovery Context

    [Insert complete SESSION_CONTEXT.design_context]

    ## Task

    Using the brainstorming skill in synthesis mode:
    1. Skip "Understanding the idea" phase - context is complete
    2. Skip "Exploring approaches" questions - decisions are made
    3. Go directly to "Presenting the design"
    4. Do NOT ask "does this look right so far" - proceed through all sections
    5. Save to: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-design.md
```

### 2.2 Review Design Document

<RULE>Subagent MUST invoke reviewing-design-docs.</RULE>

```
Task (or subagent simulation):
  description: "Review design document"
  prompt: |
    First, invoke the reviewing-design-docs skill using the Skill tool.
    Then follow its complete workflow.

    ## Context for the Skill

    Design document location: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-design.md

    Return the complete findings report with remediation plan.
```

### 2.3 Approval Gate

**Approval Gate Logic:**

```python
def handle_review_checkpoint(findings, mode):
    if mode == "autonomous":
        # Never pause - proceed automatically
        # CRITICAL: Always favor most complete/correct fixes
        if findings:
            dispatch_fix_subagent(
                findings,
                fix_strategy="most_complete",  # Not "quickest"
                treat_suggestions_as="mandatory",  # Not "optional"
                fix_depth="root_cause"  # Not "surface_symptom"
            )
        return "proceed"

    if mode == "interactive":
        # Always pause - wait for user
        if len(findings) > 0:
            present_findings_summary(findings)
            display("Type 'continue' when ready for me to fix these issues.")
            wait_for_user_input()
            dispatch_fix_subagent(findings)
        else:
            display("Review complete - no issues found.")
            display("Ready to proceed to next phase?")
            wait_for_user_acknowledgment()
        return "proceed"

    if mode == "mostly_autonomous":
        # Only pause for critical blockers
        critical_findings = [f for f in findings if f.severity == "critical"]
        if critical_findings:
            present_critical_blockers(critical_findings)
            wait_for_user_input()
        if findings:
            dispatch_fix_subagent(findings)
        return "proceed"
```

### 2.4 Fix Design Document

<RULE>Subagent MUST invoke executing-plans.</RULE>

<CRITICAL>
In autonomous mode, ALWAYS favor most complete and correct solutions:
- Treat suggestions as mandatory improvements
- Fix root causes, not just symptoms
- Ensure fixes maintain consistency
</CRITICAL>

```
Task (or subagent simulation):
  description: "Fix design document"
  prompt: |
    First, invoke the executing-plans skill using the Skill tool.
    Then use its workflow to systematically fix the design document.

    ## Context for the Skill

    Review findings to address:
    [Paste complete findings report and remediation plan]

    Design document location: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-design.md

    ## Fix Quality Requirements

    - Address ALL items: critical, important, minor, AND suggestions
    - Choose fixes that produce highest quality results
    - Fix underlying issues, not just surface symptoms
```

---

## ═══════════════════════════════════════════════════════════════════
## STOP AND VERIFY: Phase 2 → Phase 3 Transition
## ═══════════════════════════════════════════════════════════════════

Before proceeding to Phase 3, verify Phase 2 is complete:

```bash
# Verify design document exists
ls ~/.local/spellbook/docs/<project-encoded>/plans/*-design.md
```

- [ ] Brainstorming subagent DISPATCHED in SYNTHESIS MODE (not done in main context)
- [ ] Design document created and saved
- [ ] Design review subagent (reviewing-design-docs) DISPATCHED
- [ ] Approval gate handled per autonomous_mode
- [ ] All critical/important findings fixed (if any)

If ANY unchecked: Go back to Phase 2. Do NOT proceed.

---

**Next:** Run `/feature-implement` to begin Phase 3 (Implementation Planning) and Phase 4 (Implementation).
