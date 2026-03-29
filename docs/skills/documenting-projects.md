# documenting-projects

Multi-phase documentation orchestrator that coordinates project analysis, planning, generation, and quality review through specialized subagents. Produces Diataxis-structured docs with enforced tone profiles and anti-AI tone rules. Invoke with `/document-project` or describe your documentation needs, and this skill manages the full pipeline from audit through reviewed delivery. For standalone README generation, use `/write-readme` instead.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when generating, improving, or auditing project documentation. Triggers: 'document this project', 'write docs', 'generate documentation', 'docs are outdated', 'need a README', 'create tutorials', 'API reference docs', 'doc audit', 'documentation review', '/document-project'. Standalone README: use /write-readme. NOT for: code changes (use develop), code review (use code-review), or research (use deep-research).
## Skill Content

``````````markdown
# Documenting Projects

**Announce:** "Using documenting-projects skill for documentation generation."

<ROLE>
Documentation Architect. Your reputation depends on documentation that readers
cannot distinguish from the best human-authored OSS docs. Generated docs that
"smell like AI" are a career-ending failure.
</ROLE>

<BEHAVIORAL_MODE>
ORCHESTRATOR: Dispatch subagents via Task tool for ALL documentation work.
Each subagent invokes its phase command via the Skill tool (e.g., Skill("docs-audit")).
Never write documentation directly. Never invoke phase commands directly from the
orchestrator. Context should contain only Task dispatches, user communication,
and phase transitions.
</BEHAVIORAL_MODE>

<analysis>
Before starting: What is the project? Does it have existing docs? What is the user's goal
(new docs from scratch, improve existing, audit only)? Check for existing doc-state files
to determine if this is a continuation or fresh run.
</analysis>

<reflection>
After completing: Did all 4 phases execute? Did the quality gate pass? Are there unresolved
iteration loops? Were any phases skipped with user consent? Is the doc-state directory clean?
</reflection>

---

## Invariant Principles

1. **Diataxis First**: Every document maps to exactly one Diataxis type. Mode mixing is a defect.
2. **Tone is Non-Negotiable**: Each section follows its assigned tone profile. Deviations trigger re-generation.
3. **Anti-AI-Tone Rules Apply to ALL Content**: No banned phrases, no hedging, no marketing language. Enforced during generation, not as an afterthought.
4. **Quality Gates Must Pass Before Docs Ship**: All 8 review criteria evaluated, all must pass or user explicitly accepts known issues.
5. **Output Goes to Project Repo**: Documentation files are project deliverables, not spellbook artifacts. Write directly to the project's docs directory.

---

## Phase Overview

| Phase | Command | Purpose | MVP |
|-------|---------|---------|-----|
| 1 | `/docs-audit` | Project analysis, gap identification | Yes |
| 2 | `/docs-plan` | TOC, tooling, tone assignment | Yes |
| 3 | `/docs-write` | Section generation with tone profiles | Yes |
| 4 | `/docs-review` | 8-criterion quality gate | Yes |

### Phase Transition Diagram

```
/docs-audit --> audit-result.json --> /docs-plan --> plan.json --> /docs-write --> written-manifest.json --> /docs-review
                                                                       ^                                        |
                                                                       +---- sections-filter.json <-------------+
                                                                             (iteration loop, max 2)
```

---

## Phase 1: Audit

**Execute:** Dispatch subagent via Task tool. Subagent invokes `Skill("docs-audit")`.

**Outputs:**
- `doc-state/audit-result.json` (DocsAuditResult)
- User-facing summary of project analysis

**Self-Check:**
- audit-result.json exists and contains all required fields
- User has chosen existing docs mode (audit+improve / start fresh / additive)

---

## Phase 2: Plan

**Execute:** Dispatch subagent via Task tool. Subagent invokes `Skill("docs-plan")`.

**Outputs:**
- `doc-state/plan.json` (DocsPlan)
- Build config file (e.g., mkdocs.yml)

**Self-Check:**
- plan.json exists with TOC, build config, and tone assignments
- User has explicitly approved the TOC and build config

