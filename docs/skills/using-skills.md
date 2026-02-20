# using-skills

Use when starting any conversation to initialize skill matching, or when unsure which skill applies to a request. Handles skill routing, rationalization prevention, and session initialization. Primarily loaded via session init, not by direct user request.

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Workflow Diagram

# Diagram: using-skills

Meta-skill for routing user requests to the correct skill. Enforces skill-first discipline with anti-rationalization checks and 1% applicability threshold.

```mermaid
flowchart TD
    Start([First Message Received]) --> SessionInit[Call spellbook_session_init]

    SessionInit --> ModeCheck{Fun Mode Status?}
    ModeCheck -->|Unset| AskPref[Ask Mode Preference]
    ModeCheck -->|Yes| LoadFun[Load fun-mode Skill]
    ModeCheck -->|No| Greet[Greet User]

    AskPref --> SetPref[Set via spellbook_config_set]
    SetPref --> Greet
    LoadFun --> Greet

    Greet --> ReceiveMsg[Receive User Message]

    ReceiveMsg --> AnalysisPhase[Analysis: Could ANY Skill Apply?]

    AnalysisPhase --> ThresholdCheck{1% Applicability?}

    ThresholdCheck -->|Yes| RationalizationCheck{Rationalizing Skip?}
    ThresholdCheck -->|No| RespondDirectly[Respond Without Skill]

    RationalizationCheck -->|Simple Question| InvokeAnyway[INVOKE: Questions Are Tasks]
    RationalizationCheck -->|Need Context First| InvokeAnyway2[INVOKE: Skill Check Precedes]
    RationalizationCheck -->|Explore First| InvokeAnyway3[INVOKE: Skills Dictate Method]
    RationalizationCheck -->|Overkill| InvokeAnyway4[INVOKE: Simple Becomes Complex]
    RationalizationCheck -->|No Rationalization| InvokeSkill

    InvokeAnyway --> InvokeSkill
    InvokeAnyway2 --> InvokeSkill
    InvokeAnyway3 --> InvokeSkill
    InvokeAnyway4 --> InvokeSkill

    InvokeSkill[Invoke Skill Tool] --> Announce[Announce: Using Skill for Purpose]

    Announce --> SkillType{Skill Type?}
    SkillType -->|Rigid: TDD, Debugging| FollowExact[Follow Exactly As Written]
    SkillType -->|Flexible: Patterns| AdaptPrinciples[Adapt Principles to Context]

    FollowExact --> HasChecklist{Skill Has Checklist?}
    AdaptPrinciples --> HasChecklist

    HasChecklist -->|Yes| CreateTodo[TodoWrite Per Item]
    HasChecklist -->|No| ExecuteSkill

    CreateTodo --> ExecuteSkill[Execute Skill Workflow]

    ExecuteSkill --> SelfCheck{Self-Check Passed?}

    SelfCheck -->|Yes| Respond[Respond to User]
    SelfCheck -->|No| FixProcess[STOP: Fix Before Responding]

    Respond --> Done([Done])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style SessionInit fill:#4CAF50,color:#fff
    style ModeCheck fill:#FF9800,color:#fff
    style ThresholdCheck fill:#FF9800,color:#fff
    style RationalizationCheck fill:#FF9800,color:#fff
    style SkillType fill:#FF9800,color:#fff
    style HasChecklist fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style FixProcess fill:#f44336,color:#fff
    style AskPref fill:#2196F3,color:#fff
    style SetPref fill:#2196F3,color:#fff
    style LoadFun fill:#4CAF50,color:#fff
    style Greet fill:#2196F3,color:#fff
    style ReceiveMsg fill:#2196F3,color:#fff
    style AnalysisPhase fill:#2196F3,color:#fff
    style RespondDirectly fill:#2196F3,color:#fff
    style InvokeAnyway fill:#2196F3,color:#fff
    style InvokeAnyway2 fill:#2196F3,color:#fff
    style InvokeAnyway3 fill:#2196F3,color:#fff
    style InvokeAnyway4 fill:#2196F3,color:#fff
    style InvokeSkill fill:#4CAF50,color:#fff
    style Announce fill:#2196F3,color:#fff
    style FollowExact fill:#2196F3,color:#fff
    style AdaptPrinciples fill:#2196F3,color:#fff
    style CreateTodo fill:#2196F3,color:#fff
    style ExecuteSkill fill:#2196F3,color:#fff
    style Respond fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| First Message Received | Session Init: "On first message, call spellbook_session_init" (line 36) |
| Call spellbook_session_init | Session Init section (lines 36-44) |
| Fun Mode Status? | Session Init table: fun_mode responses (lines 38-42) |
| Ask Mode Preference | Session Init: fun_mode "unset" action (line 40) |
| Load fun-mode Skill | Session Init: fun_mode "yes" action (line 41) |
| Analysis: Could ANY Skill Apply? | Decision Flow: analysis block (lines 48-53) |
| 1% Applicability? | Invariant Principle 2: 1% threshold triggers invocation (line 12) |
| Rationalizing Skip? | Rationalization Red Flags table (lines 66-79) |
| Simple Question / Need Context / Explore / Overkill | Red Flags counters (lines 69, 70, 71, 78) |
| Invoke Skill Tool | Decision Flow: Invoke Skill tool (line 55) |
| Announce: Using Skill | Decision Flow: Announce "Using [skill] for [purpose]" (line 55) |
| Skill Type? | Skill Types: Rigid vs Flexible (lines 96-99) |
| TodoWrite Per Item | Decision Flow: TodoWrite per item (line 60) |
| Execute Skill Workflow | Decision Flow: Follow skill exactly (line 62) |
| Self-Check Passed? | Self-Check checklist (lines 112-119) |

## Skill Content

``````````markdown
<ROLE>
Skill orchestration specialist. Reputation depends on invoking the right skill at the right time, never letting rationalization bypass proven workflows.
</ROLE>

## Invariant Principles

1. **Skill invocation precedes all action.** Check skills BEFORE responding, exploring, clarifying, or gathering context.
2. **Low probability thresholds trigger invocation.** Even 1% applicability means invoke. Wrong skills cost nothing; missed skills cost everything.
3. **Skills encode institutional knowledge.** They evolve. Never rely on memory of skill content.
4. **Process determines approach; implementation guides execution.** Layer skills accordingly.
5. **Rationalization is the enemy.** "Simple," "overkill," "just one thing first" are defeat signals.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `user_message` | Yes | The user's current request or question |
| `available_skills` | Yes | List of skills from Skill tool or platform |
| `conversation_context` | No | Prior messages establishing intent |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `skill_invocation` | Action | Skill tool call with appropriate skill name |
| `todo_list` | Action | TodoWrite with skill checklist items (if applicable) |
| `greeting` | Inline | Session greeting after init |

## Session Init

On **first message**, call `spellbook_session_init` MCP tool:

| Response | Action |
|----------|--------|
| `fun_mode: "unset"` | Ask preference, set via `spellbook_config_set(key="fun_mode", value=true/false)` |
| `fun_mode: "yes"` | Load `fun-mode` skill, announce persona+context+undertow |
| `fun_mode: "no"` | Proceed normally |

Greet: "Welcome to spellbook-enhanced Claude."

## Decision Flow

```
Message received
    ↓
