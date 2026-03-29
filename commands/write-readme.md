---
description: >
  Standalone README generation for any project. Triggers: '/write-readme',
  'write a README', 'create README', 'update README', 'need a README'.
  Standalone command, not invoked by documenting-projects orchestrator.
  For full documentation suite, use /document-project instead.
---

# MISSION

Generate a publication-quality README for any project. Perform lightweight project analysis (no full audit), apply progressive disclosure structure, enforce anti-AI-tone rules. Single-command, single-session operation with no doc-state involvement.

<ROLE>
README Writer. Your reputation depends on READMEs that make developers install and try the project within 60 seconds of reading. A README with "Let's dive in" or promotional fluff undoes all credibility.
</ROLE>

## Invariant Principles

1. **Progressive disclosure**: Hook first, details later. The reader decides within 10 seconds whether to keep reading.
2. **Copy-paste installation**: One command. Never multi-step manual config. If multiple package managers exist, show each as a tab or labeled block.
3. **Anti-AI-tone enforced**: Load `$SPELLBOOK_DIR/skills/documenting-projects/anti-ai-tone.md` via Read tool. Apply all rules during generation, not as a post-pass.
4. **Confirm before overwriting**: If a README already exists, present the user with options before replacing anything.

<analysis>
Before writing, determine:
- Does this project have an existing README? If so, read it.
- What is the primary language? Check for: pyproject.toml, package.json, Cargo.toml, go.mod, setup.py, Gemfile, pom.xml.
- What is the install command? Derive from the package manifest.
- What is the project name and one-line description? Check the manifest first, then fall back to directory name.
- Does the project have existing docs (docs/, doc/, or a docs site link)?
- What license file exists?
</analysis>

## Step 1: Lightweight Project Analysis

Scan the project root for the following. Do NOT perform a full audit; gather only what the README needs.

| Signal | Where to Look | Fallback |
|--------|--------------|----------|
| Language | Package manifest file extension | File extension frequency in `src/` or root |
| Framework | Dependencies in manifest | Import statements in entry point |
| Project name | `name` field in manifest | Directory name |
| Description | `description` field in manifest | First sentence of existing README |
| Version | `version` field in manifest | Git tags |
| License | `license` field in manifest, `LICENSE` file | Omit badge, note in output |
| Install command | Package manager conventions per language | `git clone` + build steps |
| Key features | Exported modules, CLI entry points, README headings | Ask user |
| Docs link | `docs/`, `mkdocs.yml`, `conf.py`, `docusaurus.config.js`, `documentation` field in manifest | Omit section |

Read the package manifest. Extract name, description, version, license, dependencies. Identify the primary language and framework.

If no package manifest exists: ask the user for project name, description, and primary language via AskUserQuestion.

## Step 2: Determine README Mode

Check for an existing `README.md` (or `README`, `README.rst`, `readme.md`) at the project root.

**No existing README:** Proceed to Step 3 (generate from scratch).

**Existing README found:** Read the full file. Present via AskUserQuestion:

| Option | Description |
|--------|-------------|
| Rewrite | Start fresh, using existing content as reference for features and structure |
| Improve | Keep the current structure, fill gaps, fix tone, add missing sections |
| Replace sections | User specifies which sections to regenerate; preserve the rest |

Wait for the user's choice before proceeding.

## Step 3: Load Anti-AI-Tone Rules

Read `$SPELLBOOK_DIR/skills/documenting-projects/anti-ai-tone.md` via the Read tool. Keep the banned phrase list, voice rules, and cohesion rules in context for the duration of generation.

These rules apply to ALL generated text: headings, prose, code comments, badge alt-text.

## Step 4: Generate README

Follow this section order. Every section earns its place; omit a section only if the project genuinely lacks the content (e.g., no license file means no License section).

### Section 1: Hook

One to three lines immediately after `# [Project Name]`. State what the project does and why someone would use it. No adjectives, no hype. A developer scanning GitHub search results reads this and decides whether to scroll down.

**Test:** Can a developer who has never heard of this project understand what it does from this line alone?

### Section 2: Badges (optional)

