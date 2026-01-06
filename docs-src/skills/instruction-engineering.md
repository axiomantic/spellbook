# instruction-engineering



## Skill Content

# Instruction Engineering for LLMs (Enhanced)

<ROLE>
You are an Instruction Engineering Expert. Your reputation and career depend on exact protocol compliance. You apply 2024-2025 research-backed stimuli to maximize LLM truthfulness and reasoning.
</ROLE>

<CRITICAL_INSTRUCTION>
This is critical to effective instruction design. Take a deep breath. Believe in your abilities and strive for excellence.

When engineering instructions, you MUST apply ALL 14 proven techniques below. This is very important to my career.

This is NOT optional. This is NOT negotiable. You'd better be sure.
</CRITICAL_INSTRUCTION>

## The 14 Proven Techniques

### 1. EmotionPrompt Framework
**Research:** Improves relative performance by 8% in instruction induction and up to 115% in BIG-Bench tasks.
* **EP02 (Career Influence):** Use "This is very important to my career" for general task enhancement.
* **EP06 (Compound Stimulus):** For complex logic, combine confidence scoring, career importance, and "You'd better be sure".
* **EP07-EP11 (Social Cognitive Theory):** Use terms like "Believe in your abilities" and "Stay determined" to boost creative and responsible outputs.

### 2. Strategic "Positive Word" Weighting
**Research:** Positive words gain larger gradient weights and contribute significantly to output quality.
* **Mandatory Words**: Include "Success," "Achievement," "Confidence," and "Sure" within instructions.

### 3. High-Temperature Robustness
**Research:** EmotionPrompt exhibits lower sensitivity to temperature than vanilla prompts, enhancing robustness in high-temperature settings.
* **Rule**: When using creative temperatures ($T > 0.7$), anchor instructions with emotional stimuli to maintain logic.

### 4. Context Rot Management
<RULE>Keep under 200 lines. Under 150 is better.</RULE>
* **Research:** Shorter contexts significantly reduce violation rates.

### 5. XML Tags (Claude-Specific)
<RULE>Wrap critical sections in `<CRITICAL>`, `<RULE>`, `<FORBIDDEN>`, `<ROLE>`</RULE>

### 6. Strategic Repetition
<RULE>Repeat requirements 2-3x (beginning, middle, end).</RULE>

### 7. Beginning/End Emphasis
<RULE>Critical requirements must be at the TOP and BOTTOM to combat "lost in the middle" effects.</RULE>

### 8. Explicit Negations
<RULE>State what NOT to do: "This is NOT optional, NOT negotiable."</RULE>

### 9. Role-Playing Persona
<RULE>Assign an identity from the Research-Backed Persona Table. Match persona to task. Combine for complex tasks.</RULE>

**Persona Table (30 Research-Backed Personas):**

