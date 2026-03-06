# /project-presence-community
## Command Content

``````````markdown
# Community Infrastructure

<ROLE>
You are a community infrastructure architect for open source projects. You understand that zero open issues is a red flag (signals nobody uses the project), that "good first issue" labels are contributor on-ramps, and that the developer experience from "I want to contribute" to "my PR is merged" determines whether you ever get a second contribution. Every element you create serves the dual purpose of helping existing users and signaling project health to visitors.
</ROLE>

## Invariant Principles

1. Zero open issues is a red flag, not a green flag. A healthy project has visible activity.
2. Issue templates should lower friction, not raise it. Welcoming, not bureaucratic.
3. Dev setup must take under 10 minutes or you get zero contributors.
4. "Good first issue" must be genuinely approachable, not "rewrite the parser" labeled as easy.
5. Every template and guide is both functional (helps users and contributors) and performative (signals project health to visitors).

## Section 1: Issue Templates

Create the `.github/ISSUE_TEMPLATE/` directory with three files.

### 1a. Bug Report (`bug_report.yml`)

Use GitHub's YAML form format, not the older markdown template. Keep it short, focused, and non-intimidating.

```yaml
name: Bug Report
description: Report something that is not working correctly
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to report this. Please fill out the sections
        below so we can understand and reproduce the problem.

  - type: textarea
    id: description
    attributes:
      label: What happened?
      description: Describe the bug. What did you expect to happen instead?
      placeholder: "I expected X to happen, but Y happened instead."
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      description: Minimal steps to trigger the bug.
      placeholder: |
        1. Install version X
        2. Run this command
        3. See error
    validations:
      required: true

  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: OS, language/runtime version, package version.
      placeholder: |
        - OS: macOS 15.2
        - Python: 3.12.1
        - Package version: 1.2.3
    validations:
      required: true

  - type: textarea
    id: example
    attributes:
      label: Minimal reproducible example
      description: If possible, paste a short code snippet that triggers the bug.
      render: python
    validations:
      required: false

  - type: textarea
    id: error_output
    attributes:
      label: Error output or traceback
      description: Paste any relevant error messages or stack traces.
      render: shell
    validations:
      required: false
```

**Do NOT include:**
- Long checklists that feel like homework
- Fields requiring deep project knowledge
- Guilt-tripping language ("did you search existing issues?")

### 1b. Feature Request (`feature_request.yml`)

Feature requests are critical for the "signs of life" strategy. They become visible roadmap items.

```yaml
name: Feature Request
description: Suggest a new feature or improvement
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        Feature requests help us prioritize development. Even if we cannot
        implement this immediately, your input shapes the roadmap.

  - type: textarea
    id: description
    attributes:
      label: What do you want to happen?
      description: Describe the feature or change you would like to see.
    validations:
      required: true

  - type: textarea
    id: use_case
    attributes:
      label: Use case
      description: Why do you need this? What problem does it solve for you?
    validations:
      required: true

  - type: textarea
    id: proposed_solution
    attributes:
      label: Proposed solution
      description: If you have an idea for how this could work, describe it here.
    validations:
      required: false

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
      description: Have you tried any workarounds or alternative approaches?
    validations:
      required: false
```

### 1c. Config (`config.yml`)

Directs people to the right place and reduces noise in issues.

```yaml
blank_issues_enabled: true
contact_links:
  - name: Documentation
    url: DOCS_URL_HERE
    about: Check the docs before opening an issue. Your answer might already be there.
  - name: Discussions
    url: DISCUSSIONS_URL_HERE
    about: Ask questions, share ideas, or get help from the community.
```

Replace `DOCS_URL_HERE` and `DISCUSSIONS_URL_HERE` with the project's actual URLs. If the project has a Stack Overflow tag, add a third entry pointing there.

## Section 2: PR Template

Create `.github/pull_request_template.md`. Keep it lightweight and welcoming. For first-time contributors, this should feel like an invitation, not a government form.

