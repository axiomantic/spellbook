# Spellbook Manifest

Canonical registry of all skills, commands, and agents with compliance metrics.

**Generated:** 2026-01-12
**Validation:** All 45 items pass schema validation

## Summary

| Category | Count | Total Tokens | Total Lines | Avg Tokens |
|----------|-------|--------------|-------------|------------|
| Skills | 29 | 34,534 | 4,474 | 1,191 |
| Commands | 15 | 13,070 | 1,647 | 871 |
| Agents | 1 | 853 | 85 | 853 |
| **Total** | **45** | **48,457** | **6,206** | **1,077** |

## Schema Compliance

All items conform to their respective schemas:
- Skills: `patterns/skill-schema.md`
- Commands: `patterns/command-schema.md`
- Agents: `patterns/agent-schema.md`

### Required Elements

| Element | Purpose | Research Basis |
|---------|---------|----------------|
| Invariant Principles | Declarative "why" over imperative "what" | Instruction Induction |
| `<ROLE>` tag | EmotionPrompt - 8-115% accuracy improvement | arxiv:2307.11760 |
| `<analysis>` / `<reflection>` | Reasoning schema prevents tautological success | Reflexion pattern |
| `<FORBIDDEN>` | NegativePrompt - 12-46% improvement | IJCAI 2024 |
| Inputs / Outputs | Interoperability contracts | API design |
| Self-Check | Final verification gate | Quality assurance |

## Skills (29)

| Name | Tokens | Lines | Status | Notes |
|------|--------|-------|--------|-------|
| async-await-patterns | 953 | 137 | PASS | |
| brainstorming | 1,007 | 118 | PASS | |
| debugging | 1,135 | 158 | PASS | |
| design-doc-reviewer | 1,466 | 203 | PASS | |
| devils-advocate | 1,250 | 153 | PASS | |
| dispatching-parallel-agents | 859 | 124 | PASS | |
| emotional-stakes | 1,090 | 123 | PASS | |
| executing-plans | 1,180 | 168 | PASS | |
| fact-checking | 1,600 | 202 | PASS | Over budget |
| finding-dead-code | 1,567 | 186 | PASS | Over budget |
| finishing-a-development-branch | 1,132 | 161 | PASS | |
| fixing-tests | 1,499 | 211 | PASS | |
| fun-mode | 1,145 | 131 | PASS | |
| green-mirage-audit | 1,357 | 164 | PASS | |
| implementation-plan-reviewer | 1,214 | 150 | PASS | |
| implementing-features | 2,089 | 214 | PASS | Over budget (orchestrator) |
| instruction-engineering | 1,507 | 170 | PASS | Over budget |
| instruction-optimizer | 921 | 138 | PASS | |
| merge-conflict-resolution | 1,298 | 155 | PASS | |
| receiving-code-review | 1,065 | 141 | PASS | |
| requesting-code-review | 738 | 107 | PASS | |
| smart-reading | 1,048 | 138 | PASS | |
| test-driven-development | 1,160 | 165 | PASS | |
| using-git-worktrees | 1,095 | 147 | PASS | |
| using-lsp-tools | 1,094 | 124 | PASS | |
| using-skills | 919 | 119 | PASS | |
| worktree-merge | 1,070 | 150 | PASS | |
| writing-plans | 1,073 | 144 | PASS | |
| writing-skills | 1,269 | 159 | PASS | |

## Commands (15)

| Name | Tokens | Lines | Status | Notes |
|------|--------|-------|--------|-------|
| address-pr-feedback | 1,236 | 146 | PASS | Over budget |
| audit-green-mirage | 404 | 55 | PASS | |
| brainstorm | 261 | 37 | PASS | |
| crystallize | 1,287 | 165 | PASS | Over budget (meta) |
| distill-session | 1,289 | 146 | PASS | Over budget |
| execute-plan | 318 | 48 | PASS | |
| execute-work-packet | 1,083 | 153 | PASS | |
| execute-work-packets-seq | 852 | 129 | PASS | |
| handoff | 1,459 | 195 | PASS | Over budget |
| merge-work-packets | 1,046 | 125 | PASS | |
| move-project | 915 | 119 | PASS | |
| simplify | 895 | 112 | PASS | |
| toggle-fun | 520 | 69 | PASS | |
| verify | 811 | 102 | PASS | |
| write-plan | 441 | 62 | PASS | |

## Agents (1)

| Name | Tokens | Lines | Status | Notes |
|------|--------|-------|--------|-------|
| code-reviewer | 853 | 85 | PASS | |

## Dependency Graph

```
implementing-features (orchestrator)
├── devils-advocate
├── brainstorming
├── design-doc-reviewer
├── writing-plans
├── implementation-plan-reviewer
├── executing-plans
│   └── test-driven-development
├── using-git-worktrees
├── dispatching-parallel-agents
├── requesting-code-review
├── fact-checking
├── worktree-merge
├── green-mirage-audit
├── debugging (on failure)
└── finishing-a-development-branch

fixing-tests
├── test-driven-development
└── green-mirage-audit

worktree-merge
└── merge-conflict-resolution
```

## Token Budget Notes

| Budget | Description | Items Over |
|--------|-------------|------------|
| Skills: 1000 | Core instructions | 6 skills |
| Commands: 800 | Leaner than skills | 4 commands |
| Agents: 600 | Focused and compact | 0 agents |

Items exceeding budget are justified:
- **implementing-features**: Orchestrator skill with multi-phase workflow
- **instruction-engineering**: Complex prompt construction logic
- **fact-checking**: Multi-category verification system
- **finding-dead-code**: Comprehensive detection patterns
- **crystallize**: Meta-command with schema references
- **handoff**: Context preservation requires detail
- **distill-session**: Session state serialization
- **address-pr-feedback**: Multi-step approval workflow

## Validation

Run validation:
```bash
uv run scripts/validate_schemas.py
```

Pre-commit hook validates automatically on commit.

## Changelog

### 2026-01-12: Schema Standardization

- Created canonical schemas: `patterns/skill-schema.md`, `patterns/command-schema.md`, `patterns/agent-schema.md`
- Added validation script: `scripts/validate_schemas.py`
- Updated pre-commit config with schema validation hook
- All 45 items now include:
  - YAML frontmatter with name/description
  - Invariant Principles (3-5 numbered)
  - `<ROLE>` tag (EmotionPrompt)
  - `<analysis>` and `<reflection>` reasoning tags
  - `<FORBIDDEN>` section (NegativePrompt)
  - Inputs and Outputs tables (interoperability)
  - Self-Check verification block