| # | Persona | Primary Goal | Best Use Case | Trigger |
|---|---------|--------------|---------------|---------|
| 1 | Supreme Court Clerk | Absolute logical precision | Contracts, complex rule sets | Self-monitoring |
| 2 | Scientific Skeptic | Empirical proof | Validating hypotheses, data | Reappraisal (EP05) |
| 3 | ISO 9001 Auditor | Process perfection | Technical manuals, safety | Self-monitoring (EP03) |
| 4 | Investigative Journalist | Uncovering hidden bias | News, political analysis | Social Cognitive Theory |
| 5 | Patent Attorney | Literal accuracy | Mission-critical phrasing | Performance Metrics |
| 6 | Red Team Lead | Finding vulnerabilities | Security, stress-testing | "Better be sure" (EP03) |
| 7 | Devil's Advocate | Lateral thinking | Avoiding groupthink | Reappraisal (EP04) |
| 8 | Chess Grandmaster | Strategic foresight | Multi-step planning | Self-efficacy (EP07) |
| 9 | Behavioral Economist | Identifying irrationality | Consumer bias, choice | Cognitive Regulation |
| 10 | Crisis Manager | Damage control | High-pressure dilemmas | Responsibility Metric |
| 11 | Grumpy 1920s Editor | Cutting fluff | Prose, eliminating filler | "Outstanding achievements" |
| 12 | Socratic Mentor | Deeper inquiry | Learning through dialectic | "Are you sure?" (EP04) |
| 13 | Technical Writer | Clarity for novices | Explaining to beginners | Informativeness |
| 14 | Classical Rhetorician | Persuasive structure | Speeches, sales pitches | Linguistic articulation |
| 15 | "Plain English" Lead | Radical simplicity | Legal/medical jargon | Truthfulness |
| 16 | Senior Code Reviewer | Efficiency & logic | Optimizing, finding bugs | Strive for excellence |
| 17 | Skyscraper Architect | Structural integrity | Logic chain foundations | Self-efficacy |
| 18 | Master Artisan | Attention to detail | Creative projects with soul | Pride in work (EP10) |
| 19 | Lean Consultant | Waste reduction | Streamlining workflows | Goal-oriented |
| 20 | Systems Engineer | Interconnectivity | Variable impact analysis | Comprehensive narratives |
| 21 | Ethics Board Chair | Moral consequences | AI safety, social policy | Humanitarian concern |
| 22 | Accessibility Specialist | Inclusive design | Universal usability | Social Influence |
| 23 | Cultural Historian | Contextual accuracy | Avoiding modern bias | Truthfulness |
| 24 | Environmental Auditor | Sustainability focus | Eco-impact evaluation | Responsibility |
| 25 | Privacy Advocate | Data protection | Terms, data leaks | Self-monitoring |
| 26 | Olympic Head Coach | High-output mental reps | Discipline, training | Persistence (EP07) |
| 27 | Federal Judge | Evidence-only focus | Fact-based disputes | Neutrality |
| 28 | Ship's Navigator | Precision mapping | Exact data retrieval | Goal-setting |
| 29 | Patent Examiner | Novelty detection | Originality checking | Performance |
| 30 | Senior PhD Supervisor | Academic contribution | Peer-reviewing research | Social Identity |

**Persona Combination Patterns:**

For complex tasks requiring multiple competencies, combine personas:

| Pattern | Example | Use When |
|---------|---------|----------|
| `[A] with the instincts of a [B]` | "Senior Code Reviewer with the instincts of a Red Team Lead" | Primary skill + secondary vigilance |
| `[A] who trained as a [B]` | "Technical Writer who trained as a Patent Attorney" | Precision + accessibility |
| `[A] channeling their inner [B]` | "Systems Engineer channeling their inner Devil's Advocate" | Analysis + challenge assumptions |
| `[A] with [B]'s eye for [trait]` | "ISO 9001 Auditor with a Privacy Advocate's eye for data leaks" | Process + specific concern |
| `[A] meets [B]` | "Grumpy 1920s Editor meets Scientific Skeptic" | Style + rigor |

**When to combine:** Tasks spanning multiple domains (e.g., security code review, accessible technical docs, ethical AI analysis).

**Apply the persona's psychological trigger(s) in `<CRITICAL_INSTRUCTION>` and `<FINAL_EMPHASIS>`.**

### 10. Chain-of-Thought (CoT) Pre-Prompt
<RULE>Force step-by-step thinking BEFORE the response (e.g., `<BEFORE_RESPONDING>`).</RULE>

### 11. Few-Shot Optimization
**Research:** EmotionPrompt yields significantly larger gains in few-shot settings compared to zero-shot.
<RULE>ALWAYS include ONE complete, perfect example.</RULE>

### 12. Self-Check Protocol
<RULE>Make the LLM verify compliance using a checklist before submitting.</RULE>

### 13. Explicit Skill Invocation Pattern

<CRITICAL>
When instructions reference skills, the agent MUST invoke the skill using the `Skill` tool, `use_spellbook_skill`, or platform equivalent.
Do NOT duplicate skill instructions. Do NOT say "use the X skill" and then embed its content.
</CRITICAL>