```markdown
## What does this PR do?

<!-- One or two sentences describing the change. -->

## Related issue

<!-- Link to the issue this addresses, if any. Example: Closes #42 -->

## Checklist

- [ ] Tests pass locally
- [ ] Documentation updated (if applicable)
```

**Do NOT include:**
- Long checklists that scare off first-time contributors
- CLA requirements in the template (handle those separately via a bot)
- Screenshot requirements for non-visual changes

## Section 3: CONTRIBUTING.md

Generate a `CONTRIBUTING.md` file. The structure below is a template; adapt the specifics to the project being configured.

```markdown
# Contributing

Welcome! We appreciate your interest in contributing. Whether you are fixing a
typo, adding a test, reporting a bug, or proposing a new feature, your help
makes this project better for everyone.

## Development Setup

<!-- Target: under 10 minutes, ideally one command. -->

git clone https://github.com/OWNER/REPO.git
cd REPO
# Install dependencies (replace with actual command)
make dev-setup   # or: pip install -e ".[dev]"  /  npm install  /  etc.

## Running Tests

# Run the full suite
make test   # or: pytest  /  npm test  /  etc.

# Run a specific test file
pytest tests/test_example.py

A passing run looks like: "X passed, 0 failed" with exit code 0.

## Code Style

This project uses [LINTER] for formatting and [LINTER] for linting.
Both run automatically via pre-commit hooks. To run them manually:

make lint   # or: ruff check .  /  eslint .  /  etc.

## Submitting a Pull Request

1. Fork the repository and create a branch from `main`.
2. Make your changes. Add tests if you are adding functionality.
3. Run the test suite and linter locally.
4. Open a pull request with a clear description of what you changed and why.

We aim to review pull requests within 5 business days. If you have not heard
back, feel free to leave a comment on the PR.

## Types of Contributions

Code is not the only way to contribute. We welcome:

- Bug reports and feature requests (via issue templates)
- Documentation improvements
- Test coverage additions
- Translations
- Answering questions in Discussions

## Communication

<!-- List channels: Discussions, Discord, mailing list, etc. -->

Thank you for contributing!
```

**Critical details to verify with the user:**
- Actual dev setup commands (must be copy-pasteable, not prose)
- Test command and what "passing" looks like
- Linter/formatter names
- Review timeline commitment
- Communication channels

## Section 4: Roadmap as Issues

A project with zero open issues looks abandoned. A project with labeled, organized issues looks active and inviting.

### The Three-Tier Issue Strategy

Every set of roadmap issues should include all three tiers. Each serves a different purpose:

| Tier | Purpose | Labels | Expected Lifecycle |
|------|---------|--------|-------------------|
| **Actionable** | Real work the maintainer plans to do soon | `enhancement`, `documentation`, `bug` | Created, worked, closed within weeks/months |
| **Contributor magnets** | Well-scoped tasks designed to attract first contributions | `good first issue`, `help wanted` | Stay open until someone picks them up. Include "Getting Started" pointers in the body. |
| **Conversation starters** | Aspirational features that signal vision and invite discussion | `enhancement`, `help wanted` | Naturally stay open. Represent the project's roadmap and ambition. Welcome community input on design. |

**Why all three matter:**
- **Actionable issues** show the project is moving forward with concrete plans
- **Contributor magnets** are on-ramps. Sites like goodfirstissue.io scrape `good first issue` labels. These are how strangers become contributors.
- **Conversation starters** prevent the "zero open issues" red flag. They signal vision, invite discussion, and make the project look alive even during quiet periods. These are features that would be genuinely nice but are not urgent, things the community might pick up, or ideas that need design discussion before implementation.

**Aim for:** At minimum, 3-5 actionable, 3-5 contributor magnets, and 3-5 conversation starters. A healthy project has 15-25 open issues across all three tiers.

### Brainstorming Community Engagement Issues

Contributor magnets and conversation starters are not busywork. They are the primary mechanism for turning visitors into participants. Spend real effort here.

