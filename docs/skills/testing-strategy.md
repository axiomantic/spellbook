# testing-strategy

Reference guide for choosing which tests to run, when to run them, and how to diagnose cross-module regressions. Keeps test feedback loops tight by matching test scope to change scope.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Test selection strategy and scope guidance. Triggers: 'which tests should I run', 'test tiers', 'test marks', 'slow tests', 'integration vs unit', 'cross-module regression', 'test scope', 'what should I run', 'select tests', 'test batching'. NOT for: writing tests (use test-driven-development) or fixing broken tests (use fixing-tests).
## Skill Content

``````````markdown
<analysis>
Reference for choosing which tests to run based on change scope, and diagnosing cross-module regressions when targeted tests pass but the full suite fails.
</analysis>

<reflection>
Did I match test scope to change scope, and did I avoid running the full suite when targeted tests would suffice?
</reflection>

# Testing Strategy

## Invariant Principles

1. **Scope Matches Change** - Test selection mirrors the scope of the code change; a single-file change does not justify a full suite run.
2. **Marks Are Proactive** - Tests are marked (slow, gpu, network) at authoring time based on what they require, not how fast they happen to run today.
3. **Full Suite Runs Once** - The complete test suite runs once per work unit completion, not after every incremental change.

## Test Tiers

| Tier | Time | What | When |
|------|------|------|------|
| Unit | <1s each | Pure logic, no I/O, no external deps | After every change |
| Integration | 1-5s each | Real resources (DB, filesystem, network) | After completing a logical unit of work |
| E2E / Slow | >5s each | Full pipelines, large data, real services | Once per feature branch, before PR |

## Selecting What to Run

- **Single file changed**: Run only the test file(s) that directly test that module. `src/auth/login.py` changed? Run `tests/test_login.py`.
- **Shared dependency changed** (types, config, utilities): Grep for imports of the changed module across test files. Run all direct consumers.
- **Multi-file task complete**: Run unit tests for all changed files in one command.
- **All tasks in a work unit complete**: Run the full suite once.
- **If >5 test files affected**: Run the full fast tier rather than listing individually.

**Batching**: Write code for task 1, run targeted tests, write code for task 2, run targeted tests, run full suite once at end.

## Writing Tests for Speed

Mock expensive resources in unit tests. Use smallest possible inputs. Never sleep in tests. One assertion focus per test. No fixtures heavier than the test itself.

## Test Marks

Apply marks proactively when writing tests. A test that calls a GPU kernel is a GPU test even if it is fast today.

| Mark | Meaning |
|------|---------|
| `slow` | >5 seconds. Skip during rapid iteration. |
| `gpu`, `hardware` | Requires specific hardware. Skip on machines without it. |
| `network` / `external` | Calls external services. Skip in offline/fast modes. |
| `integration` | Requires multiple components working together. |
| `smoke` | Minimal sanity checks. Run first. |

If a project lacks marks, infer tiers from `--durations=0` (pytest) or equivalent: >5s is slow, >1s is integration, the rest are unit.

## Cross-Module Regression

When the full suite fails after targeted tests passed: check failed test imports against your changed modules, then investigate shared mutable state, test ordering, or resource contention.
``````````