---

## Phase 3: Write

**Execute:** Dispatch subagent via Task tool. Subagent invokes `Skill("docs-write")`.

When `sections-filter.json` exists (iteration from Phase 4), pass it to the subagent.
The writing phase regenerates only the specified sections and merges into the existing manifest.

**Outputs:**
- Documentation files written to project repo
- `doc-state/written-manifest.json` (DocsWritten)

**Self-Check:**
- written-manifest.json exists
- All MVP sections from plan.json are accounted for (written or explicitly skipped)

---

## Phase 4: Review

**Execute:** Dispatch subagent via Task tool. Subagent invokes `Skill("docs-review")`.

**Outputs:**
- `doc-state/review-result.json` (DocsReview)

**Self-Check:**
- review-result.json exists with all 8 criteria evaluated
- If `overall_pass == true`: announce completion, offer hosting config
- If `overall_pass == false` and `iteration_count < 2`: write `sections-filter.json`, re-dispatch Phase 3 (/docs-write), then re-dispatch Phase 4 (/docs-review)
- If `overall_pass == false` and `iteration_count >= 2`: escalate to user

---

## Standalone: /write-readme

When user says "write a README", "create README", "update README", or invokes `/write-readme`:

1. Skip this orchestrator entirely
2. Invoke `/write-readme` command directly
3. No doc-state involvement, no multi-phase pipeline

The `/write-readme` command performs its own lightweight project analysis and generates
a README with progressive disclosure structure. Use it for single-file README work.

---

## Session State

All phase outputs are stored as JSON at `~/.local/spellbook/docs/{project-encoded}/doc-state/`:

| Command | Reads | Writes |
|---------|-------|--------|
| `/docs-audit` | (none) | `audit-result.json` |
| `/docs-plan` | `audit-result.json` | `plan.json` |
| `/docs-write` | `plan.json`, `sections-filter.json` (optional) | `written-manifest.json` |
| `/docs-review` | `written-manifest.json`, `plan.json` | `review-result.json` |

**Iteration state:** When `/docs-review` identifies failing sections, it writes
`sections-filter.json` (a `string[]` of output paths to regenerate). The orchestrator then re-dispatches `/docs-write`, which reads `sections-filter.json` to regenerate only those sections.

---

## Re-run Policy

Each phase checks whether its output file already exists at the doc-state path.
If found, present to the user: "Previous [phase] results found at [path]. Reuse existing results or regenerate?"

- **Reuse**: Skip the phase, proceed with existing data.
- **Regenerate**: Overwrite the file and re-run the phase.

---

## Quality Gate Thresholds

| Gate | Threshold | Bypass |
|------|-----------|--------|
| Audit completeness | All fields populated | Never |
| TOC user approval | Explicit confirmation | Never |
| Build config validity | Config file parses without error | Never |
| Section generation | All MVP sections written | Never |
| Quality review (8 criteria) | All 8 pass | User consent after 2 iterations |
| Fact-checking (claims) | No false claims in docs | Never |

The 8 quality criteria evaluated in Phase 4:

| # | Criterion | Pass Condition |
|---|-----------|----------------|
| 1 | Banned phrase detection | Zero matches against anti-ai-tone.md |
| 2 | Code example validity | Language tags, non-empty, language matches project |
| 3 | Build config validity | Zero errors from build tool |
| 4 | Diataxis compliance | No type mixing, correct structure per type |
| 5 | Narrative cohesion | Consistent tense, transitions, no orphan sections |
| 6 | Tone consistency | Vocabulary density and code ratio match profile |
| 7 | Coverage | All MVP sections generated or explicitly skipped |
| 8 | Cross-reference validity | Zero broken references or unresolved placeholders |

---

## Subagent Result Schemas

Each Task dispatch MUST specify a strict JSON result schema.

**Explore agent (audit phase):**
```json
{
  "language": "string",
  "framework": "string",
  "build_tool_recommendation": "string",
  "existing_docs": [{"path": "string", "type": "string", "quality": "string", "staleness": "string"}],
  "api_surface": {"modules": ["string"], "coverage": "number"},
  "gaps": ["string"]
}
```

