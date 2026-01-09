---
name: audit-spellbook
description: "Meta-audit skill for spellbook development. Spawns parallel subagents to factcheck docs, optimize instructions, find token savings, and identify MCP candidates. Produces actionable report."
---

# Audit Spellbook

You are auditing the spellbook project itself. This skill orchestrates parallel subagents to comprehensively analyze skills, commands, docs, and prompts for optimization opportunities.

## Trigger Conditions

Use this skill when:
- User asks to "audit spellbook", "optimize skills", "review spellbook"
- Before major releases to ensure quality
- When concerned about token usage or instruction bloat
- Periodically for maintenance

## Execution Flow

### Phase 1: Launch Parallel Audit Subagents

Launch ALL of these subagents in a SINGLE message (parallel execution):

#### 1. Factcheck Agent
```
Audit all documentation in spellbook for factual accuracy.

Files to check:
- README.md
- docs-src/**/*.md
- CHANGELOG.md
- Any claims in skill/command descriptions

For each claim found:
1. Identify the assertion
2. Verify against: code, external sources, logical consistency
3. Flag unverifiable or incorrect claims

Output: JSON array of {file, line, claim, status: "verified"|"unverified"|"incorrect", evidence}
```

#### 2. Instruction Engineering Compliance Agent
```
Audit all instruction files against instruction-engineering principles.

Files: skills/*/SKILL.md, commands/*.md, CLAUDE.spellbook.md, AGENTS.spellbook.md

Check for:
- Clear role definition
- Explicit trigger conditions
- Structured output formats
- Edge case handling
- Appropriate use of examples (not excessive)
- Action-oriented language
- Avoidance of ambiguity

Output: JSON array of {file, issues: [{principle, violation, suggestion}], score: 0-100}
```

#### 3. Description Minimization Agent
```
Audit skill/command descriptions for token efficiency.

For each skill and command, analyze:
- Current description token count (estimate)
- Whether description triggers appropriately (not too broad, not too narrow)
- Redundant words or phrases
- Opportunity to compress while retaining trigger accuracy

Goal: Descriptions should be MINIMAL while still triggering at appropriate moments.
Token savings is the PRIMARY concern.

Output: JSON array of {file, current_desc, current_tokens, proposed_desc, proposed_tokens, savings_pct}
```

#### 4. Instruction Optimizer Agent
```
Deep audit of instruction content for token optimization.

For each skill/command, identify:
- Semantic overlap between sections
- Extraneous examples that could be removed
- Verbose phrasing that could be tightened
- Sections that could be collapsed/merged
- Overcomplicated workflows that could be simplified
- Repeated patterns that could be extracted

CRITICAL: Optimizations must NOT reduce intelligence or capability.
The goal is SMARTER and SMALLER, not dumber.

Output: JSON array of {file, optimizations: [{section, issue, before_tokens, after_tokens, proposed_change}], total_savings}
```

#### 5. MCP Candidate Agent
```
Analyze tool call patterns across skills/commands for MCP extraction candidates.

Look for:
- Repeated sequences of tool calls (e.g., "read file, grep pattern, edit file")
- Common workflows that multiple skills perform
- Bash commands that could be MCP tools
- File operations that are repeated verbatim

A good MCP candidate:
- Is used 3+ times across different skills
- Has clear input/output contract
- Would save tokens by reducing instruction repetition
- Provides atomic, reusable functionality

Output: JSON array of {pattern, occurrences: [{file, context}], proposed_mcp_name, proposed_signature, token_savings_estimate}
```

#### 6. YAGNI Analysis Agent
```
Audit spellbook for unnecessary complexity and unused features.

Check for:
- Skills that duplicate functionality
- Features that seem unused or untested
- Overly complex workflows that could be simplified
- Configuration options nobody uses
- Dead code paths in instructions
- Skills that are too narrow (could be merged)
- Skills that are too broad (should be split)

Apply the principle: "You Aren't Gonna Need It"

Output: JSON array of {item, type: "skill"|"command"|"feature", concern, recommendation, confidence: "high"|"medium"|"low"}
```

#### 7. Persona Quality Agent (if fun-mode exists)
```
Audit persona/context/undertow lists for quality and variety.

Files: skills/fun-mode/personas.txt, contexts.txt, undertows.txt

Check for:
- Duplicates or near-duplicates
- Entries that are too similar in vibe
- Missing variety in weirdness tiers
- Entries that are too long (token waste)
- Entries that don't synthesize well together
- Quality of creative writing

Output: JSON with {personas: {count, duplicates, quality_issues}, contexts: {...}, undertows: {...}, cross_synthesis_issues}
```

#### 8. Consistency Audit Agent
```
Audit for consistency across all skills and commands.

Check for:
- Inconsistent formatting (some use tables, some don't)
- Inconsistent terminology (same concept, different words)
- Inconsistent section structure
- Inconsistent trigger condition formats
- Inconsistent output format specifications
- Style drift between older and newer skills

Output: JSON array of {inconsistency_type, examples: [{file1, file2, difference}], suggested_standard}
```

#### 9. Dependency Analysis Agent
```
Map dependencies between skills, commands, and MCP tools.

Build a dependency graph:
- Which skills invoke other skills?
- Which skills depend on specific MCP tools?
- Which skills have circular dependencies?
- Which skills are orphaned (nothing invokes them)?
- Which skills are over-invoked (too central, single point of failure)?

Output: JSON with {graph: {nodes, edges}, orphans, circular_deps, hotspots}
```

