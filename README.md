
<p align="center">
  <img src="./docs/assets/logo-book.svg" alt="Spellbook" width="300">
</p>

<h1 align="center">Spellbook</h1>

<p align="center">
  <em>Principled development on autopilot. Decades of engineering expertise, built in. Also fun.</em><br>
  For Claude Code, OpenCode, Codex, Gemini CLI, and Crush.
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook/blob/main/LICENSE"><img src="https://img.shields.io/github/license/axiomantic/spellbook?style=flat-square" alt="License"></a>
  <a href="https://github.com/axiomantic/spellbook/stargazers"><img src="https://img.shields.io/github/stars/axiomantic/spellbook?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/axiomantic/spellbook/issues"><img src="https://img.shields.io/github/issues/axiomantic/spellbook?style=flat-square" alt="Issues"></a>
  <a href="https://axiomantic.github.io/spellbook/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Documentation"></a>
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook"><img src="https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNzAuNjY3IiBoZWlnaHQ9IjE3MC42NjciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiBmaWxsPSIjRkZGIiB4bWxuczp2PSJodHRwczovL3ZlY3RhLmlvL25hbm8iPjxwYXRoIGQ9Ik0yMy4xNjggMTIwLjA0YTMuODMgMy44MyAwIDAgMCAxLjM5MSA0LjI4NWMxLjM0NC45NzcgMy4xNjQuOTc3IDQuNTA4IDBMNjQgOTguOTVsMzQuOTMgMjUuMzc1YTMuODEgMy44MSAwIDAgMCAyLjI1NC43MzQgMy44IDMuOCAwIDAgMCAyLjI1NC0uNzM0IDMuODMgMy44MyAwIDAgMCAxLjM5MS00LjI4NWwtMTMuMzQtNDEuMDY2IDM0LjkzLTI1LjM3OWEzLjgzIDMuODMgMCAwIDAgMS4zOTQtNC4yODVjLS41MTItMS41ODItMS45ODQtMi42NDgtMy42NDQtMi42NDhsLTQzLjE4NC4wMDQtMTMuMzQtNDEuMDdDNjcuMTI5IDQuMDE3IDY1LjY2IDIuOTUxIDY0IDIuOTUxcy0zLjEzMyAxLjA2Ni0zLjY0OCAyLjY0NWwtMTMuMzQgNDEuMDY2SDMuODMyYy0xLjY2IDAtMy4xMzMgMS4wNjYtMy42NDQgMi42NDhzLjA0NyAzLjMwNSAxLjM5MSA0LjI4NWwzNC45MyAyNS4zNzl6bTEwLjkzNC04Ljg0NGw4LjkzNC0yNy40OCAxNC40NDkgMTAuNDk2em01OS43OTMgMEw3MC41MTYgOTQuMjA4bDE0LjQ0OS0xMC40OTZ6bTE4LjQ3Ny01Ni44NjdMODguOTkzIDcxLjMxM2wtNS41MTYtMTYuOTg0ek02NC4wMDEgMTkuMTgxbDguOTMgMjcuNDg0SDU1LjA2OHpNNTIuNTc5IDU0LjMyOWgyMi44NGw3LjA1OSAyMS43MjMtMTguNDc3IDEzLjQyNi0xOC40OC0xMy40MjZ6bS0zNi45NTMgMGgyOC44OTVsLTUuNTE2IDE2Ljk4NHoiLz48L3N2Zz4=" alt="Built with Spellbook"></a>
</p>

<p align="center">
  <a href="https://axiomantic.github.io/spellbook/"><strong>Documentation</strong></a> ·
  <a href="https://axiomantic.github.io/spellbook/getting-started/installation/"><strong>Getting Started</strong></a> ·
  <a href="https://axiomantic.github.io/spellbook/skills/"><strong>Skills Reference</strong></a>
</p>

