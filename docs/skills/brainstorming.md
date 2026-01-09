# brainstorming

"Use before any creative work - creating features, building components, adding functionality, or modifying behavior"

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Skill Content

``````````markdown
# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

**Two modes of operation:**
- **Interactive mode** (default): Ask questions, validate incrementally, collaborate with user
- **Synthesis mode**: Given comprehensive context, produce design without questions

## Mode Detection

<CRITICAL>
Check your context for synthesis mode indicators BEFORE starting the interactive process.
</CRITICAL>

**Synthesis mode is active when you see ANY of these in your context:**
- "SYNTHESIS MODE" or "synthesis mode"
- "Mode: AUTONOMOUS"
- "DO NOT ask questions"
- "Pre-Collected Discovery Context" or "design_context"
- Comprehensive context with architectural decisions, scope boundaries, success criteria already defined

**When synthesis mode is detected:**
1. Skip "Understanding the idea" phase entirely
2. Skip "Exploring approaches" questions
3. Go directly to "Presenting the design" - write the FULL design
4. Do NOT ask "does this look right so far" between sections
5. Do NOT ask "Ready to set up for implementation?"
6. Produce complete output, then stop

**When synthesis mode is NOT detected:**
Continue with standard interactive process below.

---

## Autonomous Mode Behavior

<!-- SUBAGENT: CONDITIONAL for synthesis mode - If context lacks codebase patterns, dispatch Explore subagent first. Otherwise proceed in main context with provided design_context. -->

When synthesis mode / autonomous mode is active:

### Skip These Interactions
- Questions about purpose, constraints, success criteria (should be in context)
- "Which approach would you prefer?" (make the best choice, document rationale)
- "Does this look right so far?" (proceed through all sections)
- "Ready to set up for implementation?" (just complete the design doc)

### Make These Decisions Autonomously
- Architectural approach: Choose best fit based on context, document why
- Trade-offs: Make the call, document alternatives considered
- Scope boundaries: Use what's in context, flag any ambiguity

### Circuit Breakers (Still Pause For)
- Security-critical design decisions with no guidance in context
- Contradictory requirements that cannot be reconciled
- Missing context that makes design impossible (not just inconvenient)

Use the Circuit Breaker Format from patterns/autonomous-mode-protocol.md if pausing.

---

## The Process (Interactive Mode)

<!-- SUBAGENT: NO for interactive mode - Stay in main context. Iterative user interaction required. Context must persist across exchanges. -->

**Understanding the idea:**
- Check out the current project state first (files, docs, recent commits)
- If exploring codebase for patterns/context, use Explore subagent (returns synthesis, saves main context)
- Ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**
- Once you believe you understand what you're building, present the design
- Break it into sections of 200-300 words
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

## After the Design

**Documentation:**
- Write the validated design to `~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-<topic>-design.md`
- Create the directory if it doesn't exist: `mkdir -p ~/.local/spellbook/docs/<project-encoded>/plans`
- Generate project encoded path:
  ```bash
  # Encode full project path: /Users/alice/Development/myproject → Users-alice-Development-myproject
  PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
  ```
- Use elements-of-style:writing-clearly-and-concisely skill if available
- Commit the design document to git

**Implementation (if continuing):**
- Ask: "Ready to set up for implementation?"
- Use using-git-worktrees to create isolated workspace
- Use writing-plans to create detailed implementation plan

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design in sections, validate each
- **Be flexible** - Go back and clarify when something doesn't make sense
``````````
