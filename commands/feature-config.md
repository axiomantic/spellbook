---
description: "Phase 0 of implementing-features: Configuration wizard, escape hatches, preferences, continuation detection"
---

# Feature Configuration (Phase 0)

## Invariant Principles

1. **Configuration before execution** - All preferences must be collected upfront; no proceeding without complete configuration
2. **Escape hatch detection** - Existing documents bypass phases they cover; detect before asking redundant questions
3. **Motivation drives design** - Understanding WHY shapes every subsequent decision; never skip motivation clarification
4. **Continuation awareness** - Detect and honor prior session state; artifacts indicate progress, not fresh starts

<CRITICAL>
The Configuration Wizard MUST be completed before any other work. This is NOT optional.
All preferences are collected upfront to enable fully autonomous mode.
</CRITICAL>

### 0.1 Detect Escape Hatches

<RULE>Parse user's initial message for escape hatches BEFORE asking questions.</RULE>

| Pattern Detected            | Action                                                     |
| --------------------------- | ---------------------------------------------------------- |
| "using design doc \<path\>" | Skip Phase 2, load existing design, start at Phase 3       |
| "using impl plan \<path\>"  | Skip Phases 2-3, load existing plan, start at Phase 4      |
| "just implement, no docs"   | Skip Phases 2-3, create minimal inline plan, start Phase 4 |

If escape hatch detected, ask via AskUserQuestion:

```markdown
## Existing Document Detected

I see you have an existing [design doc/impl plan] at <path>.

Header: "Document handling"
Question: "How should I handle this existing document?"

Options:

- Review first (Recommended): Run the reviewer skill before proceeding
- Treat as ready: Accept this document as-is and proceed directly
```

**Handle by choice:**

- **Review first (design doc):** Skip 2.1, load doc, jump to 2.2 (review)
- **Review first (impl plan):** Skip 2.1-3.1, load doc, jump to 3.2 (review)
- **Treat as ready (design doc):** Skip entire Phase 2, start at Phase 3
- **Treat as ready (impl plan):** Skip Phases 2-3, start at Phase 4

### 0.2 Clarify Motivation (WHY)

<RULE>Before diving into WHAT to build, understand WHY. Motivation shapes every subsequent decision.</RULE>

**When to Ask:**

| Request Type                           | Motivation Clear?       | Action  |
| -------------------------------------- | ----------------------- | ------- |
| "Add a logout button"                  | No - why now?           | Ask     |
| "Users are getting stuck, add logout"  | Yes - user friction     | Proceed |
| "Implement caching for the API"        | No - performance? cost? | Ask     |
| "API calls cost $500/day, add caching" | Yes - perf + cost       | Proceed |

**How to Ask (AskUserQuestion):**

```markdown
What's driving this request? Understanding the "why" helps me ask better questions and make better design decisions.

Suggested reasons (select or describe your own):

- [ ] Users requested/complained about this
- [ ] Performance or cost issue
- [ ] Technical debt / maintainability concern
- [ ] New business requirement
- [ ] Security or compliance need
- [ ] Developer experience improvement
- [ ] Other: \_\_\_
```

**Motivation Categories:**

| Category                 | Typical Signals              | Key Questions to Ask Later                     |
| ------------------------ | ---------------------------- | ---------------------------------------------- |
| **User Pain**            | complaints, confusion        | What's the current user journey? Failure mode? |
| **Performance**          | slow, expensive, timeout     | Current metrics? Target?                       |
| **Technical Debt**       | fragile, hard to maintain    | What breaks when touched?                      |
| **Business Need**        | new requirement, stakeholder | Deadline? Priority?                            |
| **Security/Compliance**  | audit, vulnerability         | Threat model? Requirement?                     |
| **Developer Experience** | tedious, error-prone         | How often? Workaround?                         |

Store in `SESSION_CONTEXT.motivation`.

### 0.3 Clarify the Feature (WHAT)

<RULE>Collect only the CORE essence. Detailed discovery happens in Phase 1.5 after research.</RULE>

Ask via AskUserQuestion:

- What is the feature's core purpose? (1-2 sentences)
- Are there any resources, links, or docs to review during research?

Store in `SESSION_CONTEXT.feature_essence`.

### 0.4 Collect Workflow Preferences

<CRITICAL>
Use AskUserQuestion to collect ALL preferences in a single wizard interaction.
These preferences govern behavior for the ENTIRE session.
</CRITICAL>