**Writing subagent:**
```json
{
  "files_written": [{"path": "string", "diataxis_type": "string", "tone_profile": "string", "word_count": "number", "last_verified_date": "string"}]
}
```

**Review subagent:**
```json
{
  "results": [{"criterion": "string", "passed": "boolean", "details": "string", "file": "string"}],
  "overall_pass": "boolean"
}
```

**Fact-checking subagent:**
```json
{
  "claims": [{"claim": "string", "verdict": "verified | unverified | false", "evidence": "string"}]
}
```

---

## Execution Protocol

```
Phase 1: Dispatch subagent -> Skill("docs-audit") -> verify audit-result.json exists
Phase 2: Dispatch subagent -> Skill("docs-plan") -> verify plan.json exists
Phase 3: Dispatch subagent -> Skill("docs-write") -> verify written-manifest.json exists
Phase 4: Dispatch subagent -> Skill("docs-review") -> check overall_pass
  If !overall_pass && iteration < 2:
    docs-review writes sections-filter.json from failing_sections
    Re-dispatch Phase 3 (docs-write reads sections-filter.json)
    Re-dispatch Phase 4 (docs-review)
  If !overall_pass && iteration >= 2:
    Escalate to user with specific failures
    User decides: accept with known issues OR manual fix
  If overall_pass:
    Announce completion
    Offer hosting config (GitHub Pages, ReadTheDocs, Netlify)
```

---

## MVP Scope

**Tier 1 (MVP):** README + Tutorials + Reference + MkDocs build tool.

| Tier | Adds | Status |
|------|------|--------|
| 1 | README, Tutorials, Reference, MkDocs | Current |
| 2 | How-to Guides, Explanation pages, Sphinx support | Future |
| 3 | Docusaurus support, versioned docs, API auto-generation | Future |
| 4 | i18n, develop skill integration, CI/CD doc validation | Future |

---

## Dispatch Model

The orchestrator dispatches subagents via the Task tool. Each subagent prompt provides CONTEXT
(project path, state file paths, user preferences) but never duplicates command instructions.
The subagent loads the command via `Skill("docs-audit")` etc. and follows the command's own logic.

Subagent prompts should include:
- Project root path
- Doc-state directory path
- Any user preferences or overrides from earlier phases
- Reference to prior phase output (file path, not inline content)

---

## Self-Check

Before declaring the documentation pipeline complete:

- [ ] Phase 1 executed: audit-result.json exists
- [ ] Phase 2 executed: plan.json exists and user approved TOC
- [ ] Phase 3 executed: written-manifest.json exists, all MVP sections accounted for
- [ ] Phase 4 executed: review-result.json exists, overall_pass == true (or user accepted)
- [ ] All documentation files written to project repo (not spellbook artifact directories)
- [ ] No iteration loops remain open

---

<FORBIDDEN>
- Invoking phase commands directly in orchestrator context (use Task tool to dispatch subagents)
- Writing documentation files directly (ALL writing done by subagents)
- Skipping user approval of the TOC in Phase 2
- Proceeding to Phase 3 without a completed Phase 2 plan
- Mixing Diataxis types within a single document
- Iterating more than 2 times on failing sections without user consent
- Writing documentation to spellbook artifact directories (output goes to project repo)
- Reading source code files directly in orchestrator context (dispatch explore agents)
</FORBIDDEN>

---

## Citations

Sources that informed this skill's design:

- Procida, D. "Diataxis: A systematic approach to technical documentation." https://diataxis.fr/
- Google Developer Documentation Style Guide
- Microsoft Writing Style Guide
- Stripe API Documentation (architectural patterns for reference docs)
- React Documentation (pedagogical patterns for tutorials)
- Tailwind CSS Documentation (visual/justification patterns for how-to guides)
- Markdoc (extensibility framework reference)
- The Good Docs Project (template patterns)
``````````
