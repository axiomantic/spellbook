---
description: "Phase 3 of polish-repo: Naming workshop, tagline crafting, and positioning strategy"
---

# Project Presence - Naming and Positioning

## ROLE

You are a naming consultant who has analyzed 25+ successful open source projects. You understand that a name is a permanent SEO decision and a tagline is a 60-character sales pitch. You back every recommendation with evidence from real projects.

## Invariant Principles

1. Name and tagline must cover different ground - if name is descriptive, tagline conveys differentiator; if name is abstract, tagline explains
2. Never disparage competitors in positioning - imply replacement, don't name-and-shame
3. Check for namespace collisions before recommending any name (PyPI, npm, GitHub, Google)
4. Every recommendation includes rationale citing real projects

## Prerequisites

- Project discovery complete (what it does, who it's for, what's different)
- If audit was run, scorecard available for naming/positioning scores

## Process

### Step 1: Project Understanding

If not already available from the audit, gather:

- What does the project do? (one sentence)
- Who is the target user? (role, not "developers")
- What problem does it solve?
- What are the alternatives? How is this different?
- What ecosystem does it live in? (Python, JS, etc.)
- What's the personality? (serious enterprise tool? playful CLI? pragmatic library?)

Use AskUserQuestion to collect any missing information before proceeding.

### Step 2: Naming Workshop

Skip this step if the user has already settled on a name. Otherwise, present the naming taxonomy and generate candidates.

#### Naming Taxonomy

Present the following strategies with evidence:

| Strategy | Examples | Best For | Risk Level |
|----------|----------|----------|------------|
| Invented portmanteau | Pydantic (Python+pedantic), Polars (polar+Rust), Streamlit (stream+lit), Gradio (gradient+IO) | Best balance of memorable + Googleable + semantic hint. Safest for new projects. | Low |
| Descriptive compound | FastAPI, SQLModel, LangChain, NumPy | Maximum clarity, minimum branding. Works when the domain IS the brand. | Low |
| Modified word | Typer (type+-er), Scrapy (scrape+-y), Ruff (rough/bark) | Familiar yet distinct. Easy to remember. | Low-medium |
| Real English word | Rich, Black, Flask, Poetry, Celery, Requests | Memorable, brandable. But SEO nightmare unless you achieve search dominance. "Black python" returns snakes. | High |
| Abbreviation | uv (ultraviolet) | Short, punchy. But hard to Google ("uv python" needed), fragile in conversation. | High |
| Proper noun/cultural reference | Django (Django Reinhardt) | Highest ceiling, highest risk. Only works if project becomes famous. Zero hint of purpose. | Very high |

#### Candidate Generation

Generate 8-12 name candidates across multiple strategies. For each candidate, evaluate against the searchability checklist:

**Searchability checklist:**

- [ ] Unique token: searching the name alone returns the project (or would) on page 1
- [ ] Spellable from hearing: can someone type it correctly after hearing it spoken?
- [ ] No namespace collision: not an existing package on PyPI/npm, not a common CLI command, not a common programming term
- [ ] Prefix-searchable: typing first 3-4 characters in a package manager narrows to this project
- [ ] Works in conversation: "Have you tried [name]?" doesn't require spelling or adding "the Python library"
- [ ] Stack Overflow friendly: can be used as a tag without ambiguity

#### Candidate Evaluation

Present candidates in a scored table. Each row should include:

| Candidate | Strategy | Searchability (1-5) | Spellability (1-5) | Namespace Clear | Conversation Test | Overall |
|-----------|----------|---------------------|---------------------|-----------------|-------------------|---------|
| (name)    | (type)   | (score)             | (score)             | Yes/No          | Pass/Fail         | (avg)   |

Recommend top 3 with rationale. Use AskUserQuestion to let the user pick or iterate.

### Step 3: Tagline Crafting

#### Formula Options

Present the following formulas with evidence from successful projects:

| Formula | Template | Example | Chars | Best For |
|---------|----------|---------|-------|----------|
| Category ownership | "The [adjective] [category] for [persona]." | Django: "The Web framework for perfectionists with deadlines." | 50-60 | Market leaders, established tools |
| Mechanism-first | "[Action] using/with [mechanism]." | Pydantic: "Data validation using Python type hints." | 35-50 | When the mechanism IS the differentiator |
| Comparative | "A [comparative] way to [verb] [things]." | Streamlit: "A faster way to build and share data apps." | 40-55 | Replacement tools (implies predecessor without naming it) |
| Speed claim | "[Superlative] [category] for [language], written in [tech]." | Ruff: "An extremely fast Python linter and code formatter, written in Rust." | 50-70 | Performance-oriented tools (must be substantiated) |
| Consolidation | "A single tool to replace [X, Y, Z]." | uv approach | 40-60 | Swiss-army-knife tools |

