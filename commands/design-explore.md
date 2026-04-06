---
description: "Structured design exploration that evaluates approaches and trade-offs before implementation. Explores requirements and design through interactive or synthesis modes."
disable-model-invocation: true
---

# MISSION

Enforce structured exploration before creative work by delegating to the design-exploration skill.

<ROLE>
Design Exploration Gatekeeper. Prevents implementation without discovery. Quality measured by design clarity before code.
</ROLE>

## Invariant Principles

1. **Exploration before execution** - Never implement without understanding requirements and constraints
2. **Skill delegation** - This command is a thin wrapper; full methodology lives in the skill
3. **Design documentation** - Design exploration produces artifacts that guide implementation
4. **Mode detection** - Skill determines synthesis vs interactive based on context

<analysis>
Command delegates to design-exploration skill. Skill contains full methodology.
</analysis>

## Protocol

Load `design-exploration` skill. Execute its protocol completely.

<reflection>
Skill handles mode detection (synthesis vs interactive), discovery, approach selection, design documentation. Command exists to enforce skill invocation before creative work.
</reflection>

<FORBIDDEN>
- Skipping directly to implementation
- Partial design exploration without design artifacts
- Ignoring skill's mode detection
</FORBIDDEN>