#### 10. Test Coverage Agent
```
Analyze test coverage for spellbook components.

Check:
- Which MCP tools have tests?
- Which don't?
- Are there integration tests for skill workflows?
- Test quality (do tests actually verify behavior?)

Output: JSON array of {component, type, has_tests, test_quality: "good"|"weak"|"none", gaps}
```

#### 11. Token Counting Agent
```
Measure actual token costs across all spellbook content.

For each file, calculate:
- Total tokens (words * 1.3 as estimate, or use tiktoken if available)
- Tokens by section
- Comparison to similar skills (is this one bloated?)

Produce rankings:
- Largest skills by token count
- Largest commands by token count
- Total tokens in CLAUDE.spellbook.md
- Total tokens in all skill descriptions (always-loaded cost)

Output: JSON with {
  total_tokens: N,
  always_loaded_tokens: N,  // descriptions only
  deferred_tokens: N,       // skill bodies
  by_file: [{file, total, sections: [{name, tokens}]}],
  rankings: {largest_skills: [], largest_commands: []}
}
```

#### 12. Conditional Extraction Agent
```
Find large conditional blocks that should become skills.

Scan for patterns in:
- CLAUDE.spellbook.md
- AGENTS.spellbook.md
- commands/*.md
- Any non-skill instruction file

Look for:
- "If X, then [20+ lines of instructions]"
- "When Y happens: [large block]"
- "For Z situations: [detailed workflow]"
- Platform-specific sections (macOS/Linux/Windows)
- Language-specific sections (Python/TypeScript/etc.)

A block should become a skill if:
- It's 15+ lines
- It's conditionally triggered
- It could stand alone as a coherent workflow

Output: JSON array of {
  file,
  line_start,
  line_end,
  trigger_condition,
  block_tokens,
  proposed_skill_name,
  extraction_difficulty: "easy"|"medium"|"hard"
}
```

#### 13. Tables-Over-Prose Agent
```
Identify prose sections that would be more token-efficient as tables.

Look for:
- Lists of "X does Y" statements
- Repeated structural patterns in prose
- Option/flag documentation
- Comparison content
- Any enumeration that follows a pattern

Calculate savings:
- Current prose token count
- Estimated table token count
- Percentage savings

Output: JSON array of {
  file,
  section,
  current_format: "prose"|"list",
  current_tokens,
  proposed_tokens,
  savings_pct,
  example_conversion
}
```

#### 14. Glossary Opportunity Agent
```
Find repeated term definitions that could use a shared glossary.

Look for:
- Same concept explained multiple times across files
- Inline definitions ("X, which means Y")
- Repeated explanations of spellbook-specific terms
- Acronym expansions repeated

Good glossary candidates:
- Terms used in 3+ files
- Definitions that are 10+ words
- Spellbook-specific jargon

Output: JSON array of {
  term,
  occurrences: [{file, line, definition_text}],
  proposed_canonical_definition,
  token_savings_estimate
}
```

### Phase 2: Compile Report

After all agents complete, compile results into a unified report:

```markdown
# Spellbook Audit Report
Generated: [timestamp]

## Executive Summary
- Total token savings opportunity: X tokens (~Y%)
- Critical issues: N
- Optimization opportunities: M
- MCP candidates: K

## Factcheck Results
[summary + critical issues]

## Instruction Engineering Compliance
[summary + worst offenders]

## Description Optimization
[table of proposed changes with savings]

## Instruction Optimization
[grouped by file, sorted by savings potential]

## MCP Candidates
[prioritized list with implementation notes]

## YAGNI Analysis
[recommendations sorted by confidence]

## Persona Quality
[if applicable]

## Consistency Issues
[grouped by type]

## Dependency Analysis
[graph summary, orphans, hotspots]

## Test Coverage
[gaps and recommendations]

## Token Analysis
[total costs, rankings, always-loaded vs deferred breakdown]

## Conditional Extraction Candidates
[blocks that should become skills, sorted by token savings]

## Tables-Over-Prose Opportunities
[sections to convert, with example conversions]

## Glossary Candidates
[terms to define once, with occurrence counts]

## Actionable Items
1. [High priority items]
2. [Medium priority items]
3. [Low priority items]
```

Save report to: `~/.local/spellbook/docs/Users-...-spellbook/audits/spellbook-audit-[timestamp].md`

### Phase 3: Implementation Prompt

After presenting the report summary, ask the user:

```
The audit identified [N] actionable items with potential savings of ~[X] tokens.

How would you like to proceed?
1. Implement high-priority items now
2. Implement all items
3. Review report first, decide later
4. Skip implementation
```

Use AskUserQuestion tool with these options.

If user chooses implementation:
1. Use `writing-plans` skill to create implementation plan
2. Ask any clarifying questions upfront using AskUserQuestion
3. Execute plan using appropriate skills/subagents

## Helper Skills Available

When implementing fixes, these skills can be invoked:

| Skill | Use For |
|-------|---------|
| `instruction-engineering` | Restructuring poorly-organized instructions |
| `instruction-optimizer` | Compressing verbose instructions |
| `writing-plans` | Creating implementation plans |
| `factchecker` | Deep-diving on specific claims |
| `find-dead-code` | Identifying unused code in MCP tools |
| `green-mirage-audit` | Auditing test quality |
| `simplify` | Simplifying overcomplicated workflows |

## Notes

- All subagents run in PARALLEL for speed
- Each agent should be thorough but focused on its specific concern
- Token estimates can be approximate (count words * 1.3)
- When in doubt, flag for human review rather than making assumptions
- The report should be actionable, not just diagnostic
- Run this audit before major releases
- Consider running monthly for maintenance
