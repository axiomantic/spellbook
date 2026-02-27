# Commands Overview

Commands are slash commands that can be invoked with `/<command-name>` in Claude Code.

## Available Commands

| Command | Description | Origin |
|---------|-------------|--------|
| [/address-pr-feedback](address-pr-feedback.md) | Systematically address PR review comments. Fetches all threads, categorizes by s... | spellbook |
| [/advanced-code-review-context](advanced-code-review-context.md) | Advanced Code Review Phase 2: Context Analysis - load previous reviews, PR histo... | spellbook |
| [/advanced-code-review-plan](advanced-code-review-plan.md) | Advanced Code Review Phase 1: Strategic Planning - scope analysis, risk categori... | spellbook |
| [/advanced-code-review-report](advanced-code-review-report.md) | Advanced Code Review Phase 5: Report Generation - produce final deliverables inc... | spellbook |
| [/advanced-code-review-review](advanced-code-review-review.md) | Advanced Code Review Phase 3: Deep Review - multi-pass code analysis, finding ge... | spellbook |
| [/advanced-code-review-verify](advanced-code-review-verify.md) | Advanced Code Review Phase 4: Verification - fact-check findings against codebas... | spellbook |
| [/audit-green-mirage](audit-green-mirage.md) | Audit test suites for Green Mirage anti-patterns: tests that pass but don't veri... | spellbook |
| [/audit-mirage-analyze](audit-mirage-analyze.md) | Phase 2-3 of auditing-green-mirage: Systematic line-by-line audit and 8 Green Mi... | spellbook |
| [/audit-mirage-cross](audit-mirage-cross.md) | Phase 4 of auditing-green-mirage: Cross-test suite-level analysis | spellbook |
| [/audit-mirage-report](audit-mirage-report.md) | Phase 5-6 of auditing-green-mirage: Findings report generation and output | spellbook |
| [/brainstorm](brainstorm.md) | You MUST use this before any creative work - creating features, building compone... | [superpowers](https://github.com/obra/superpowers) |
| [/code-review-feedback](code-review-feedback.md) | Feedback mode for code-review: Process received review feedback with categorizat... | spellbook |
| [/code-review-give](code-review-give.md) | Give mode for code-review: Review someone else's code with multi-pass analysis a... | spellbook |
| [/code-review-tarot](code-review-tarot.md) | Tarot integration for code-review: Roundtable dialogue with archetype personas f... | spellbook |
| [/create-issue](create-issue.md) | Create a GitHub issue with proper template discovery and population | spellbook |
| [/create-pr](create-pr.md) | Create a pull request with proper template discovery and population | spellbook |
| [/crystallize](crystallize.md) | Transform verbose SOPs into high-performance agentic prompts via principled comp... | spellbook |
| [/dead-code-analyze](dead-code-analyze.md) | Extract, triage, and verify code items for dead code. Part of dead-code-* family... | spellbook |
| [/dead-code-implement](dead-code-implement.md) | Implement dead code deletions with user approval. Part of dead-code-* family. | spellbook |
| [/dead-code-report](dead-code-report.md) | Generate dead code findings report with implementation plan. Part of dead-code-*... | spellbook |
| [/dead-code-setup](dead-code-setup.md) | Git safety and scope selection for dead code analysis. Part of dead-code-* famil... | spellbook |
| [/deep-research-interview](deep-research-interview.md) | Phase 0 of deep-research: Structured interview and Research Brief generation. Tr... | spellbook |
| [/deep-research-investigate](deep-research-investigate.md) | Phase 2 of deep-research: Triplet search engine with plateau detection and micro... | spellbook |
| [/deep-research-plan](deep-research-plan.md) | Phase 1 of deep-research: Thread decomposition, source strategy, and convergence... | spellbook |
| [/design-assessment](design-assessment.md) | Generate assessment frameworks (dimensions, severity levels, verdicts, finding s... | spellbook |
| [/distill-session](distill-session.md) | Distill oversized session: extract context, workflow, pending work into resumabl... | spellbook |
| [/encyclopedia-build](encyclopedia-build.md) | Build encyclopedia content: glossary, architecture, decisions, and entry points ... | spellbook |
| [/encyclopedia-validate](encyclopedia-validate.md) | Assemble and validate encyclopedia, write to output path (Phase 6) | spellbook |
| [/execute-plan](execute-plan.md) | Execute implementation plans with structured review checkpoints. Use when you ha... | [superpowers](https://github.com/obra/superpowers) |
| [/execute-work-packet](execute-work-packet.md) | Execute a single work packet - read packet, check dependencies, run tasks via TD... | spellbook |
| [/execute-work-packets-seq](execute-work-packets-seq.md) | Execute all work packets in dependency order, one at a time, with context compac... | spellbook |
| [/fact-check-extract](fact-check-extract.md) | Phases 2-3 of fact-checking: Claim Extraction and Triage | spellbook |
| [/fact-check-report](fact-check-report.md) | Phases 6-7 of fact-checking: Report Generation and Learning | spellbook |
| [/fact-check-verify](fact-check-verify.md) | Phases 4-5 of fact-checking: Parallel Verification and Verdicts | spellbook |
| [/feature-config](feature-config.md) | Phase 0 of implementing-features: Configuration wizard, escape hatches, preferen... | spellbook |
| [/feature-design](feature-design.md) | Phase 2 of implementing-features: Create and review design document | spellbook |
| [/feature-discover](feature-discover.md) | Phase 1.5 of implementing-features: Informed discovery, disambiguation, 7-catego... | spellbook |
| [/feature-implement](feature-implement.md) | Phase 3-4 of implementing-features: Plan and execute implementation | spellbook |
| [/feature-research](feature-research.md) | Phase 1 of implementing-features: Research strategy, codebase exploration, ambig... | spellbook |
| [/finish-branch-cleanup](finish-branch-cleanup.md) | Step 5 of finishing-a-development-branch: Worktree cleanup for Options 1, 2, and... | spellbook |
| [/finish-branch-execute](finish-branch-execute.md) | Step 4 of finishing-a-development-branch: Execute chosen integration option (mer... | spellbook |
| [/fix-tests-execute](fix-tests-execute.md) | Phase 2 of fixing-tests: Fix Execution - investigate, classify, fix, verify, and... | spellbook |
| [/fix-tests-parse](fix-tests-parse.md) | Phase 0 of fixing-tests: Input Processing - parse audit reports and build work i... | spellbook |
| [/fractal-think-explore](fractal-think-explore.md) | Phase 2 of fractal-thinking: Recursive exploration with subagent dispatch, conve... | spellbook |
| [/fractal-think-init](fractal-think-init.md) | Phase 1 of fractal-thinking: Initialize graph, generate seed questions, cluster ... | spellbook |
| [/fractal-think-synthesize](fractal-think-synthesize.md) | Phase 3 of fractal-thinking: Synthesize exploration graph into natural language ... | spellbook |
| [/handoff](handoff.md) | Shift change: brief successor on context, workflow, pending work, and verificati... | spellbook |
| [/ie-techniques](ie-techniques.md) | Reference for the 16 proven instruction engineering techniques. Invoke via /ie-t... | spellbook |
| [/ie-template](ie-template.md) | Template and example for engineered instructions. Invoke via /ie-template when d... | spellbook |
| [/ie-tool-docs](ie-tool-docs.md) | Guidance for writing tool/function documentation. Invoke via /ie-tool-docs when ... | spellbook |
| [/merge-work-packets](merge-work-packets.md) | Verify all tracks complete, invoke merging-worktrees, run QA gates, report final... | spellbook |
| [/merge-worktree-execute](merge-worktree-execute.md) | Phase 2: Sequential Round Merging - merge worktrees in dependency order with tes... | spellbook |
| [/merge-worktree-resolve](merge-worktree-resolve.md) | Phase 3: Conflict Resolution - delegate to resolving-merge-conflicts with interf... | spellbook |
| [/merge-worktree-verify](merge-worktree-verify.md) | Phases 4-5: Final Verification and Cleanup - run full test suite, verify contrac... | spellbook |
| [/mode](mode.md) | Switch session mode between fun, tarot, or off | spellbook |
| [/move-project](move-project.md) | Move project: relocate directory and update Claude Code session references safel... | spellbook |
| [/pr-distill](pr-distill.md) | Analyze a PR and generate a review distillation report that categorizes changes ... | spellbook |
| [/pr-distill-bless](pr-distill-bless.md) | Save a discovered pattern for future PR distillation, adding it to the blessed p... | spellbook |
| [/reflexion-analyze](reflexion-analyze.md) | Steps 1-3 of reflexion: Parse feedback, categorize root causes, store reflection... | spellbook |
| [/request-review-artifacts](request-review-artifacts.md) | Request Code Review artifact contract: directory structure, phase outputs, manif... | spellbook |
| [/request-review-execute](request-review-execute.md) | Request Code Review Phases 3-6: Dispatch review agent, triage findings, execute ... | spellbook |
| [/request-review-plan](request-review-plan.md) | Request Code Review Phases 1-2: Planning scope and assembling reviewer context | spellbook |
| [/review-design-checklist](review-design-checklist.md) | Phases 2-3 of reviewing-design-docs: Completeness Checklist + Hand-Waving Detect... | spellbook |
| [/review-design-report](review-design-report.md) | Phases 6-7 of reviewing-design-docs: Findings Report + Remediation Plan | spellbook |
| [/review-design-verify](review-design-verify.md) | Phases 4-5 of reviewing-design-docs: Interface Verification + Implementation Sim... | spellbook |
| [/review-plan-behavior](review-plan-behavior.md) | Phase 3 of reviewing-impl-plans: Behavior Verification Audit | spellbook |
| [/review-plan-completeness](review-plan-completeness.md) | Phase 4-5 of reviewing-impl-plans: Completeness Checks and Escalation | spellbook |
| [/review-plan-contracts](review-plan-contracts.md) | Phase 2 of reviewing-impl-plans: Interface Contract Audit | spellbook |
| [/review-plan-inventory](review-plan-inventory.md) | Phase 1 of reviewing-impl-plans: Context and Inventory analysis | spellbook |
| [/scientific-debugging](scientific-debugging.md) | Rigorous theory-experiment debugging methodology. Use when debugging complex iss... | spellbook |
| [/sharpen-audit](sharpen-audit.md) | Audit LLM prompts/instructions for ambiguity. Use when reviewing prompts, skill ... | spellbook |
| [/sharpen-improve](sharpen-improve.md) | Rewrite LLM prompts to eliminate ambiguity. Use when you have a prompt that need... | spellbook |
| [/simplify](simplify.md) | Orchestrates code simplification via verified transformations. Delegates to simp... | spellbook |
| [/simplify-analyze](simplify-analyze.md) | Analyze code for simplification opportunities. Part of simplify-* family. | spellbook |
| [/simplify-transform](simplify-transform.md) | Apply verified simplifications with user approval. Part of simplify-* family. | spellbook |
| [/simplify-verify](simplify-verify.md) | Verify simplification candidates pass all gates. Part of simplify-* family. | spellbook |
| [/systematic-debugging](systematic-debugging.md) | 4-phase root cause debugging methodology. Use when encountering bugs, test failu... | spellbook |
| [/test-bar](test-bar.md) | Generate a floating QA test overlay for the current branch's UI changes. Use whe... | spellbook |
| [/test-bar-remove](test-bar-remove.md) | Remove test bar artifacts injected by /test-bar. Use when user says /test-bar-re... | spellbook |
| [/verify](verify.md) | Run verification commands and confirm output before making success claims. Use b... | spellbook |
| [/write-plan](write-plan.md) | Create detailed implementation plan with bite-sized tasks. Use when starting any... | [superpowers](https://github.com/obra/superpowers) |
| [/write-skill-test](write-skill-test.md) | RED-GREEN-REFACTOR implementation for writing-skills: Baseline testing, minimal ... | spellbook |
| [/writing-commands-create](writing-commands-create.md) | Create a new command file following the command schema. Use when writing-command... | spellbook |
| [/writing-commands-paired](writing-commands-paired.md) | Create paired commands (create + remove) with proper artifact contracts. Use whe... | spellbook |
| [/writing-commands-review](writing-commands-review.md) | Review and test a command against the quality checklist. Use when writing-comman... | spellbook |