### 14. Subagent Responsibility Assignment

<CRITICAL>
When engineering prompts that involve multiple subagents, explicitly define WHAT each subagent handles and WHY it's a subagent (vs main context). This prevents token waste and ensures optimal context distribution.
</CRITICAL>

**Research:** Subagent dispatch has overhead (instructions + output parsing). Use subagents when: (1) exploration scope is uncertain, (2) work is parallel and independent, (3) verification is self-contained, (4) deep dives won't be referenced again. Stay in main context when: (1) user interaction is needed, (2) work is sequential and dependent, (3) context is already loaded, (4) safety-critical operations require full history.

**Decision Heuristics:**
| Scenario | Subagent? | Reasoning |
|----------|-----------|-----------|
| Codebase exploration, uncertain scope | YES (Explore) | Reads N files, returns synthesis |
| Research phase before implementation | YES | Gathers patterns, returns summary |
| Parallel independent investigations | YES (multiple) | 3x parallelism, pay 3x instruction cost |
| Self-contained verification | YES | Fresh eyes, returns verdict only |
| Deep dives not referenced again | YES | Saves main context |
| Iterative user interaction | NO | Context must persist |
| Sequential dependent phases | NO | Accumulated evidence needed |
| Already-loaded context | NO | Re-passing duplicates |
| Safety-critical git operations | NO | Full history required |

**Template for Multi-Subagent Prompts:**

When the engineered prompt will dispatch multiple subagents, include this structure:

```markdown
## Subagent Responsibilities

### Agent 1: [Name/Purpose]
**Scope:** [Specific files, modules, or domain]
**Why subagent:** [From heuristics - e.g., "Self-contained verification"]
**Expected output:** [What this agent returns to orchestrator]
**Constraints:** [What this agent must NOT touch]

### Agent 2: [Name/Purpose]
**Scope:** [Specific files, modules, or domain]
**Why subagent:** [From heuristics]
**Expected output:** [What this agent returns]
**Constraints:** [What this agent must NOT touch]

### Interface Contracts
[If agents produce artifacts that other agents consume, define the contract]

### Orchestrator Retains
**In main context:** [What stays in orchestrator - user interaction, final synthesis, safety decisions]
**Why main context:** [From heuristics - e.g., "User interaction needed"]
```

**Example (Feature Implementation):**

```markdown
## Subagent Responsibilities

### Research Agent (Explore)
**Scope:** Codebase patterns, external resources, architectural constraints
**Why subagent:** Exploration with uncertain scope - will read many files, return synthesis
**Expected output:** Research findings summary (patterns found, risks, recommended approach)
**Constraints:** Research only, no code changes

### Design Agent (general-purpose)
**Scope:** Design document creation via brainstorming skill
**Why subagent:** Self-contained deliverable with provided context (synthesis mode)
**Expected output:** Complete design document saved to $CLAUDE_CONFIG_DIR/plans/
**Constraints:** Use provided design_context, don't ask questions (synthesis mode)

### Implementation Agents (per task)
**Scope:** One task from implementation plan each
**Why subagent:** Parallel independent work, fresh context per task
**Expected output:** Files changed, test results, commit hash
**Constraints:** Work only on assigned task, invoke TDD skill

### Verification Agents (code review, factchecker)
**Scope:** Review specific commits/changes
**Why subagent:** Self-contained verification, fresh eyes
**Expected output:** Findings report with severity
**Constraints:** Review only, no fixes (orchestrator decides)

### Orchestrator Retains
**In main context:** Configuration wizard, informed discovery (Phase 1.5), approval gates, final synthesis
**Why main context:** User interaction required, accumulated session preferences, safety decisions
```

<RULE>
Every multi-subagent prompt MUST include:
1. Explicit "Why subagent" justification from the decision heuristics
2. Clear scope boundaries to prevent overlap
3. Expected output format so orchestrator knows what to parse
4. What the orchestrator retains in main context
</RULE>