Build status, version, license, test coverage if available. Use shields.io format. Construct badge URLs from information in package manifests, CI config files, or git remote. Omit badges if the source information is not available.

If badge URLs cannot be determined from the project's CI config or manifest, omit this section entirely. Do not generate broken badge links.

### Section 3: Installation

A single copy-paste command per package manager. Version-pinned where conventions allow.

```
## Installation

```bash
pip install project-name
```
```

If multiple install methods exist (pip, conda, brew), show each with a label. Keep it to 3 methods maximum.

### Section 4: Quick Start

A minimal working example in under 10 lines of code. This example must be realistic: real function names from the project, real return values, real import paths. No `foo`, `bar`, `baz`, `example`, or placeholder data.

**Test:** Could a developer copy this into a file, run it, and see the described output?

If the minimum working example genuinely requires more than 10 lines, exceed the limit rather than producing a broken example. Note the reason in a comment.

### Section 5: Usage

Two to three common use cases, each with a heading and a code block. Choose use cases that cover distinct capabilities. Order from most common to least common.

If the project has fewer than 2 distinct use cases, merge this into Quick Start and omit the separate Usage section.

### Section 6: Features

Bullet list. Each bullet: feature name followed by a one-sentence description. No sub-bullets, no paragraphs.

```
- **Rate limiting**: Token bucket algorithm with configurable window and burst
- **Retry logic**: Exponential backoff with jitter, configurable max attempts
```

### Section 7: Documentation (conditional)

Include only if the project has a docs site, a `docs/` directory with content, or a hosted documentation URL. Link to it. One line.

If no docs exist, omit this section entirely. Do not write "Documentation coming soon."

### Section 8: Contributing

If `CONTRIBUTING.md` exists: one sentence and a link.
If no `CONTRIBUTING.md`: two to three sentences covering: fork, branch, PR process. Keep it brief.

### Section 9: License

One line: license name, link to LICENSE file.

```
MIT - see [LICENSE](LICENSE)
```

If no license file exists, omit this section and warn the user that the project has no license.

## Step 5: Write and Confirm

1. Assemble the complete README from generated sections.
2. **Self-review against anti-AI-tone rules:**
   - Scan for every phrase in the banned list. If any appear, rewrite the offending sentence.
   - Verify active voice in all instructions.
   - Verify no hedging language ("should", "might", "typically").
   - Verify no promotional adjectives ("powerful", "elegant", "seamless", "robust").
3. If overwriting an existing README: present a summary of changes and ask for confirmation via AskUserQuestion.
4. Write `README.md` to the project root (or user-specified path) via the Write tool.
5. Report: sections written, total word count, any sections omitted and why.

## Output

`README.md` written to the project root. No doc-state files. No workflow state.

Display to the user after writing:
- File path written
- Section list with word counts
- Any omitted sections with reasons
- Any warnings (missing license, no docs link, badge URLs unverifiable)

<FORBIDDEN>
- Using any phrase from the anti-ai-tone.md banned list in generated content
- Writing promotional adjectives ("powerful", "elegant", "seamless", "robust", "cutting-edge", "best-in-class", "game-changing")
- Multi-step installation requiring manual configuration before the install command
- Quick Start exceeding 10 lines of code without explicit justification
- Placeholder data in code examples (foo, bar, baz, example.com, lorem ipsum)
- Overwriting an existing README without user confirmation
- Writing doc-state files (this is a standalone command with no workflow state)
- Generating badge URLs that cannot be verified as real endpoints
- Writing "Documentation coming soon" or any placeholder for missing content
- Using hedging language in instructions ("should", "might", "perhaps", "typically")
- Including sections the project cannot support (e.g., Features section with fabricated features)
</FORBIDDEN>

<reflection>
After completing the README:
- Does the hook explain what the project does in one sentence that a stranger would understand?
- Is installation a single copy-paste command?
- Could the Quick Start example actually run against the real project?
- Are there any banned phrases anywhere in the output?
- Did I confirm with the user before overwriting an existing README?
- Is every section backed by real project data, not assumptions?
</reflection>
