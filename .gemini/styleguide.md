# Spellbook Code Review Style Guide

## Version Bump and Changelog (Required)

Every PR must include:

1. **A version bump in the `.version` file** (which `pyproject.toml` reads via `dynamic = ["version"]`) following semantic versioning:
   - **patch** (0.x.Y): bug fixes, internal refactors, test-only changes
   - **minor** (0.X.0): new features, new MCP tools, new skills/commands, behavioral changes
   - **major** (X.0.0): only when crossing the 1.0 threshold (project is pre-1.0)
2. **A corresponding CHANGELOG.md entry** under an `## Unreleased` or `## [version]` heading describing what changed

**Enforcement rules:**
- The version MUST increment by exactly 1 from the current version on the base branch (no gaps like 0.39.0 to 0.41.0)
- The bump level (patch vs minor) must match the scope of changes in the PR
- If the PR description or a comment says "no version bump needed" or "skip version bump", this requirement is waived

Flag as **high severity** if the version bump or changelog entry is missing. Flag as **medium severity** if the bump level seems incorrect for the scope of changes.

## General Review Focus

- Python code should follow PEP 8 and use type hints
- All MCP tool functions must have `@mcp.tool()` and `@inject_recovery_context` decorators
- Tests must use the bigfoot testing framework, NOT unittest.mock
- Silent `except Exception: pass` blocks should log the exception
- Prefer top-level imports over function-level imports unless there is a circular dependency
