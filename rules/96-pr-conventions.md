---
id: pr-conventions
name: Pull Request Conventions
class: preference
default: "on"
description: >
  How a repository's pull request template is discovered and applied, and which
  sections never appear in a pull request body.
benefit: >
  Uses the repository's own PR template instead of the harness's default Test-plan shape.
declining_means: >
  Pull request bodies follow the harness default, which typically imposes a
  Summary and Test plan structure the repository did not ask for.
related:
  - skills/creating-issues-and-pull-requests
renamed_from: []
superseded_by: null
paths: []
---

## Pull Request Conventions

<CRITICAL>
Before running `gh pr create`, ALWAYS invoke the `creating-issues-and-pull-requests` skill. That skill's job is to discover and apply the repo's PR template. Going straight to `gh pr create` causes the Claude Code harness's hardcoded `## Summary` + `## Test plan` template to win, which is almost never what the repo actually wants.
</CRITICAL>

<RULE>NEVER include a "Test plan" section (or any test-plan-shaped checklist) in PR bodies. Not as `## Test plan`, not as `### Testing`, not as a trailing checklist. The user has explicitly rejected this pattern.</RULE>

<RULE>ALWAYS use the repository's PR template when one exists. Fetch it via `creating-issues-and-pull-requests` skill, which checks `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/pull_request_template.md`, and `PULL_REQUEST_TEMPLATE/*.md`. If no template exists, a plain description is fine — do NOT invent `## Summary` / `## Test plan` sections to fill the void.</RULE>

**Background — why the disconnect happens:** The Claude Code harness system prompt (above all user instructions) contains a literal `gh pr create` heredoc template with `## Summary` and `## Test plan` sections. When `gh pr create` is invoked directly without going through the skill, that template biases the output. These rules override the harness default.