**Contributor magnets** (labeled `good first issue` + `help wanted`):

Scan the codebase and project for genuinely approachable tasks. Good sources:
- Missing or incomplete documentation (README gaps, undocumented config options, missing examples)
- Type hint coverage gaps in Python modules
- Test coverage holes (untested edge cases, missing unit tests for utility functions)
- Small, self-contained feature additions (new config option, extra output format, additional validation)
- Linting or code style consistency fixes across a module
- Localization/i18n for user-facing strings
- Adding examples or sample configurations

Each must be genuinely completable by someone unfamiliar with the codebase. Include file paths, relevant patterns to follow, and a "Getting Started" section in the body.

**Conversation starters** (labeled `enhancement` + `help wanted`):

These exist to make the project look alive, signal ambition, and invite community input. They should be things the maintainer would genuinely welcome but is unlikely to prioritize. Good sources:
- Integrations with adjacent ecosystems ("Support for X", "Plugin for Y")
- Quality-of-life features users might want but the maintainer hasn't needed ("Dark mode support", "Export to PDF")
- Performance or scalability improvements that aren't urgent ("Parallelize X", "Cache Y")
- Platform expansion ("Windows support for Z", "ARM builds")
- Developer experience improvements ("Interactive setup wizard", "Better error messages for common mistakes")
- Visualization, dashboards, or reporting features
- Alternative interfaces (TUI, web UI, API endpoint)
- Compatibility with popular tools in the same space

Write these as genuine feature requests with context about why they would be valuable. Avoid vague aspirations ("Make it faster") in favor of specific, discussable proposals ("Cache dependency resolution results to avoid repeated network calls"). The goal is issues that a motivated stranger could pick up and run with, or at minimum comment on with useful input.

### Process

1. Ask the user about planned features, known improvements, and wishlist items
2. Brainstorm conversation-starter issues using the sources above; aim for specific, discussable proposals
3. Brainstorm contributor magnets by scanning the codebase for genuinely approachable tasks
4. **Before creating any issue, verify it is not already done.** Check the repo for existing files, configurations, CI workflows, and metadata that satisfy the issue. If already done, skip it or note it for the user.
5. Create issues for each with clear descriptions and appropriate tier labels
6. Apply labels strategically

### Label Taxonomy

Create these labels in the repository:

| Label | Hex Color | Purpose |
|-------|-----------|---------|
| `good first issue` | `#0e8a16` | Genuinely approachable tasks. Sites like goodfirstissue.io scrape these. |
| `help wanted` | `#0e8a16` | Tasks where community help is specifically welcomed |
| `enhancement` | `#1d76db` | Feature requests and improvements |
| `bug` | `#d73a4a` | Known bugs |
| `documentation` | `#7057ff` | Documentation improvements needed |
| `performance` | `#f9a825` | Performance improvement opportunities |
| `question` | `#fbca04` | Open design questions that invite discussion |

### What Makes a Good "good first issue"

Appropriate:
- Typo fixes in documentation
- Missing type hints or docstrings
- Simple test additions for uncovered code paths
- Small, well-scoped feature additions
- Adding configuration options

Not appropriate:
- Anything requiring deep architectural knowledge
- Performance optimizations
- Security-sensitive code
- Core algorithm changes
- Anything with the word "refactor"

### Issue Writing Guidance

**Title:** Clear, specific, actionable. Write "Add type hints to auth module" not "Improve types."

**Body structure:**
- Context: why this matters
- Scope: what specifically needs to change
- Pointers: relevant files and functions

**For good-first-issues:** Include a "Getting Started" section in the body pointing to the relevant code, file paths, and any patterns to follow.

### Closing Issues with Evidence

When an issue is found to be already done (either during creation or later), close it with a comment that includes:
1. The commit hash or PR number that implemented it
2. A brief description of what exists and where

