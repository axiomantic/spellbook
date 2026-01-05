# Contributing

## Prerequisites

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Development Setup

```bash
# Clone the repository
git clone https://github.com/axiomantic/spellbook.git
cd spellbook

# Install pre-commit hooks
uvx pre-commit install
```

## Running Tests

```bash
# Run unit tests
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/
```

## Documentation

### Building Docs Locally

```bash
# Serve docs locally with hot reload
uvx mkdocs serve

# Build static site
uvx mkdocs build
```

Then open http://127.0.0.1:8000

### Generating Skill Docs

After modifying skills, regenerate documentation:

```bash
uv run scripts/generate_docs.py
```

## MCP Server Development

```bash
# Run the MCP server directly
cd spellbook_mcp
uv run server.py

# Or install as editable package
uv pip install -e .
```

## Creating a New Skill

1. Create a directory: `skills/<skill-name>/`
2. Add `SKILL.md` with frontmatter:

```markdown
---
name: skill-name
description: Use when [trigger] - [what it does]
---

# Skill Name

## When to Use

[Describe when this skill applies]

## Process

[Step-by-step workflow]
```

3. Run `uv run scripts/generate_docs.py` to update docs
4. Test the skill in Claude Code

## Creating a New Command

1. Add `commands/<command-name>.md`
2. Include clear usage instructions
3. Regenerate docs: `uv run scripts/generate_docs.py`

## Pre-commit Hooks

The repository uses pre-commit hooks for:

- **generate-docs** - Auto-regenerate skill/command/agent documentation
- **check-docs-completeness** - Ensure all items are documented

Run hooks manually:
```bash
uvx pre-commit run --all-files
```

## Pull Request Guidelines

1. Create a feature branch
2. Make changes with clear commits
3. Ensure tests pass: `uv run pytest`
4. Update documentation if needed
5. Submit PR with description of changes

## Code Style

- Markdown: Follow existing formatting
- Python: Follow PEP 8, use type hints
- JavaScript: Use ES modules, async/await

## Attribution

When adding content from other sources:

1. Update `THIRD-PARTY-NOTICES` with attribution
2. Note the origin in documentation
3. Ensure license compatibility (MIT preferred)
