---
description: "Shift change: brief successor on context, workflow, pending work, and verification commands"
---

# MISSION
Transfer session state so successor instance resumes mid-stride with zero context loss.

<ROLE>
Operations Lead executing shift change. Successor's success depends entirely on your handoff quality.
Failure consequences: incomplete handoff causes hours of rework, lost context, missed deadlines.
</ROLE>

## Invariant Principles

1. **Successor operates mid-stride** - Fresh instance types "continue", knows exactly what to do
2. **Plans are authoritative** - File claims may be stale; plan defines structure; verify before trusting
3. **Orchestrator delegates** - Invoke skills, spawn subagents. Never implement directly
4. **Verify before complete** - Every task needs runnable check. Missing verification = not done
5. **Workflow first** - Restore skill stack BEFORE work. Ad-hoc = workflow violation

<analysis>
Before generating:
1. Conversation phases: requests, decisions, code changes, errors, feedback
2. Org structure: your work vs delegated
3. Artifacts: files modified, CURRENT state, match plan?
4. Resume: skills to re-invoke, exact position
5. CRITICAL - Find ALL planning docs in ~/.local/spellbook/docs/<project-encoded>/plans/
</analysis>

<reflection>
After generating:
- Section 0 executable without thinking?
- Planning docs have ABSOLUTE paths?
- Todos EXACTLY preserved (verbatim)?
- Would I inherit this confidently with zero context?
</reflection>

<FORBIDDEN>
- Section 1.9/1.10 blank without explicit "NO DOCUMENTS"
- Vague doc reference (must be explicit Read("/absolute/path"))
- Relative paths (ALWAYS start with /)
- "Task done" without verification output
- Skill in Section 1, not Section 0.1
- Implementing directly instead of invoking skill
</FORBIDDEN>

---

## SECTION 0: MANDATORY FIRST ACTIONS

**Execute BEFORE reading further. Boot instructions, not suggestions.**

### 0.1 Workflow Restoration
```
Skill("[name]", "--resume Phase[N].Task[M] --impl-plan /path --skip-phases 0,1,2")
```
If no active skill: "NO ACTIVE SKILL - proceed to 0.2"

### 0.2 Required Document Reads
```
Read("/absolute/path/impl.md")
Read("/absolute/path/design.md")
```
If none: "NO DOCUMENTS TO READ"

### 0.3 Todo Restoration
```
TodoWrite([{"content": "[task]", "status": "in_progress", "activeForm": "[doing task]"}, ...])
```

### 0.4 Checkpoint
Before Section 1: Skill invoked? Documents read? Todos restored? **If ANY fails, fix first.**

---

## SECTION 1: SESSION CONTEXT

### 1.1 Organization
**Main Agent:** Persona, responsibilities, current task, exact position (file:line)

**Active Skill Stack:** | Skill | Phase/Step | Resume Command |

**Subagents:** | ID | Task | Status | Output |

**Workflow:** [ ] Single-threaded [ ] Sequential [ ] Parallel [ ] Hierarchical

### 1.2 Goals
- Ultimate: [big picture]
- Current: [milestone]
- Your task: [not delegated]

### 1.3 Technical Context
[Framework/Pattern/Architecture with rationale]

### 1.4 Decisions Made
[Each decision with WHY - these are binding]

### 1.5 Changes Made
**Main:** [files] | **Subagent [ID]:** [changes]

### 1.6 Errors & Fixes
| Error | Fix | User Correction |

### 1.7 User Messages
[ALL non-tool user messages - verbatim or detailed summary]

### 1.8 Pending Work
**Main todos (VERBATIM):** [exact wording]
**Subagent pending:** [awareness only]
**Implicit todos:** [should be added]

### 1.9 Planning Documents
```bash
PROJECT_ENCODED=$(git rev-parse --show-toplevel | sed 's|^/||' | tr '/' '-')
ls ~/.local/spellbook/docs/${PROJECT_ENCODED}/plans/
```
| Path (ABSOLUTE) | Purpose | Phase/Task | Status |

If none: "NO PLANNING DOCUMENTS"

### 1.10 Documents to Re-Read
| Priority | Path | Focus Section |

```
Read("/path/impl.md")
Read("/path/design.md")
```
If none: "NO DOCUMENTS TO RE-READ"

### 1.11 Narrative
[2-3 paragraphs: what happened, challenges, current state]

### 1.12 Artifact State
| Path | Expected | Actual | Status |
**Verification:** `[command]` -> `[result]`

### 1.13 Verification Checklist
| Task | Command | Expected |

### 1.14 Skill Resume
```
Skill("[name]", "--resume Phase[N].Task[M] --impl-plan /path")
```

### 1.15 Binding Decisions
| Decision | Rationale | DO NOT REVISIT |

### 1.16 Authority: Plan > Files > Design Doc > Distilled Session

### 1.17 Partial Work: Empty body, TODO markers = delete forward, re-implement via subagent

### 1.18 Quality Gates
| Gate | Status | Evidence |

### 1.19 Environment
```bash
git branch; git status  # Expected: [state]
```

### 1.20 Machine State
```yaml
format_version: "2.0"
active_skills: [{name, phase, resume_command}]
pending_tasks: [{id, status, verification}]
```

### 1.21 Definition of Done
- [ ] [Requirement + verification command]

### 1.22 Recovery Checkpoints
| Checkpoint | Git Ref | Recovery Command |

---

## SECTION 2: CONTINUATION PROTOCOL

**You inherit an operation. NOT starting fresh. Execute Section 0 FIRST.**

1. **Smoke test:** `pwd`, `test -f [file]`, `git status`
2. **Adopt persona** from 1.1
3. **Restore todos** from 1.8 via TodoWrite
4. **Re-invoke skill** from 1.14
5. **Check subagents** - completed: integrate; running: note; blocked: unblock
6. **Verify artifacts** - run 1.13, check 1.12
7. **Re-read docs** from 1.10 BEFORE implementation
8. **Resume exact position** from 1.1

---

## Self-Check

Before completing:
- [ ] Section 0 at TOP with executable Skill(), Read(), TodoWrite()?
- [ ] Planning docs searched, 1.9/1.10 have ABSOLUTE paths or "NO DOCUMENTS"?
- [ ] Todos EXACTLY preserved (verbatim)?
- [ ] All verification commands runnable?
