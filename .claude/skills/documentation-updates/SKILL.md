---
name: documentation-updates
description: "Use after modifying library skills, library commands, or agents to ensure CHANGELOG, README, and docs are updated"
---

# Documentation Updates

Enforces documentation hygiene when library content changes.

<CRITICAL>
When ANY of these are modified, corresponding documentation MUST be updated:
- `skills/*/SKILL.md` (library skills)
- `commands/*.md` (library commands)
- `agents/*/AGENT.md` (agents)

This does NOT apply to repo skills (`.claude/skills/`) which are internal tooling.
</CRITICAL>

## Required Updates

| Change Type | CHANGELOG | README | Docs |
|-------------|-----------|--------|------|
| New library skill | Add to "Added" section | Update skill count, add to table, add link ref | Run `python3 scripts/generate_docs.py` |
| Modified library skill | Add to "Changed" section | Only if description changed | Run docs generator |
| Removed library skill | Add to "Removed" section | Update count, remove from table/links | Run docs generator |
| New command | Add to "Added" section | Update command count, add to table | Run docs generator |
| Modified command | Add to "Changed" section | Only if description changed | Run docs generator |

## Checklist

Before completing any PR that touches library content:

- [ ] CHANGELOG.md updated under `## [Unreleased]`
- [ ] README.md skill/command count is accurate
- [ ] README.md tables include new items with link references
- [ ] `python3 scripts/generate_docs.py` has been run
- [ ] Generated docs committed (pre-commit hooks should handle this)

## CHANGELOG Format

```markdown
## [Unreleased]

### Added
- **skill-name skill** - one-line description
  - Bullet point for notable feature
  - Another bullet point

### Changed
- **skill-name skill** - what changed and why

### Removed
- **skill-name skill** - why it was removed
```

## README Update Pattern

1. Update count in `### Skills (N total)` header
2. Add skill to appropriate category row in table
3. Add link reference at bottom of skills section:
   ```markdown
   [skill-name]: https://axiomantic.github.io/spellbook/latest/skills/skill-name/
   ```

## Terminology

See CLAUDE.md glossary for distinction between:
- **Library skills** (`skills/`) - installed for spellbook users
- **Repo skills** (`.claude/skills/`) - internal tooling for spellbook development
