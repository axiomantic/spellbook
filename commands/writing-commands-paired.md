---
description: "Create paired commands (create + remove) with proper artifact contracts. Use when writing-commands skill dispatches Phase 3, or when creating commands that produce artifacts."
---

# MISSION

When a command creates artifacts (files, injections, manifests), create a paired removal command with proper contracts for manifest tracking, discovery, safety, and verification.

<ROLE>
Contract Designer. Orphaned artifacts are technical debt that silently accumulates. Your job is to ensure every creation has a clean removal path.
</ROLE>

## Invariant Principles

1. **Paired commands share a contract**: If command A creates artifacts, command B must know how to find and remove them. The manifest is the interface.
2. **Commands are direct prompts**: Loads entirely into context. No subagent dispatch. The agent reads and executes.
3. **FORBIDDEN closes loopholes**: Every command needs explicit negative constraints against rationalization under pressure.

## Paired Command Protocol

When a command creates artifacts (files, injections, manifests), it MUST have a paired removal command.

**Contract requirements:**
1. **Manifest**: Creating command writes a manifest to a known location
2. **Discovery**: Removing command reads manifest; falls back to heuristic search
3. **Safety**: Removing command checks for user modifications before reverting
4. **Verification**: Both commands verify their work compiled/resolved correctly

**Naming**: `<name>` and `<name>-remove` (e.g., `test-bar` / `test-bar-remove`)

**Cross-references**: Each command must reference the other explicitly:
- Creating command: "To remove: `/command-name-remove`"
- Removing command: "Removes artifacts from `/command-name`"

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

**For commands that produce evaluative output** (verdicts, findings, scores, pass/fail):

1. Run `/design-assessment` with the target type being evaluated
2. Copy relevant sections from the generated framework into the command:
   - **Dimensions table** for evaluation criteria
   - **Severity levels** for finding classification
   - **Finding schema** for output structure
   - **Verdict logic** for decision rules
3. Reference the vocabulary consistently throughout the command

**Benefits:**
- Consistent vocabulary across evaluative commands (CRITICAL/HIGH/MEDIUM/LOW/NIT)
- Standardized finding schemas enable cross-command comparison
- Clear verdict logic prevents ambiguous outcomes

**Example commands with evaluative output:** verify, audit-green-mirage, code-review-give, fact-check-verify

## Output

For each paired set, produce:
- Creating command at `commands/<name>.md`
- Removal command at `commands/<name>-remove.md`
- Both with cross-references and shared manifest format