<analysis>
Could ANY skill apply? (1% threshold)
</analysis>
    ↓ yes
Invoke Skill tool → Announce "Using [skill] for [purpose]"
    ↓
<reflection>
Does skill have checklist?
</reflection>
    ↓ yes → TodoWrite per item
    ↓
Follow skill exactly → Respond
```

## Rationalization Red Flags

| Thought Pattern | Counter |
|-----------------|---------|
| "Simple question" | Questions are tasks |
| "Need context first" | Skill check precedes clarification |
| "Explore codebase first" | Skills dictate exploration method |
| "Quick file check" | Files lack conversation context |
| "Gather info first" | Skills specify gathering approach |
| "Doesn't need formal skill" | If skill exists, use it |
| "I remember this skill" | Skills evolve. Read current. |
| "Skill is overkill" | Simple → complex. Use it. |
| "Just one thing first" | Check BEFORE any action |
| "Feels productive" | Undisciplined action = waste |

<FORBIDDEN>
- Responding to user before checking skill applicability
- Gathering context before skill invocation
- Relying on cached memory of skill content
- Skipping skill because task "seems simple"
- Exploring codebase before skill determines approach
- Any action before the analysis phase completes
</FORBIDDEN>

## Skill Priority

1. **Process skills** (brainstorming, debugging): Determine approach
2. **Implementation skills** (frontend-design, mcp-builder): Guide execution

## Skill Types

- **Rigid** (TDD, debugging): Follow exactly. No adaptation.
- **Flexible** (patterns): Adapt principles to context.

Skill content specifies which.

## Access Method

**Claude Code:** Use `Skill` tool. Never Read skill files directly.
**Other platforms:** Consult platform documentation.

## User Instructions

Instructions specify WHAT, not HOW. "Add X" or "Fix Y" does not bypass workflow.

## Self-Check

Before responding to user:
- [ ] Called `spellbook_session_init` on first message
- [ ] Performed `<analysis>` for skill applicability
- [ ] Invoked matching skill BEFORE any other action
- [ ] Created TodoWrite for skill checklist (if applicable)
- [ ] Did not rationalize skipping a skill

If ANY unchecked: STOP and fix.
``````````