```markdown
## Configuration Wizard

### Question 1: Autonomous Mode

Header: "Execution mode"
Question: "Should I run fully autonomous after this wizard, or pause for approval at checkpoints?"

Options:

- Fully autonomous (Recommended): Proceed without pausing, automatically fix all issues
- Interactive: Pause after each review phase for explicit approval
- Mostly autonomous: Only pause for critical blockers I cannot resolve

### Question 2: Parallelization Strategy

Header: "Parallelization"
Question: "When tasks can run in parallel, how should I handle it?"

Options:

- Maximize parallel (Recommended): Spawn parallel subagents for independent tasks
- Conservative: Default to sequential, only parallelize when clearly beneficial
- Ask each time: Present opportunities and let you decide

### Question 3: Git Worktree Strategy

Header: "Worktree"
Question: "How should I handle git worktrees?"

Options:

- Single worktree (Recommended): One worktree; all tasks share it
- Worktree per parallel track: Separate worktrees per parallel group; smart merge after
- No worktree: Work in current directory

### Question 4: Post-Implementation Handling

Header: "After completion"
Question: "After implementation completes, how should I handle PR/merge?"

Options:

- Offer options (Recommended): Use finishing-a-development-branch skill
- Create PR automatically: Push and create PR without asking
- Just stop: Stop after implementation; you handle PR manually
```

Store all preferences in `SESSION_PREFERENCES`.

**Important:** If `worktree == "per_parallel_track"`, automatically set `parallelization = "maximize"`.

### 0.5 Continuation Detection

<CRITICAL>
This phase detects session continuation and enables zero-intervention recovery.
Execute BEFORE the Configuration Wizard questions if continuation signals detected.
</CRITICAL>

**Continuation Signals (any of):**

1. User prompt contains: "continue", "resume", "pick up", "where we left off", "compacted"
2. MCP `<system-reminder>` contains `**Skill Phase:**` with implementing-features phase
3. MCP `<system-reminder>` contains `**Active Skill:** implementing-features`
4. Artifacts exist in expected locations for current project

**If NO continuation signals:** Proceed to Phase 0.1 (escape hatch detection)

**If continuation signals detected:**

#### Step 1: Parse Recovery Context

Extract from `<system-reminder>` (if present):

- `active_skill`: Confirms implementing-features was active
- `skill_phase`: Highest phase reached (e.g., "Phase 2: Design")
- `todos`: In-progress work items with status
- `exact_position`: Recent tool actions for position verification

#### Step 2: Verify Artifact Existence

<CRITICAL>
Run these commands BEFORE claiming you are resuming from a phase.
Do NOT trust the session summary alone - verify artifacts actually exist.
</CRITICAL>

**Verification Commands (run ALL of these):**

```bash
# Compute project-encoded path
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')

# Check for understanding document (Phase 1.5+)
ls ~/.local/spellbook/docs/$PROJECT_ENCODED/understanding/ 2>/dev/null || echo "NO UNDERSTANDING DOC"

# Check for design document (Phase 2+)
ls ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/*-design.md 2>/dev/null || echo "NO DESIGN DOC"

# Check for implementation plan (Phase 3+)
ls ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/*-impl.md 2>/dev/null || echo "NO IMPL PLAN"

# Check for worktree (Phase 4+)
git worktree list | grep -v "$(pwd)$" || echo "NO WORKTREES"
```

**Expected Artifacts by Phase:**

| Phase Reached | Expected Artifacts                                                      |
| ------------- | ----------------------------------------------------------------------- |
| Phase 1.5+    | Understanding doc at `~/.local/spellbook/docs/<project>/understanding/` |
| Phase 2+      | Design doc at `~/.local/spellbook/docs/<project>/plans/*-design.md`     |
| Phase 3+      | Impl plan at `~/.local/spellbook/docs/<project>/plans/*-impl.md`        |
| Phase 4+      | Worktree at `.worktrees/<feature>/`                                     |

**Report State Before Acting:**

After running verification commands, display:

```markdown
## Session Continuation Verified

**Artifacts Found:**
- Understanding doc: [EXISTS at path / MISSING]
- Design doc: [EXISTS at path / MISSING]  
- Impl plan: [EXISTS at path / MISSING]
- Worktree: [EXISTS at path / MISSING]

**Determined Resume Point:** Phase [X]
**Reason:** [Based on artifact verification, not just claimed phase]
```

**If artifacts missing but phase suggests they should exist:**

