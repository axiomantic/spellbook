# Quick Start

After installation, Spellbook skills are available immediately. Skills are invoked automatically when your coding assistant detects a matching trigger, or manually with `/<skill-name>`.

## Common Workflows

### Starting a New Feature or Project

Invoke the [develop](../skills/develop.md) skill. It handles the entire lifecycle: research, discovery, design, planning, and implementation with quality gates at every phase.

```
I want to add dark mode to the settings page.
```

That's it. The `develop` skill activates automatically when you describe what you want to build, or invoke it explicitly with `/develop`. It coordinates subagents for research, design review, TDD, code review, and fact-checking.

### Debugging an Issue

Describe the bug or paste a stack trace. The [debugging](../skills/debugging.md) skill activates automatically.

```
This test is failing with a timeout on CI but passes locally.
```

Or invoke explicitly with `/debugging`. It selects between scientific debugging, systematic elimination, and CI-specific investigation based on the problem type.

### Code Review

**Requesting review before a PR:**

```
Review my changes using /requesting-code-review
```

The [requesting-code-review](../skills/requesting-code-review.md) skill assembles context, dispatches review agents, triages findings, and produces a remediation plan.

**Deep multi-phase review:**

Use [advanced-code-review](../skills/advanced-code-review.md) for historical context analysis, fact-checked findings, and tiered severity reporting.

## Key Skills

| Skill | What it does |
|-------|-------------|
| [develop](../skills/develop.md) | Full-lifecycle feature implementation with research, design, planning, and execution |
| [debugging](../skills/debugging.md) | Structured bug investigation with methodology selection and hypothesis tracking |
| [fractal-thinking](../skills/fractal-thinking.md) | Recursive question decomposition for deep exploration of complex topics |
| [dehallucination](../skills/dehallucination.md) | Verifies claims and references are grounded in reality, not fabricated |
| [auditing-green-mirage](../skills/auditing-green-mirage.md) | Detects tests that pass but don't actually verify behavior |
