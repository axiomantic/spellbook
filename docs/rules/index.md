# Rule Modules Overview

Rule modules are the behavioral instructions spellbook installs into your coding
assistant. Each module is a separate file under `rules/`, delivered as a symlink
on harnesses that read a rules directory and as a generated bundle on harnesses
that read a single instruction file.

Mandatory modules install on every platform. Optional modules are offered during
installation and recorded under the `rules.module.<id>` config keys, so a module
you decline is never reinstalled and a module added later is offered once.

## Available Rule Modules

| Module | Class | Description |
|--------|-------|-------------|
| [Spellbook Core](00-core.md) | mandatory | What spellbook is, how paths resolve, what runs at session start, and the shared vocabulary every other rule module assumes. |
| [Session Context](10-session.md) | optional (default on) | The project-knowledge offer protocol: AGENTS.md reading, fleshing out, and per-directory extensions. |
| [Orchestration and Subagent Dispatch](20-orchestration.md) | mandatory | You conduct rather than implement: how substantive work is delegated to subagents, how model and effort are matched to a task, and how skills execute. |
| [Intent Routing](30-intent-routing.md) | mandatory | How a user's expressed wish about functionality routes to a skill, and why planning happens inside the develop skill rather than in the harness planner. |
| [Develop Skill Discipline](40-develop-discipline.md) | optional (default on) | Phase non-fungibility inside the develop skill, and the thoroughness contract that invoking develop establishes. |
| [Verification Discipline](45-verification.md) | mandatory | Why a success signal is not evidence that a step ran, and how to verify the artifact a step should have produced instead of its exit status. |
| [Git Safety](50-git-safety.md) | mandatory | Which git and session operations require explicit permission, and which content is never allowed to reach an executing tool or a shared workflow state. |
| [AI Attribution Suppression](51-ai-attribution.md) | optional (default on) | Suppresses AI attribution in commits, pull requests, issues, and comments. |
| [Diff and Branch Semantics](55-diff-semantics.md) | mandatory | How the merge target and merge base are detected, and how the diff endpoint is chosen for the task at hand. |
| [Autonomous Mode](60-autonomy.md) | optional (default on) | How the agent behaves when it is running without turn-by-turn confirmation. |
| [Bash Gate Navigation](70-bash-gate.md) | mandatory | How to read a spellbook bash-gate denial, which layer produced it, and what the correct response is for each block class. |
| [Code Quality](80-code-quality.md) | optional (default on) | The standing quality bar for produced code and the rule against silently skipping pre-existing issues. |
| [Testing Discipline](81-testing.md) | optional (default on) | How many test commands run at once and how test scope is matched to change scope. |
| [File Reading](82-file-reading.md) | optional (default on) | Sizing a file or command output before reading it, and the ban on truncating reads. |
| [Python Conventions](83-language-python.md) | optional (default on) | Import placement convention for Python code. |
| [Review Method](85-review-method.md) | optional (default on) | How a code review loads the standards it will judge against, and how much of the diff it is obliged to read. |
| [Review Posture (Zero Tolerance)](86-review-posture.md) | optional (default off) | An adversarial, zero-tolerance quality-gate posture for code review. |
| [Agent Role](91-role.md) | mandatory | The standing persona every skill inherits rather than restating. |
| [Core Philosophy](92-core-philosophy.md) | mandatory | The standing dispositions that govern how a solution is chosen: verify before trusting, dig rather than retreat, preserve behavior, and prefer correctness to speed. |
| [Communication](93-communication.md) | optional (default on) | How questions reach the user, and the expected tone for prose the agent writes. |
| [Worktrees](95-worktrees.md) | optional (default on) | Isolation between a worktree and its main checkout, the worktree location convention, and the requirement that git commands run from the worktree path. |
| [Pull Request Conventions](96-pr-conventions.md) | optional (default on) | How a repository's pull request template is discovered and applied, and which sections never appear in a pull request body. |
| [Opportunity Awareness](97-opportunity-awareness.md) | optional (default on) | Self-monitoring for reusable artifact candidates and project knowledge gaps at natural pause points. |