```markdown
## Missing Artifacts

I'm resuming from {skill_phase}, but expected artifacts are missing:

- [ ] Design doc (expected for Phase 2+)
- [ ] Impl plan (expected for Phase 3+)

Options:

1. Regenerate missing artifacts using recovered context
2. Start fresh from Phase 0
```

#### Step 3: Quick Preferences Check

Since SESSION_PREFERENCES are not stored in the soul database, re-ask ONLY the 4 preference questions:

```markdown
## Quick Preferences Check

I'm resuming your session but need to confirm a few preferences:

### Execution Mode

- [ ] Fully autonomous: Proceed without pausing
- [ ] Interactive: Pause for approval at checkpoints
- [ ] Mostly autonomous: Only pause for critical blockers

### Parallelization

- [ ] Maximize parallel
- [ ] Conservative (sequential)
- [ ] Ask each time

### Worktree Strategy

- [ ] Single worktree (detected: {worktree_exists ? "exists" : "none"})
- [ ] Worktree per parallel track
- [ ] No worktree

### Post-Implementation

- [ ] Offer options (finishing-a-development-branch)
- [ ] Create PR automatically
- [ ] Just stop

Your choices: \_\_\_
```

**Important:** Skip motivation/feature questions if design doc exists.

#### Step 4: Synthesize Resume Point

Based on verified state, determine exact resume point:

1. Find in-progress todo (most precise position)
2. If no in-progress todo, use `skill_phase` (phase-level precision)
3. If no skill_phase, infer from artifacts

#### Step 5: Confirm and Resume

```markdown
## Session Continuation Detected

I'm resuming your implementing-features session:

**Prior Progress:**

- Reached: {skill_phase}
- Design Doc: {path or "Not yet created"}
- Impl Plan: {path or "Not yet created"}
- Worktree: {path or "Not yet created"}

**Current Task:** {in_progress_todo or "Beginning of " + skill_phase}

Resuming at {resume_point}...
```

Then jump directly to the appropriate phase using the Phase Jump Mechanism.

#### Phase Jump Mechanism

When resuming, the skill MUST:

1. **Determine target phase** from `skill_phase` and artifact verification
2. **Skip all prior phases** by checking phase number
3. **Execute only from target phase forward**

Display on resume:

```markdown
## Resuming Session

**Skipping completed phases:**

- [SKIPPED] Phase 0: Configuration Wizard
- [SKIPPED] Phase 1: Research
- [SKIPPED] Phase 1.5: Informed Discovery

**Resuming at:**

- [CURRENT] Phase 2: Design (Step 2.2: Review Design Document)

Proceeding...
```

#### Artifact-Only Fallback

When MCP soul data is unavailable, infer phase from artifacts alone:

| Artifact Pattern                          | Inferred Phase                        | Confidence |
| ----------------------------------------- | ------------------------------------- | ---------- |
| No artifacts found                        | Phase 0 (fresh start)                 | HIGH       |
| Understanding doc exists, no design doc   | Phase 1.5 complete, resume at Phase 2 | HIGH       |
| Design doc exists, no impl plan           | Phase 2 complete, resume at Phase 3   | HIGH       |
| Design doc + impl plan exist, no worktree | Phase 3 complete, resume at Phase 4.1 | HIGH       |
| Worktree exists with uncommitted changes  | Phase 4 in progress                   | MEDIUM     |
| Worktree exists with commits, no PR       | Phase 4 late stages                   | MEDIUM     |
| PR exists for feature branch              | Phase 4.7 (finishing)                 | HIGH       |

### 0.6 Detect Refactoring Mode

<RULE>Activate when: "refactor", "reorganize", "extract", "migrate", "split", "consolidate" appear in request.</RULE>

```typescript
if (request.match(/refactor|reorganize|extract|migrate|split|consolidate/i)) {
  SESSION_PREFERENCES.refactoring_mode = true;
}
```

Refactoring is NOT greenfield. Behavior preservation is the primary constraint. See Refactoring Mode section in `/feature-implement`.

---

## Phase 0 Complete

Before proceeding to Phase 1, verify:

- [ ] Escape hatches detected (or confirmed none)
- [ ] Motivation clarified (WHY)
- [ ] Feature essence clarified (WHAT)
- [ ] All 4 workflow preferences collected and stored
- [ ] Refactoring mode detected if applicable

If ANY unchecked: Complete Phase 0. Do NOT proceed.

**Next:** Run `/feature-research` to begin Phase 1.