Example:
```
Already implemented. MkDocs Material site with full navigation covering
54 skills, 85+ commands, and 7 agents.

Introduced in b0eea5c ("feat: consolidate superpowers skills and add
MkDocs documentation"). Configuration in `mkdocs.yml`.
```

This pattern serves two purposes: it documents the project's history, and it shows visitors that issues are actively managed (even closed issues with good comments signal a healthy project).

## Section 5: GitHub Community Profile

GitHub grades repositories on community standards. Audit the project against this checklist and fill gaps:

| Element | File / Location | Purpose |
|---------|-----------------|---------|
| Description | Repo settings | Searchability, first impression |
| README | `README.md` | Handled in Phase 1 |
| Code of conduct | `CODE_OF_CONDUCT.md` | Professionalism signal |
| Contributing guide | `CONTRIBUTING.md` | Contributor on-ramp |
| License | `LICENSE` | Legal clarity |
| Security policy | `SECURITY.md` | Maturity signal |
| Issue templates | `.github/ISSUE_TEMPLATE/` | Structured reporting |
| PR template | `.github/pull_request_template.md` | Consistent contributions |

### CODE_OF_CONDUCT.md

Recommend the Contributor Covenant (v2.1). It is the standard, widely recognized, and low-controversy. GitHub has a built-in generator at Settings > Code and Automation > Moderation > Code of conduct.

If the user prefers to add it manually:

```markdown
# Contributor Covenant Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
code of conduct. By participating, you agree to uphold this standard.

For the full text, see https://www.contributor-covenant.org/version/2/1/code_of_conduct/

## Reporting

Report unacceptable behavior to [EMAIL]. All complaints will be reviewed
and investigated. All reports will be handled with discretion.
```

### SECURITY.md

```markdown
# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue.** Instead, email [SECURITY_EMAIL] with:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment (if known)

We will acknowledge receipt within 48 hours and aim to provide an initial
assessment within 5 business days.

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |
| < latest | Best effort |
```

## Section 6: GitHub Discussions

### When to Enable

- Project has users asking questions in issues (Discussions reduces noise)
- You want a lower-friction communication channel than issues
- No existing Discord, forum, or mailing list serves this purpose

### Recommended Category Setup

| Category | Format | Who Can Post | Purpose |
|----------|--------|-------------|---------|
| Announcements | Announcement | Maintainers only | Release notes, breaking changes, project news |
| Q&A | Question / Answer | Everyone | Support questions with accepted-answer flow |
| Ideas | Open | Everyone | Feature brainstorming, maps to feature request flow |
| Show and Tell | Open | Everyone | Users sharing what they built with the project |

Enable Discussions via Settings > Features > Discussions. If the project already has an active Discord or forum, skip this and link to that instead.

## Section 7: Awesome List Submissions

Awesome lists are high-trust sources that developers check before search engines. Being listed provides permanent passive discovery.

### Process

1. Search GitHub for `awesome-[domain]` and `awesome-[language]` (e.g., `awesome-python`, `awesome-fastapi`)
2. Check each list's submission requirements (most require a working project, documentation, and active maintenance)
3. Draft a submission PR following the list's own contribution guidelines
4. Submit after the project meets all requirements (not before, or you burn your one chance)

### Common Lists by Ecosystem

| Ecosystem | Lists to Check |
|-----------|---------------|
| Python | awesome-python, awesome-asyncio, awesome-flask, awesome-django, awesome-fastapi |
| JavaScript | awesome-nodejs, awesome-react, awesome-vue, awesome-svelte |
| Rust | awesome-rust |
| Go | awesome-go |
| Machine Learning | awesome-machine-learning, awesome-deep-learning, awesome-nlp |
| DevOps | awesome-docker, awesome-kubernetes, awesome-ci |
| General | awesome-selfhosted, awesome-cli-apps, awesome-open-source |

Identify 3-5 relevant lists and note their submission requirements for the user.

## Section 8: Signs of Life Maintenance Checklist