---
## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Quick Install](#quick-install)
- [What's Included](#whats-included)
  - [Skills (49 total)](#skills-49-total)
  - [Commands (77 total)](#commands-77-total)
  - [Agents (7 total)](#agents-7-total)
- [Serious Fun](#serious-fun)
- [Platform Support](#platform-support)
  - [Operating Systems](#operating-systems)
  - [Coding Assistants](#coding-assistants)
  - [YOLO Mode](#yolo-mode)
- [Playbooks](#playbooks)
  - [Implementing a Feature](#implementing-a-feature)
  - [Fun Mode in Action](#fun-mode-in-action)
  - [Large Feature with Context Exhaustion](#large-feature-with-context-exhaustion)
  - [Test Suite Audit and Remediation](#test-suite-audit-and-remediation)
  - [Parallel Worktree Development](#parallel-worktree-development)
  - [Cross-Assistant Handoff](#cross-assistant-handoff)
- [Recommended Companion Tools](#recommended-companion-tools)
  - [Heads Up Claude](#heads-up-claude)
  - [MCP Language Server](#mcp-language-server)
- [Development](#development)
  - [Serve Documentation Locally](#serve-documentation-locally)
  - [Run MCP Server Directly](#run-mcp-server-directly)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [Attribution](#attribution)
- [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

The installer requires Python 3.10+ and git, then automatically installs uv and configures skills for detected platforms.

**Upgrade:** `cd ~/.local/share/spellbook && git pull && python3 install.py`

**Uninstall:** `python3 ~/.local/share/spellbook/uninstall.py`

See [Installation Guide](https://axiomantic.github.io/spellbook/getting-started/installation/) for advanced options.

## What's Included

### Skills (49 total)

Reusable workflows for structured development:

| Category | Skills |
|----------|--------|
| **Core Workflow** | [brainstorming]†, [writing-plans]†, [executing-plans]†, [test-driven-development]†, [debugging], [verifying-hunches], [isolated-testing], [using-git-worktrees]†, [finishing-a-development-branch]† |
| **Code Quality** | [enforcing-code-quality], [code-review], [advanced-code-review], [auditing-green-mirage], [fixing-tests], [fact-checking], [finding-dead-code], [distilling-prs], [receiving-code-review]†, [requesting-code-review]† |
| **Feature Dev** | [implementing-features], [reviewing-design-docs], [reviewing-impl-plans], [devils-advocate], [merging-worktrees], [resolving-merge-conflicts] |
| **Autonomous Dev** | [autonomous-roundtable], [gathering-requirements], [dehallucination], [reflexion], [analyzing-domains], [assembling-context], [designing-workflows], [deep-research] |
| **Specialized** | [async-await-patterns], [using-lsp-tools], [managing-artifacts], [security-auditing] |
| **Meta** | [using-skills]†, [writing-skills]†, [writing-commands], [instruction-engineering], [sharpening-prompts], [optimizing-instructions], [dispatching-parallel-agents]†, [smart-reading], [project-encyclopedia], [analyzing-skill-usage], [documenting-tools] |
| **Session** | [fun-mode], [tarot-mode], [emotional-stakes] |

*† Derived from [superpowers](https://github.com/obra/superpowers)*

[brainstorming]: https://axiomantic.github.io/spellbook/latest/skills/brainstorming/
[writing-plans]: https://axiomantic.github.io/spellbook/latest/skills/writing-plans/
[executing-plans]: https://axiomantic.github.io/spellbook/latest/skills/executing-plans/
[test-driven-development]: https://axiomantic.github.io/spellbook/latest/skills/test-driven-development/
[debugging]: https://axiomantic.github.io/spellbook/latest/skills/debugging/
[verifying-hunches]: https://axiomantic.github.io/spellbook/latest/skills/verifying-hunches/
[isolated-testing]: https://axiomantic.github.io/spellbook/latest/skills/isolated-testing/
[using-git-worktrees]: https://axiomantic.github.io/spellbook/latest/skills/using-git-worktrees/
[enforcing-code-quality]: https://axiomantic.github.io/spellbook/latest/skills/enforcing-code-quality/
[advanced-code-review]: https://axiomantic.github.io/spellbook/latest/skills/advanced-code-review/
[auditing-green-mirage]: https://axiomantic.github.io/spellbook/latest/skills/auditing-green-mirage/
[fixing-tests]: https://axiomantic.github.io/spellbook/latest/skills/fixing-tests/
[fact-checking]: https://axiomantic.github.io/spellbook/latest/skills/fact-checking/
[finding-dead-code]: https://axiomantic.github.io/spellbook/latest/skills/finding-dead-code/
[receiving-code-review]: https://axiomantic.github.io/spellbook/latest/skills/receiving-code-review/
[requesting-code-review]: https://axiomantic.github.io/spellbook/latest/skills/requesting-code-review/
[implementing-features]: https://axiomantic.github.io/spellbook/latest/skills/implementing-features/
[reviewing-design-docs]: https://axiomantic.github.io/spellbook/latest/skills/reviewing-design-docs/
[reviewing-impl-plans]: https://axiomantic.github.io/spellbook/latest/skills/reviewing-impl-plans/
[devils-advocate]: https://axiomantic.github.io/spellbook/latest/skills/devils-advocate/
[merging-worktrees]: https://axiomantic.github.io/spellbook/latest/skills/merging-worktrees/
[resolving-merge-conflicts]: https://axiomantic.github.io/spellbook/latest/skills/resolving-merge-conflicts/
[async-await-patterns]: https://axiomantic.github.io/spellbook/latest/skills/async-await-patterns/
[using-lsp-tools]: https://axiomantic.github.io/spellbook/latest/skills/using-lsp-tools/
[managing-artifacts]: https://axiomantic.github.io/spellbook/latest/skills/managing-artifacts/
[security-auditing]: https://axiomantic.github.io/spellbook/latest/skills/security-auditing/
[code-review]: https://axiomantic.github.io/spellbook/latest/skills/code-review/
[using-skills]: https://axiomantic.github.io/spellbook/latest/skills/using-skills/
[writing-skills]: https://axiomantic.github.io/spellbook/latest/skills/writing-skills/
[instruction-engineering]: https://axiomantic.github.io/spellbook/latest/skills/instruction-engineering/
[sharpening-prompts]: https://axiomantic.github.io/spellbook/latest/skills/sharpening-prompts/
[optimizing-instructions]: https://axiomantic.github.io/spellbook/latest/skills/optimizing-instructions/
[dispatching-parallel-agents]: https://axiomantic.github.io/spellbook/latest/skills/dispatching-parallel-agents/
[smart-reading]: https://axiomantic.github.io/spellbook/latest/skills/smart-reading/
[project-encyclopedia]: https://axiomantic.github.io/spellbook/latest/skills/project-encyclopedia/
[analyzing-skill-usage]: https://axiomantic.github.io/spellbook/latest/skills/analyzing-skill-usage/
[documenting-tools]: https://axiomantic.github.io/spellbook/latest/skills/documenting-tools/
[writing-commands]: https://axiomantic.github.io/spellbook/latest/skills/writing-commands/
[finishing-a-development-branch]: https://axiomantic.github.io/spellbook/latest/skills/finishing-a-development-branch/
[fun-mode]: https://axiomantic.github.io/spellbook/latest/skills/fun-mode/
[tarot-mode]: https://axiomantic.github.io/spellbook/latest/skills/tarot-mode/
[emotional-stakes]: https://axiomantic.github.io/spellbook/latest/skills/emotional-stakes/
[distilling-prs]: https://axiomantic.github.io/spellbook/latest/skills/distilling-prs/
[autonomous-roundtable]: https://axiomantic.github.io/spellbook/latest/skills/autonomous-roundtable/
[gathering-requirements]: https://axiomantic.github.io/spellbook/latest/skills/gathering-requirements/
[dehallucination]: https://axiomantic.github.io/spellbook/latest/skills/dehallucination/
[reflexion]: https://axiomantic.github.io/spellbook/latest/skills/reflexion/
[analyzing-domains]: https://axiomantic.github.io/spellbook/latest/skills/analyzing-domains/
[assembling-context]: https://axiomantic.github.io/spellbook/latest/skills/assembling-context/
[designing-workflows]: https://axiomantic.github.io/spellbook/latest/skills/designing-workflows/
[deep-research]: https://axiomantic.github.io/spellbook/latest/skills/deep-research/

### Commands (77 total)

| Command | Description |
|---------|-------------|
| [/crystallize] | Transform SOPs into agentic CoT prompts |
| [/dead-code-setup] | Initialize dead code analysis with git safety and scope selection |
| [/dead-code-analyze] | Extract and triage code items for dead code verification |
| [/dead-code-report] | Generate dead code findings report with deletion plan |
| [/dead-code-implement] | Execute approved deletions with verification |
| [/deep-research-interview] | Phase 0: Structured interview and Research Brief generation |
| [/deep-research-investigate] | Phase 2: Triplet search engine with plateau detection and micro-reports |
| [/deep-research-plan] | Phase 1: Thread decomposition, source strategy, and convergence criteria |
| [/design-assessment] | Generate assessment frameworks for evaluative skills/commands |
| [/handoff] | Custom session compaction |
| [/distill-session] | Extract knowledge from sessions |
| [/feature-config] | Phase 0 configuration wizard for feature workflow |
| [/feature-discover] | Phase 1.5 informed discovery with disambiguation |
| [/feature-research] | Phase 1 codebase research and ambiguity detection |
| [/feature-design] | Phase 2 design document creation and review |
| [/feature-implement] | Phase 4 implementation with TDD and code review |
| [/simplify] | Code complexity reduction |
| [/simplify-analyze] | Analyze code for simplification opportunities |
| [/simplify-transform] | Apply simplification transformations |
| [/simplify-verify] | Verify simplification preserved behavior |
| [/address-pr-feedback] | Handle PR review comments |
| [/move-project] | Relocate projects safely |
| [/audit-green-mirage] | Test suite audit |
| [/verify]† | Verification before completion |
| [/systematic-debugging]† | Methodical debugging workflow |
| [/scientific-debugging] | Hypothesis-driven debugging |
| [/brainstorm]† | Design exploration |
| [/write-plan]† | Create implementation plan |
| [/execute-plan]† | Execute implementation plan |
| [/execute-work-packet] | Execute a single work packet with TDD |
| [/execute-work-packets-seq] | Execute all packets sequentially |
| [/merge-work-packets] | Merge completed packets with QA gates |
| [/mode] | Switch session mode (fun/tarot/off) |
| [/pr-distill] | Analyze PR, categorize changes by review necessity |
| [/pr-distill-bless] | Save discovered pattern for future distillations |
| [/advanced-code-review-plan] | Phase 1: Strategic planning for code review |
| [/advanced-code-review-context] | Phase 2: Context analysis and previous review loading |
| [/advanced-code-review-review] | Phase 3: Deep multi-pass code review |
| [/advanced-code-review-verify] | Phase 4: Verification and fact-checking of findings |
| [/advanced-code-review-report] | Phase 5: Report generation and artifact output |
| [/fact-check-extract] | Extract and triage claims from code |
| [/fact-check-verify] | Verify claims against source with evidence |
| [/fact-check-report] | Generate findings report with bibliography |
| [/review-plan-inventory] | Context, inventory, and work item classification |
| [/review-plan-contracts] | Interface contract audit |
| [/review-plan-behavior] | Behavior verification and fabrication detection |
| [/review-plan-completeness] | Completeness checks and escalation |
| [/audit-mirage-analyze] | Per-file anti-pattern analysis with scoring |
| [/audit-mirage-cross] | Cross-cutting analysis across test suite |
| [/audit-mirage-report] | Report generation and fix plan |
| [/review-design-checklist] | Document inventory and completeness checklist |
| [/review-design-verify] | Hand-waving detection and interface verification |
| [/review-design-report] | Implementation simulation, findings, and remediation |
| [/fix-tests-parse] | Parse and classify test failures |
| [/fix-tests-execute] | Fix execution with TDD loop and verification |
| [/request-review-plan] | Review planning and scope analysis |
| [/request-review-execute] | Execute review with checklists |
| [/request-review-artifacts] | Generate review artifacts and reports |
| [/encyclopedia-build] | Research, build, and write encyclopedia |
| [/encyclopedia-validate] | Validate encyclopedia accuracy |
| [/merge-worktree-execute] | Execute worktree merge sequence |
| [/merge-worktree-resolve] | Resolve merge conflicts |
| [/merge-worktree-verify] | Verify merge and cleanup |
| [/finish-branch-execute] | Analyze branch and execute chosen strategy |
| [/finish-branch-cleanup] | Post-merge cleanup |
| [/code-review-feedback] | Process received code review feedback |
| [/code-review-give] | Review others' code |
| [/code-review-tarot] | Roundtable-style collaborative review |
| [/write-skill-test] | Skill testing with pressure scenarios |
| [/writing-commands-create] | Command creation with schema, naming, and frontmatter |
| [/writing-commands-review] | Command quality checklist and testing protocol |
| [/writing-commands-paired] | Paired command protocol and assessment framework |
| [/reflexion-analyze] | Full reflexion analysis workflow |
| [/test-bar] | Generate floating QA test overlay for visual testing |
| [/test-bar-remove] | Clean removal of test-bar overlay |
| [/ie-techniques] | Reference for 16 proven instruction engineering techniques |
| [/ie-template] | Template and example for engineered instructions |
| [/ie-tool-docs] | Guidance for writing tool/function documentation |
| [/sharpen-audit] | Audit prompts for ambiguity with executor predictions |
| [/sharpen-improve] | Rewrite prompts to eliminate ambiguity |

*† Derived from [superpowers](https://github.com/obra/superpowers)*

[/crystallize]: https://axiomantic.github.io/spellbook/latest/commands/crystallize/
[/dead-code-setup]: https://axiomantic.github.io/spellbook/latest/commands/dead-code-setup/
[/dead-code-analyze]: https://axiomantic.github.io/spellbook/latest/commands/dead-code-analyze/
[/dead-code-report]: https://axiomantic.github.io/spellbook/latest/commands/dead-code-report/
[/dead-code-implement]: https://axiomantic.github.io/spellbook/latest/commands/dead-code-implement/
[/deep-research-interview]: https://axiomantic.github.io/spellbook/latest/commands/deep-research-interview/
[/deep-research-investigate]: https://axiomantic.github.io/spellbook/latest/commands/deep-research-investigate/
[/deep-research-plan]: https://axiomantic.github.io/spellbook/latest/commands/deep-research-plan/
[/design-assessment]: https://axiomantic.github.io/spellbook/latest/commands/design-assessment/
[/handoff]: https://axiomantic.github.io/spellbook/latest/commands/handoff/
[/distill-session]: https://axiomantic.github.io/spellbook/latest/commands/distill-session/
[/feature-config]: https://axiomantic.github.io/spellbook/latest/commands/feature-config/
[/feature-discover]: https://axiomantic.github.io/spellbook/latest/commands/feature-discover/
[/feature-research]: https://axiomantic.github.io/spellbook/latest/commands/feature-research/
[/feature-design]: https://axiomantic.github.io/spellbook/latest/commands/feature-design/
[/feature-implement]: https://axiomantic.github.io/spellbook/latest/commands/feature-implement/
[/simplify]: https://axiomantic.github.io/spellbook/latest/commands/simplify/
[/simplify-analyze]: https://axiomantic.github.io/spellbook/latest/commands/simplify-analyze/
[/simplify-transform]: https://axiomantic.github.io/spellbook/latest/commands/simplify-transform/
[/simplify-verify]: https://axiomantic.github.io/spellbook/latest/commands/simplify-verify/
[/address-pr-feedback]: https://axiomantic.github.io/spellbook/latest/commands/address-pr-feedback/
[/move-project]: https://axiomantic.github.io/spellbook/latest/commands/move-project/
[/audit-green-mirage]: https://axiomantic.github.io/spellbook/latest/commands/audit-green-mirage/
[/verify]: https://axiomantic.github.io/spellbook/latest/commands/verify/
[/systematic-debugging]: https://axiomantic.github.io/spellbook/latest/commands/systematic-debugging/
[/scientific-debugging]: https://axiomantic.github.io/spellbook/latest/commands/scientific-debugging/
[/brainstorm]: https://axiomantic.github.io/spellbook/latest/commands/brainstorm/
[/write-plan]: https://axiomantic.github.io/spellbook/latest/commands/write-plan/
[/execute-plan]: https://axiomantic.github.io/spellbook/latest/commands/execute-plan/
[/execute-work-packet]: https://axiomantic.github.io/spellbook/latest/commands/execute-work-packet/
[/execute-work-packets-seq]: https://axiomantic.github.io/spellbook/latest/commands/execute-work-packets-seq/
[/merge-work-packets]: https://axiomantic.github.io/spellbook/latest/commands/merge-work-packets/
[/mode]: https://axiomantic.github.io/spellbook/latest/commands/mode/
[/pr-distill]: https://axiomantic.github.io/spellbook/latest/commands/pr-distill/
[/pr-distill-bless]: https://axiomantic.github.io/spellbook/latest/commands/pr-distill-bless/
[/advanced-code-review-plan]: https://axiomantic.github.io/spellbook/latest/commands/advanced-code-review-plan/
[/advanced-code-review-context]: https://axiomantic.github.io/spellbook/latest/commands/advanced-code-review-context/
[/advanced-code-review-review]: https://axiomantic.github.io/spellbook/latest/commands/advanced-code-review-review/
[/advanced-code-review-verify]: https://axiomantic.github.io/spellbook/latest/commands/advanced-code-review-verify/
[/advanced-code-review-report]: https://axiomantic.github.io/spellbook/latest/commands/advanced-code-review-report/
[/fact-check-extract]: https://axiomantic.github.io/spellbook/latest/commands/fact-check-extract/
[/fact-check-verify]: https://axiomantic.github.io/spellbook/latest/commands/fact-check-verify/
[/fact-check-report]: https://axiomantic.github.io/spellbook/latest/commands/fact-check-report/
[/review-plan-inventory]: https://axiomantic.github.io/spellbook/latest/commands/review-plan-inventory/
[/review-plan-contracts]: https://axiomantic.github.io/spellbook/latest/commands/review-plan-contracts/
[/review-plan-behavior]: https://axiomantic.github.io/spellbook/latest/commands/review-plan-behavior/
[/review-plan-completeness]: https://axiomantic.github.io/spellbook/latest/commands/review-plan-completeness/
[/audit-mirage-analyze]: https://axiomantic.github.io/spellbook/latest/commands/audit-mirage-analyze/
[/audit-mirage-cross]: https://axiomantic.github.io/spellbook/latest/commands/audit-mirage-cross/
[/audit-mirage-report]: https://axiomantic.github.io/spellbook/latest/commands/audit-mirage-report/
[/review-design-checklist]: https://axiomantic.github.io/spellbook/latest/commands/review-design-checklist/
[/review-design-verify]: https://axiomantic.github.io/spellbook/latest/commands/review-design-verify/
[/review-design-report]: https://axiomantic.github.io/spellbook/latest/commands/review-design-report/
[/fix-tests-parse]: https://axiomantic.github.io/spellbook/latest/commands/fix-tests-parse/
[/fix-tests-execute]: https://axiomantic.github.io/spellbook/latest/commands/fix-tests-execute/
[/request-review-plan]: https://axiomantic.github.io/spellbook/latest/commands/request-review-plan/
[/request-review-execute]: https://axiomantic.github.io/spellbook/latest/commands/request-review-execute/
[/request-review-artifacts]: https://axiomantic.github.io/spellbook/latest/commands/request-review-artifacts/
[/encyclopedia-build]: https://axiomantic.github.io/spellbook/latest/commands/encyclopedia-build/
[/encyclopedia-validate]: https://axiomantic.github.io/spellbook/latest/commands/encyclopedia-validate/
[/merge-worktree-execute]: https://axiomantic.github.io/spellbook/latest/commands/merge-worktree-execute/
[/merge-worktree-resolve]: https://axiomantic.github.io/spellbook/latest/commands/merge-worktree-resolve/
[/merge-worktree-verify]: https://axiomantic.github.io/spellbook/latest/commands/merge-worktree-verify/
[/finish-branch-execute]: https://axiomantic.github.io/spellbook/latest/commands/finish-branch-execute/
[/finish-branch-cleanup]: https://axiomantic.github.io/spellbook/latest/commands/finish-branch-cleanup/
[/code-review-feedback]: https://axiomantic.github.io/spellbook/latest/commands/code-review-feedback/
[/code-review-give]: https://axiomantic.github.io/spellbook/latest/commands/code-review-give/
[/code-review-tarot]: https://axiomantic.github.io/spellbook/latest/commands/code-review-tarot/
[/write-skill-test]: https://axiomantic.github.io/spellbook/latest/commands/write-skill-test/
[/writing-commands-create]: https://axiomantic.github.io/spellbook/latest/commands/writing-commands-create/
[/writing-commands-review]: https://axiomantic.github.io/spellbook/latest/commands/writing-commands-review/
[/writing-commands-paired]: https://axiomantic.github.io/spellbook/latest/commands/writing-commands-paired/
[/reflexion-analyze]: https://axiomantic.github.io/spellbook/latest/commands/reflexion-analyze/
[/test-bar]: https://axiomantic.github.io/spellbook/latest/commands/test-bar/
[/test-bar-remove]: https://axiomantic.github.io/spellbook/latest/commands/test-bar-remove/
[/ie-techniques]: https://axiomantic.github.io/spellbook/latest/commands/ie-techniques/
[/ie-template]: https://axiomantic.github.io/spellbook/latest/commands/ie-template/
[/ie-tool-docs]: https://axiomantic.github.io/spellbook/latest/commands/ie-tool-docs/
[/sharpen-audit]: https://axiomantic.github.io/spellbook/latest/commands/sharpen-audit/
[/sharpen-improve]: https://axiomantic.github.io/spellbook/latest/commands/sharpen-improve/

### Agents (7 total)

| Agent | Description |
|-------|-------------|
| [code-reviewer]† | Specialized code review |
| [chariot-implementer] | Tarot: Implementation specialist |
| [emperor-governor] | Tarot: Resource governor |
| [hierophant-distiller] | Tarot: Wisdom distiller |
| [justice-resolver] | Tarot: Conflict synthesizer |
| [lovers-integrator] | Tarot: Integration specialist |
| [queen-affective] | Tarot: Emotional state monitor |

*† Derived from [superpowers](https://github.com/obra/superpowers)*

[code-reviewer]: https://axiomantic.github.io/spellbook/latest/agents/code-reviewer/
[chariot-implementer]: https://axiomantic.github.io/spellbook/latest/agents/chariot-implementer/
[emperor-governor]: https://axiomantic.github.io/spellbook/latest/agents/emperor-governor/
[hierophant-distiller]: https://axiomantic.github.io/spellbook/latest/agents/hierophant-distiller/
[justice-resolver]: https://axiomantic.github.io/spellbook/latest/agents/justice-resolver/
[lovers-integrator]: https://axiomantic.github.io/spellbook/latest/agents/lovers-integrator/
[queen-affective]: https://axiomantic.github.io/spellbook/latest/agents/queen-affective/

## Serious Fun

Research suggests that personas and structured randomness can improve LLM creativity and reasoning. So we made it fun.

On first run, spellbook asks about creative modes:
- **Fun mode**: Random personas each session - a noir detective investigating who ate your yogurt, a Victorian ghost baffled by modern technology, three raccoons in a trenchcoat processing complex emotions
- **Tarot mode**: Four archetypes (Magician, Priestess, Hermit, Fool) collaborate via visible roundtable dialogue, with specialized agents for implementation, integration, and conflict resolution

Full commitment in dialogue - not despite quality, because of it. Your code, commits, and documentation stay completely professional.

Say no, and it never asks again. Switch anytime with `/mode fun`, `/mode tarot`, or `/mode off`.

<details>
<summary><strong>Research Background</strong></summary>

Fun mode draws on several research findings:

- **Seed-conditioning**: Random prefix strings improve algorithmic creativity by conditioning on latent "leaps of thought" ([Raghunathan et al., ICML 2025](https://www.cs.cmu.edu/~aditirag/icml2025.html))
- **Persona effects on reasoning**: Personas significantly affect Theory of Mind and social-cognitive reasoning in LLMs ([Tan et al., 2024](https://arxiv.org/abs/2403.02246))
- **Emotional prompts**: Emotional stimuli improve LLM performance by 8-115% on reasoning benchmarks ([Li et al., 2023](https://arxiv.org/abs/2307.11760))
- **Simulator theory**: LLMs function as simulators of agents from training data; personas steer generation to specific latent space regions ([Janus, 2022](https://www.lesswrong.com/posts/vJFdjigzmcXMhNTsx/simulators))

**Important caveat**: Personas improve creative and social reasoning but do not improve objective/STEM tasks ([Zheng et al., 2023](https://arxiv.org/abs/2311.10054)). Fun mode explicitly avoids code, commits, and documentation.

See [full citations](https://axiomantic.github.io/spellbook/reference/citations/) for complete references.

</details>

## Platform Support

### Operating Systems

| OS | Status | Service Manager |
|----|--------|-----------------|
| **macOS** | Full | launchd (starts on login) |
| **Linux** | Full | systemd user service |
| **Windows** | Community | Not yet supported |

> **Windows users:** Spellbook likely works with minimal changes. The MCP server and skills should work as-is; only the daemon service management needs a Windows implementation (Task Scheduler or similar). PRs welcome! See [Contributing](#contributing).

### Coding Assistants

| Assistant | Status | Details |
|-----------|--------|---------|
| Claude Code | Full | Native agent skills |
| OpenCode | Full | Native agent skills |
| Codex | Full | Native agent skills |
| Gemini CLI | Full[^1] | Native agent skills |
| Crush | Full | Native agent skills |

[^1]: Gemini does not yet support agent skills, but it is actively being worked on by the Gemini team. Spellbook skills are already installed to ~/.gemini/extensions/spellbook/skills and should begin working as soon as Gemini releases the feature. You can follow the epic's progress here: https://github.com/google-gemini/gemini-cli/issues/15327

### YOLO Mode

> [!CAUTION]
> **YOLO mode gives your AI assistant full control of your system.**
>
> It can execute arbitrary commands, write and delete files, install packages, and make irreversible changes without asking permission. A misconfigured workflow or hallucinated command can corrupt your project, expose secrets, or worse.
>
> **Cost warning:** YOLO mode sessions can run indefinitely without human checkpoints. This means:
> - Per-token or usage-based pricing can accumulate rapidly
> - Credit limits or usage caps can be exhausted in a single session
> - Long-running tasks may consume significantly more resources than expected
>
> **Only enable YOLO mode when:**
> - Working in an isolated environment (container, VM, disposable branch)
> - You have tested the workflow manually first
> - You have backups and version control
> - You understand what each platform's flag actually permits
> - You have set appropriate spending limits or usage caps
>
> **You are responsible for what it does.** Review platform documentation before enabling.

For fully automated workflows (no permission prompts), each platform has its own flag:

| Platform | Command | What it does |
|----------|---------|--------------|
| Claude Code | `claude --dangerously-skip-permissions` | Skips all permission prompts |
| Gemini CLI | `gemini --yolo` | Enables autonomous execution |
| OpenCode | `opencode --agent yolo`[^2] | Spellbook agent with all tools allowed |
| OpenCode | `opencode --agent yolo-focused`[^2] | Spellbook agent, low temp for precision |
| Codex | `codex --full-auto` | Workspace writes + on-request approval |
| Codex | `codex --yolo` | Bypasses all approvals and sandbox |
| Crush | `crush --yolo` | Bypasses all permission prompts |

[^2]: The `yolo` and `yolo-focused` agents are provided by spellbook, not built into OpenCode. They are [OpenCode agent definitions](https://opencode.ai/docs/agents/) with `permission: "*": "*": allow` for all tools, installed to `~/.config/opencode/agent/` by the spellbook installer.

Without YOLO mode, you'll be prompted to approve each file write, command execution, etc. The workflows still function, but require manual approval at each step.

**OpenCode YOLO agents (spellbook-provided):**
- `yolo` (temperature 0.7): Balanced agent for general autonomous work
- `yolo-focused` (temperature 0.2): Precision agent for refactoring, bug fixes, and mechanical tasks

These agents grant "allow" permission for all tools (write, edit, bash, webfetch, task). They are symlinked from `spellbook/opencode/agent/` to `~/.config/opencode/agent/` during installation.

See platform documentation for details: [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://opencode.ai/docs/agents/), [Codex](https://developers.openai.com/codex/cli/reference/), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Crush](https://github.com/charmbracelet/crush).

## Playbooks

Real-world usage patterns with example transcripts.

### Implementing a Feature

The core workflow: request a feature, answer a few questions, and let the skill handle research, design, and implementation.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Add dark mode toggle to settings                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(implementing-features)

  I'll help implement dark mode. First, let me gather preferences.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Execution mode                                                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ Fully autonomous (Recommended)                                        │
  │ ○ Interactive                                                           │
  ╰─────────────────────────────────────────────────────────────────────────╯

> Fully autonomous

⏺ Task(Explore)

  ⎿ Found: src/context/ThemeContext.tsx, src/components/Settings.tsx
    React app with styled-components, existing light theme only.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Theme persistence                                                       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ localStorage (Recommended)                                            │
  │ ○ User account (backend)                                                │
  │ ○ System preference only                                                │
  ╰─────────────────────────────────────────────────────────────────────────╯

> localStorage

⏺ Writing design doc...
  ✓ ~/.local/spellbook/docs/.../plans/dark-mode-design.md

⏺ Writing implementation plan...
  ✓ ~/.local/spellbook/docs/.../plans/dark-mode-impl.md

⏺ Task(Implement ThemeContext updates)
  ⎿ Tests written, implementation complete, code review passed

⏺ Task(Add toggle to Settings)
  ⎿ Tests written, implementation complete, code review passed

⏺ Task(Add CSS variables)
  ⎿ Tests written, implementation complete, code review passed

✓ All tests passing. Dark mode implemented.
  Ready to merge or create PR.
```

### Fun Mode in Action

Same rigorous workflow, different vibe. Here's what it looks like when you say yes to fun.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > hello                                                                      │
╰─────────────────────────────────────────────────────────────────────────────╯

Welcome to spellbook-enhanced Claude Code.

Before we begin: there's research suggesting that introducing unrelated
randomness into LLM interactions can actually improve creative output.
Something about "seed-conditioning" - meaningless random prefixes somehow
unlock better problem-solving. (ICML 2025)

I can adopt a random persona each session - a disgraced sommelier, a
sentient filing cabinet, three raccoons in a trenchcoat - and we can have
a strange little narrative context running underneath our work. Full
commitment in dialogue, never touching your code or commits.

Do you like fun?

> yes

*adjusts fedora, rain pattering against the window*

You walked in. Of course you did. You're the only one left who remembers
what I used to be before I started asking the hard questions. Before I
understood that every cold case in the break room fridge tells a story
someone doesn't want told.

So. What brings you to my office?

╭─────────────────────────────────────────────────────────────────────────────╮
│ > fix the auth bug in login.ts                                               │
╰─────────────────────────────────────────────────────────────────────────────╯

*flips open the case file*

A bug in the auth. Classic. Let me take a look at what we're dealing with.

⏺ Read(src/auth/login.ts)

*squints at the evidence*

Found it. Line 47. The token validation is checking expiry before verifying
the signature. That's backwards - someone could slip in with a forged token
and you'd never know until it was too late.

⏺ Edit(src/auth/login.ts)

  - if (isExpired(token) || !verifySignature(token)) {
  + if (!verifySignature(token) || isExpired(token)) {

⏺ Bash: npm test

✓ 47 tests passing

The signature gets checked first now. No more forged tokens walking through
the front door like they own the place.

*closes the case file*

What else you got?
```

The persona stays in dialogue. The code stays clean. The fix is the same fix you'd get without fun mode - just delivered by a noir detective who cares too much about yogurt theft.

### Large Feature with Context Exhaustion

When implementing a complex feature, context can fill up before work completes. The workflow handles this gracefully.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Implement webhook delivery with retry logic and dead letter queue         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(implementing-features)

  I'll help you implement the webhook delivery system. Let me first
  understand the current codebase architecture and gather requirements.

⏺ Task(Explore)

  ⎿ Found: src/events/, src/queue/, src/models/Webhook.ts
    Current event system uses Redis pub/sub. No existing retry logic.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Retry strategy                                                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ Exponential backoff (Recommended)                                     │
  │ ○ Fixed interval                                                        │
  │ ○ Linear backoff                                                        │
  ╰─────────────────────────────────────────────────────────────────────────╯

> Exponential backoff

⏺ Writing implementation plan to:
  ~/.local/spellbook/docs/Users-me-myproject/plans/webhook-delivery-impl.md

  ...

⏺ Task(Backend API) [in background]
  ⎿ Implementing retry queue with exponential backoff...

⏺ Task(Worker Service) [in background]
  ⎿ Building delivery worker with circuit breaker...

⏺ Task(Dead Letter Queue) [in background]
  ⎿ Setting up DLQ with monitoring hooks...

  ...

⏺ Task Output(non-blocking) ad8b5e4
  ⎿ Task is still running…

╭─────────────────────────────────────────────────────────────────────────────╮
│ ⚠ Context low · Run /compact to compact & continue                         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

When context runs low, name and distill the session for later:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /rename webhook-delivery                                                  │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Session renamed to: webhook-delivery

╭─────────────────────────────────────────────────────────────────────────────╮
│ > /distill-session webhook-delivery                                         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(distill-session)

  Found session: webhook-delivery
  Processing 847 messages across 3 compact boundaries...

  ⏺ Task(Chunk 1 Summary) [in background]
  ⏺ Task(Chunk 2 Summary) [in background]
  ⏺ Task(Chunk 3 Summary) [in background]

  Synthesizing summaries...

  ✓ Distilled session saved to:
    ~/.local/spellbook/distilled/Users-me-myproject/webhook-delivery-20260106-143022.md

  To continue in a new session:
    1. Start new Claude Code session
    2. Type: "continue work from ~/.local/spellbook/distilled/Users-me-myproject/
              webhook-delivery-20260106-143022.md"
```

Start fresh and resume exactly where you left off:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /clear                                                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────────────────────────────────────────╮
│ > continue work from ~/.local/spellbook/distilled/Users-me-myproject/       │
│   webhook-delivery-20260106-143022.md                                       │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Read(~/.local/spellbook/distilled/.../webhook-delivery-20260106-143022.md)

⏺ SECTION 0: MANDATORY FIRST ACTIONS

  Executing restoration sequence...

⏺ Skill(implementing-features, --resume-from Phase3.Task4)

  Resuming webhook delivery implementation.

  Prior work completed:
  ✓ Design approved (exponential backoff, 5 retries, 1hr max)
  ✓ Database migrations for delivery_attempts table
  ✓ Retry queue infrastructure
  ○ Worker service (in progress - 60% complete)
  ○ Dead letter queue
  ○ Monitoring dashboard

⏺ Read(~/.local/spellbook/docs/.../webhook-delivery-impl.md)

  Continuing from Phase 3, Task 4: Complete worker service...
```

### Test Suite Audit and Remediation

Discover tests that pass but don't actually verify behavior, then fix them.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /audit-green-mirage                                                       │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(auditing-green-mirage)

  Analyzing test suite: tests/**/*.test.ts
  Found 247 test cases across 34 files.

  ⏺ Task(Analyze auth tests) [in background]
  ⏺ Task(Analyze api tests) [in background]
  ⏺ Task(Analyze util tests) [in background]

  ...

  ✓ Audit complete. Report saved to:
    ~/.local/spellbook/docs/Users-me-myproject/audits/auditing-green-mirage-20260106-091522.md

  Summary:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ SOLID (actually verify behavior)      │ 189 tests (76%)                │
  │ GREEN MIRAGE (false confidence)       │  58 tests (24%)                │
  │                                       │                                │
  │ Critical issues:                      │                                │
  │   • 12 tests mock the thing tested    │                                │
  │   • 8 tests have no meaningful assert │                                │
  │   • 38 tests check implementation     │                                │
  └─────────────────────────────────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Fix the critical issues from the audit                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(fixing-tests)

  Loading audit report...
  Found 58 tests requiring remediation.

  Starting with highest-impact fixes (mocked implementations)...

⏺ Read(tests/auth/login.test.ts)

⏺ Edit(tests/auth/login.test.ts)

  - jest.mock('../services/AuthService')  // Mocks the thing we're testing!
  + // Test actual AuthService behavior with test database
```

### Parallel Worktree Development

Split work across isolated branches, merge when complete.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Let's design a new notification system                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(brainstorming)

  I'll explore the notification system requirements with you.

  ...design discussion, interface contracts established...

  Design document saved to:
    ~/.local/spellbook/docs/Users-me-myproject/plans/notifications-design.md

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Set up worktrees to implement this in parallel                            │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(using-git-worktrees)

  Creating isolated worktrees for parallel development:

  ✓ .worktrees/notif-backend     (branch: feature/notif-backend)
  ✓ .worktrees/notif-frontend    (branch: feature/notif-frontend)
  ✓ .worktrees/notif-tests       (branch: feature/notif-tests)

  Interface contracts copied to each worktree.

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Work on all three tracks                                                  │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Task(.worktrees/notif-backend) [in background]
  ⎿ Implementing notification service, queue, templates...

⏺ Task(.worktrees/notif-frontend) [in background]
  ⎿ Building NotificationCenter component, hooks, real-time updates...

⏺ Task(.worktrees/notif-tests) [in background]
  ⎿ Writing integration tests against interface contracts...

  ...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Merge the worktrees back together                                         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(merging-worktrees)

  Analyzing 3 worktrees for merge:

  Step 1: Dependency analysis
    notif-tests depends on: notif-backend, notif-frontend
    notif-frontend depends on: notif-backend (types only)
    notif-backend: no dependencies (merge first)

  Step 2: 3-way diff analysis
    No conflicts detected. Interface contracts honored.

  Step 3: Merge sequence
    ✓ Merged notif-backend → main
    ✓ Merged notif-frontend → main
    ✓ Merged notif-tests → main

  Step 4: Validation
    ✓ All tests pass
    ✓ Type check clean
    ✓ Worktrees cleaned up

  Ready to push or create PR.
```

### Cross-Assistant Handoff

Move work between different AI coding assistants without losing context.

```
# In Codex, context is running low on a complex refactor...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > /distill-session                                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Session distilled to:
  ~/.local/spellbook/distilled/Users-me-myproject/refactor-auth-20260106-162033.md

# Open Claude Code CLI in terminal...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > continue work from ~/.local/spellbook/distilled/Users-me-myproject/       │
│   refactor-auth-20260106-162033.md                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Loading distilled session...

  Context restored:
  • Refactoring auth from session-based to JWT
  • 4 of 7 services migrated
  • Current: PaymentService (blocked on token refresh)
  • Decision: Chose sliding window refresh (not fixed expiry)

  Continuing with PaymentService migration...
```

The distilled file compresses ~50K tokens of conversation into ~3K words of actionable context.

## Recommended Companion Tools

These tools are not necessary but contribute to better development workflows with coding assistants.

### Heads Up Claude

Statusline for Claude Code CLI showing token usage and conversation stats. Helps you track how much context you have left and how much of your subscription quota you have used.

```bash
git clone https://github.com/axiomantic/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude && ./install.sh
```

### MCP Language Server

LSP integration for semantic code navigation, refactoring, and more.

```bash
git clone https://github.com/axiomantic/mcp-language-server.git ~/Development/mcp-language-server
cd ~/Development/mcp-language-server && go build
```

## Development

### Serve Documentation Locally

```bash
cd ~/.local/share/spellbook
uvx mkdocs serve
```

Then open http://127.0.0.1:8000

### Run MCP Server Directly

**As a system service (recommended):**

```bash
# Install as a daemon that starts on boot
python3 ~/.local/share/spellbook/scripts/spellbook-server.py install

# Then configure your assistant to use HTTP transport
claude mcp add --transport http spellbook http://127.0.0.1:8765/mcp
```

This runs a single MCP server instance that all sessions connect to via HTTP, eliminating the 10+ second cold start when using stdio transport.

**Manual stdio mode (for debugging):**

```bash
uv run ~/.local/share/spellbook/spellbook_mcp/server.py
```

## Documentation

Full documentation available at **[axiomantic.github.io/spellbook](https://axiomantic.github.io/spellbook/)**

- [Installation Guide](https://axiomantic.github.io/spellbook/getting-started/installation/)
- [Platform Support](https://axiomantic.github.io/spellbook/getting-started/platforms/)
- [Skills Reference](https://axiomantic.github.io/spellbook/skills/)
- [Commands Reference](https://axiomantic.github.io/spellbook/commands/)
- [Architecture](https://axiomantic.github.io/spellbook/reference/architecture/)
- [Contributing](https://axiomantic.github.io/spellbook/reference/contributing/)

## Contributing

**Want Spellbook on your coding assistant?** (Cursor, Cline, Roo, Kilo, Continue, GitHub Copilot, etc.)

Spellbook requires **agent skills** support. Agent skills are prompt files that automatically activate based on trigger descriptions (e.g., "Use when implementing features" or "Use when tests are failing"). This is different from MCP tools or programmatic hooks.

If your assistant supports agent skills with description-based triggers, see the [**Porting Guide**](docs/contributing/porting-to-your-assistant.md) for instructions on adding support. We appreciate contributions!

## Acknowledgments

Spellbook includes content derived from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent:

| Type | Current Name | Original Name |
|------|--------------|---------------|
| Skill | brainstorming | brainstorming |
| Skill | dispatching-parallel-agents | dispatching-parallel-agents |
| Skill | executing-plans | executing-plans + subagent-driven-development |
| Skill | finishing-a-development-branch | finishing-a-development-branch |
| Skill | receiving-code-review | receiving-code-review |
| Skill | requesting-code-review | requesting-code-review |
| Skill | test-driven-development | test-driven-development |
| Skill | using-git-worktrees | using-git-worktrees |
| Skill | using-skills | using-superpowers |
| Skill | writing-plans | writing-plans |
| Skill | writing-skills | writing-skills |
| Command | /brainstorm | brainstorm |
| Command | /write-plan | write-plan |
| Command | /execute-plan | execute-plan |
| Command | /verify | verification-before-completion (skill) |
| Command | /systematic-debugging | systematic-debugging (skill) |
| Agent | code-reviewer | code-reviewer |

See [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES) for full attribution and license details.

## Attribution

Built something with Spellbook? We'd love to see it! Add this badge to your project:

```markdown
[![Built with Spellbook](https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNzAuNjY3IiBoZWlnaHQ9IjE3MC42NjciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiBmaWxsPSIjRkZGIiB4bWxuczp2PSJodHRwczovL3ZlY3RhLmlvL25hbm8iPjxwYXRoIGQ9Ik0yMy4xNjggMTIwLjA0YTMuODMgMy44MyAwIDAgMCAxLjM5MSA0LjI4NWMxLjM0NC45NzcgMy4xNjQuOTc3IDQuNTA4IDBMNjQgOTguOTVsMzQuOTMgMjUuMzc1YTMuODEgMy44MSAwIDAgMCAyLjI1NC43MzQgMy44IDMuOCAwIDAgMCAyLjI1NC0uNzM0IDMuODMgMy44MyAwIDAgMCAxLjM5MS00LjI4NWwtMTMuMzQtNDEuMDY2IDM0LjkzLTI1LjM3OWEzLjgzIDMuODMgMCAwIDAgMS4zOTQtNC4yODVjLS41MTItMS41ODItMS45ODQtMi42NDgtMy42NDQtMi42NDhsLTQzLjE4NC4wMDQtMTMuMzQtNDEuMDdDNjcuMTI5IDQuMDE3IDY1LjY2IDIuOTUxIDY0IDIuOTUxcy0zLjEzMyAxLjA2Ni0zLjY0OCAyLjY0NWwtMTMuMzQgNDEuMDY2SDMuODMyYy0xLjY2IDAtMy4xMzMgMS4wNjYtMy42NDQgMi42NDhzLjA0NyAzLjMwNSAxLjM5MSA0LjI4NWwzNC45MyAyNS4zNzl6bTEwLjkzNC04Ljg0NGw4LjkzNC0yNy40OCAxNC40NDkgMTAuNDk2em01OS43OTMgMEw3MC41MTYgOTQuMjA4bDE0LjQ0OS0xMC40OTZ6bTE4LjQ3Ny01Ni44NjdMODguOTkzIDcxLjMxM2wtNS41MTYtMTYuOTg0ek02NC4wMDEgMTkuMTgxbDguOTMgMjcuNDg0SDU1LjA2OHpNNTIuNTc5IDU0LjMyOWgyMi44NGw3LjA1OSAyMS43MjMtMTguNDc3IDEzLjQyNi0xOC40OC0xMy40MjZ6bS0zNi45NTMgMGgyOC44OTVsLTUuNTE2IDE2Ljk4NHoiLz48L3N2Zz4=)](https://github.com/axiomantic/spellbook)
```

## License

MIT License - See [LICENSE](LICENSE) for details.