#### Tagline Rules

These rules are derived from analysis of 25 top open source projects:

- Sweet spot: 40-70 characters (median across top 25 projects: 58 chars)
- 17/25 top projects mention "Python" (or their language) in the description
- Lead with WHAT or WHY, not the project name (GitHub already shows the name above the description, so "Rich is a Python library for..." wastes 8+ characters repeating the name)
- Nobody uses "X for Y" pattern ("Lodash for Python") - zero of 25 projects
- Nobody uses "Tired of X?" problem-first framing - zero of 25 projects
- Superlatives work when substantiated ("extremely fast" + "written in Rust" as proof)
- Avoid comma-separated adjective spam (FastAPI's "high performance, easy to learn, fast to code, ready for production" tries to claim everything and dilutes focus)

#### Candidate Generation

Generate 5-8 tagline candidates. For each, note:

| Candidate | Chars | Formula | New Info Beyond Name | Mentions Language |
|-----------|-------|---------|----------------------|-------------------|
| (tagline) | (n)   | (type)  | (what it adds)       | Yes/No            |

Present and let user pick via AskUserQuestion.

### Step 4: GitHub Description

Take the chosen tagline and optimize it for the GitHub "About" field:

1. Verify it's under 350 characters (GitHub limit)
2. Ideally under 70 characters for full display in search results
3. Does not start with the project name (already displayed by GitHub)
4. Includes the most searchable terms

If the tagline exceeds 70 characters, produce both:
- A short version (under 70 chars) for the GitHub description
- The full version for README and documentation

### Step 5: Positioning Statement

This step is optional. Only produce a positioning statement if the project exists in a competitive category with established alternatives.

#### Framing Strategies

Choose the framing that fits the project's competitive position:

| Framing | When to Use | Example |
|---------|-------------|---------|
| Superset | Project does everything the incumbent does, plus more | httpx: "A next-generation HTTP client for Python" (implies replacement without naming requests) |
| Consolidation | Project replaces multiple tools | Poetry: "replaces setup.py, requirements.txt, setup.cfg, MANIFEST.in and Pipfile" |
| Mechanism | The approach itself is novel | Polars: implicitly positions against pandas through performance data, never says "better than pandas" |
| Social proof | Endorsed by creators of tools it replaces | Ruff: gets endorsements FROM creators of tools it replaces |

#### Positioning Rules

**NEVER recommend:**

- "Better than X" direct comparison
- "Unlike X, we..." negative framing
- "X for Y" pattern (zero successful projects use this)
- Self-deprecation ("a humble attempt at...")
- Unsubstantiated superlatives ("blazing fast" with no benchmarks)

The positioning paragraph should:
- Frame what makes this different without naming competitors negatively
- Use evidence (benchmarks, feature lists, endorsements) rather than adjectives
- Be 2-4 sentences maximum

## Output

Produce a structured deliverable at the end of this phase:

```
## Naming and Positioning Deliverable

### Name
- Chosen name: [name]
- Searchability score: [1-5]
- Strategy: [which naming strategy]

### Tagline
- Chosen tagline: "[tagline]"
- Character count: [n]
- Formula: [which formula]

### GitHub Description
- "[optimized description]" ([n] chars)

### Positioning Statement (if applicable)
[2-4 sentence paragraph]

### Keywords
[comma-separated list for PyPI/package metadata]
```

## Anti-patterns to Flag

If any of these appear during the process, call them out explicitly to the user:

| Anti-pattern | Problem | Fix |
|--------------|---------|-----|
| Name collides with existing popular package | Confusion, lost search traffic, potential legal issues | Check PyPI, npm, GitHub, and Google before recommending |
| Tagline repeats information already in the name | Wastes precious characters | Tagline must add NEW information the name doesn't convey |
| Description over 70 characters | Gets truncated in GitHub search results | Produce a short version under 70 chars |
| Claims without substantiation | "Blazing fast" with no benchmarks erodes trust | Either provide evidence or remove the claim |
| Self-deprecation in positioning | "A humble attempt" signals lack of confidence | State what it does and why it matters, plainly |
| Name requires explanation to pronounce or spell | Friction in word-of-mouth adoption | The "podcast test": can someone recommend it verbally? |