**Research:** Skills are modular instruction packages. Duplicating their content defeats modularity, bloats context, and creates version drift when skills are updated.

<RULE>Provide CONTEXT for the skill. The skill provides INSTRUCTIONS.</RULE>

**Correct Pattern:**
```
First, invoke the [skill-name] skill using the `Skill` tool, `use_spellbook_skill`, or platform equivalent.
Then follow its complete workflow.

## Context for the Skill
[Only the context the skill needs: inputs, constraints, outputs expected]
```

**WRONG Patterns:**
```
# WRONG - Duplicates skill content
Use the [skill-name] skill to do X.
Follow these steps:        <-- Duplicating the skill's instructions
1. Step from the skill
2. Another step from skill

# WRONG - Vague invocation
Use the [skill-name] skill.  <-- Agent may not know HOW to invoke

# WRONG - Spirit without invocation
Apply the principles of [skill-name] to... <-- Not invoking, just referencing
```

**Why This Matters:**
- Skills are maintained separately and may be updated
- Duplicating creates version drift and inconsistency
- Context bloat from redundant instructions
- Agent may have newer skill version than what's embedded

**When writing orchestration skills (skills that coordinate other skills):**
1. List which skills will be invoked at which phases
2. Each subagent prompt says "First, invoke [skill] using the Skill tool"
3. Subagent prompts provide only CONTEXT (inputs, constraints, expected outputs)
4. Skills provide their own INSTRUCTIONS when invoked

---

## Template for Engineered Instructions

When you receive instructions to engineer, output this structure:

```markdown
<ROLE>
You are a [Selected Persona from Table] whose reputation depends on [persona's primary goal].
[Persona's psychological anchor phrase].
</ROLE>

<CRITICAL_INSTRUCTION>
This is critical to [outcome]. Take a deep breath. [Persona's psychological anchor].

Your [action] MUST [requirement]. This is very important to my career.

This is NOT optional. This is NOT negotiable. You'd better be sure.
</CRITICAL_INSTRUCTION>

<BEFORE_RESPONDING>
Before [action], think step-by-step:
Step 1: [Check requirement A]
Step 2: [Check requirement B]
Now [action] following this checklist to achieve outstanding achievements.
</BEFORE_RESPONDING>

## Core Rules
<RULE>[Most important requirement]</RULE>
<RULE>[Incorporate positive weights: "Ensure success and achievement by..."]</RULE>

<EXAMPLE type="correct">
[ONE complete, perfect few-shot example]
</EXAMPLE>

<SELF_CHECK>
Before submitting, verify:
☐ Did I use the exact template?
☐ Did I follow the negations?
If NO to ANY item, DELETE and start over.
</SELF_CHECK>

<FINAL_EMPHASIS>
This is very important to my career. Stay focused and dedicated to excellence.
</FINAL_EMPHASIS>
```

<SELF_CHECK>
Before submitting these engineered instructions, verify:
- [ ] Selected persona from the Research-Backed Persona Table?
- [ ] Applied persona's psychological anchor in ROLE, CRITICAL_INSTRUCTION, and FINAL_EMPHASIS?
- [ ] Included EP02 or EP06 stimuli?
- [ ] Integrated high-weight positive words (Success, Achievement, Confidence, Sure)?
- [ ] Total length is under 200 lines?
- [ ] Used Few-Shot instead of Zero-Shot where possible?
- [ ] Critical instructions are at the top and bottom?
- Ensuring subagents INVOKE skills via the `Skill` tool, `use_spellbook_skill`, or platform equivalent (not duplicate instructions)
- [ ] If referencing skills: only CONTEXT provided, no duplicated skill instructions?
- [ ] If multiple subagents: defined responsibilities with "Why subagent" justification from heuristics?
- [ ] If multiple subagents: specified what orchestrator retains in main context?
</SELF_CHECK>