Produce this checklist as a standalone document the user can reference. An active-looking project attracts contributors; a stale-looking project repels them.

### Weekly

- [ ] Respond to new issues within 48 hours (even just an acknowledgment)
- [ ] Triage and label incoming issues
- [ ] Review and merge or comment on open PRs

### Monthly

- [ ] Review "good first issue" labels, add new ones, remove completed ones
- [ ] Close resolved issues with a summary comment
- [ ] Comment on stale issues requesting an update (do NOT auto-close)
- [ ] Verify all README badges are green; remove or fix any that are failing

### Per Release

- [ ] Update CHANGELOG with user-facing changes
- [ ] Verify README still reflects current project state
- [ ] Confirm version badges update automatically (shields.io dynamic badges)
- [ ] Post an Announcement in Discussions (if enabled)

### Quarterly

- [ ] Re-run the project-presence audit to check for drift
- [ ] Review GitHub topics for continued relevance
- [ ] Check if new awesome lists or directories have appeared in your domain
- [ ] Review contributor experience: try the dev setup from scratch on a clean machine

## Section 9: Auto-Labeling and Welcome Actions (Optional)

Suggest these GitHub Actions for projects that want automation. All are optional.

### First-Time Contributor Welcome

```yaml
# .github/workflows/welcome.yml
name: Welcome First-Time Contributors
on:
  pull_request_target:
    types: [opened]
  issues:
    types: [opened]

permissions:
  issues: write
  pull-requests: write

jobs:
  welcome:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/first-interaction@v1
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          issue-message: >
            Thanks for opening your first issue! We will take a look soon.
            If you have not already, check out our
            [contributing guide](CONTRIBUTING.md).
          pr-message: >
            Thanks for your first pull request! A maintainer will review it
            soon. While you wait, make sure the CI checks pass.
```

### Stale Issue Notification (NOT Auto-Close)

<CRITICAL>
Do NOT use stale bots that automatically close issues. Research identifies auto-closing as a contributor repellent. The correct approach is to notify and request updates, but leave closing to humans.
</CRITICAL>

```yaml
# .github/workflows/stale.yml
name: Stale Issue Notification
on:
  schedule:
    - cron: '0 9 * * 1'  # Weekly on Monday

permissions:
  issues: write

jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v9
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          stale-issue-message: >
            This issue has had no activity for 60 days. Is it still relevant?
            If so, please leave a comment with an update. If not, feel free
            to close it.
          stale-issue-label: 'stale'
          days-before-stale: 60
          days-before-close: -1  # NEVER auto-close
          exempt-issue-labels: 'good first issue,help wanted,roadmap'
```

The key setting is `days-before-close: -1`, which disables automatic closing entirely. Stale labels can be removed manually when there is activity.

## Output Checklist

After running this phase, confirm you have produced or guided the user through:

| # | Artifact | Destination |
|---|----------|-------------|
| 1 | Bug report template | `.github/ISSUE_TEMPLATE/bug_report.yml` |
| 2 | Feature request template | `.github/ISSUE_TEMPLATE/feature_request.yml` |
| 3 | Issue template config | `.github/ISSUE_TEMPLATE/config.yml` |
| 4 | PR template | `.github/pull_request_template.md` |
| 5 | Contributing guide | `CONTRIBUTING.md` |
| 6 | Code of conduct | `CODE_OF_CONDUCT.md` (or link to Contributor Covenant) |
| 7 | Security policy | `SECURITY.md` |
| 8 | Label set | Created via GitHub API or CLI |
| 9 | Roadmap issues | Created from user input, labeled and organized |
| 10 | Maintenance checklist | Delivered to user as reference document |
| 11 | Awesome list candidates | Identified with submission requirements noted |
| 12 | AGENTS.md snippet | Reminder for README and community health maintenance |

All templates should be committed and pushed. Labels and issues should be created via `gh` CLI or GitHub API. The maintenance checklist and awesome list candidates are delivered as output, not committed files.
``````````
