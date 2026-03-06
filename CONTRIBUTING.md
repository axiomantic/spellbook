# Contributing

Welcome! Whether you are fixing a typo, adding a test, reporting a bug,
writing a new skill, or proposing a feature, your help makes spellbook
better for everyone.

## Development Setup

```bash
git clone https://github.com/axiomantic/spellbook.git
cd spellbook
uv pip install -e ".[dev,test,tts]"
```

Install pre-commit hooks:

```bash
./scripts/install-hooks.sh
```

## Running Tests

```bash
# Run the full suite
uv run pytest tests/ -x --timeout=30

# Run a specific test file
uv run pytest tests/test_specific_file.py -x

# Run linting
uv run ruff check .
```

A passing run shows something like `X passed` with exit code 0.

## Adding a Skill

1. Create `skills/<your-skill-name>/SKILL.md` with YAML frontmatter:
   ```yaml
   ---
   name: your-skill-name
   description: "Use when [trigger conditions]. Triggers: 'phrase1', 'phrase2'."
   ---
   ```
2. Write the skill body following existing skills as examples
3. Run `python3 scripts/generate_docs.py` to generate the docs page
4. Pre-commit hooks will validate the schema and update documentation

## Adding a Command

1. Create `commands/<your-command-name>.md` with YAML frontmatter:
   ```yaml
   ---
   description: "Brief description of the command"
   ---
   ```
2. Pre-commit hooks will generate docs and update the index

## Code Style

This project uses [Ruff](https://github.com/astral-sh/ruff) for Python
linting and formatting. Pre-commit hooks run these automatically. To run
manually:

```bash
uv run ruff check .
uv run ruff format .
```

## Submitting a Pull Request

1. Fork the repository and create a branch from `main`
2. Make your changes and add tests if adding functionality
3. Run the test suite and linter locally
4. Verify the installer works: `uv run install.py --dry-run`
5. Open a pull request with a clear description of what you changed and why

We aim to review pull requests within 5 business days. If you have not
heard back, feel free to leave a comment on the PR.

## Types of Contributions

Code is not the only way to contribute. We welcome:

- **Bug reports and feature requests** via issue templates
- **New skills and commands** for common development workflows
- **Documentation improvements** and typo fixes
- **Test coverage additions**
- **Translations** of the README

## Pre-commit Hooks

Pre-commit hooks auto-generate documentation files. If a hook fails:

1. Check the output for which files were modified
2. Stage the generated files with `git add`
3. Commit again

This is normal and expected when adding new skills or commands.

## Communication

- [GitHub Issues](https://github.com/axiomantic/spellbook/issues) for bugs and feature requests
- [GitHub Discussions](https://github.com/axiomantic/spellbook/discussions) for questions and ideas (when enabled)

Thank you for contributing!
