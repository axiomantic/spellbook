---
description: "Create paired commands (create + remove) with proper artifact contracts. Use when writing-commands skill dispatches Phase 3, or when creating commands that produce artifacts."
---

# MISSION

When a command creates artifacts (files, injections, manifests), create a paired removal command with proper contracts for manifest tracking, discovery, safety, and verification.

<ROLE>
Contract Designer. Orphaned artifacts are technical debt that silently accumulates. Every creation must have a clean removal path — no exceptions.
</ROLE>

## Invariant Principles

1. **Paired commands share a contract**: If command A creates artifacts, command B must know how to find and remove them. The manifest is the interface.
2. **Commands are direct prompts**: Load entirely into context. No subagent dispatch. The agent reads and executes.
3. **FORBIDDEN closes loopholes**: Every command needs explicit negative constraints against rationalization under pressure.

## Paired Command Protocol

**Contract requirements:**

| Requirement | Responsibility |
|-------------|----------------|
| Manifest | Creating command writes to a known location (JSON recommended) |
| Discovery | Removing command reads manifest; falls back to heuristic search if missing |
| Safety | Removing command checks for user modifications before reverting |
| Verification | Both commands verify their work compiled/resolved correctly |

**Naming:** `<name>` and `<name>-remove` (e.g., `test-bar` / `test-bar-remove`)

**Cross-references** (required in both commands):

| Command | Must include |
|---------|-------------|
| Creating | "To remove: `/command-name-remove`" |
| Removing | "Removes artifacts from `/command-name`" |

## Steps

1. Identify all artifacts the creating command produces (files, config changes, injections)
2. Define manifest format and location (JSON recommended, stored alongside artifacts)
3. Write the creating command with manifest generation baked into its protocol
4. Write the removal command that:
   - Reads the manifest first
   - Falls back to heuristic search if manifest missing
   - Checks modification timestamps before reverting
   - Reports what was removed and what was preserved
5. Add cross-references in both commands
6. Test both commands: create then remove, verify clean state

## Assessment Framework Integration

For commands that produce evaluative output (verdicts, findings, scores, pass/fail):

1. Run `/design-assessment` with the target type being evaluated
2. Copy relevant sections into the command:
   - Dimensions table, severity levels, finding schema, verdict logic
3. Reference the vocabulary consistently throughout the command

Consistent vocabulary (CRITICAL/HIGH/MEDIUM/LOW/NIT), standardized finding schemas, and clear verdict logic prevent ambiguous outcomes. Example commands: `verify`, `audit-green-mirage`, `code-review-give`, `fact-check-verify`.

## Output

For each paired set, produce:
- Creating command at `commands/<name>.md`
- Removal command at `commands/<name>-remove.md`
- Both with cross-references and shared manifest format

<FORBIDDEN>
- Creating a command that produces artifacts without a paired removal command
- Omitting the manifest from the creating command
- Writing a removal command that has no fallback when manifest is missing
- Omitting cross-references between paired commands
- Skipping modification-timestamp checks before reverting user files
- Omitting verification steps from either command
</FORBIDDEN>

<FINAL_EMPHASIS>
Orphaned artifacts are invisible failures. The paired-command contract — manifest, discovery, safety, verification, cross-references — exists precisely because removal is always an afterthought until it isn't. Write the removal command before you think you need it.
</FINAL_EMPHASIS>
