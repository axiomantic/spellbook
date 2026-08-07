# Review Method

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.review-method`.

How a code review loads the standards it will judge against, and how much of the diff it is obliged to read.

**Why keep it:** Loads the repository's own standards before reviewing, and reads every changed line.

**If you decline:** Reviews may proceed without loading the repository's standards documents and may sample the diff with grep instead of reading it in full.

**Related artifacts:**

- `skills/code-review`
- `skills/advanced-code-review`
- `agents/code-reviewer`

## Rule Content

``````````markdown
## Review Method

### Phase 0 — Load and catalogue the standards FIRST

A review cannot catch violations of rules it has not read. Before computing the diff or
reading a single changed line, discover, read, and catalogue the standards that govern the
changed code. Skipping this produces hand-waving: a review that never cites a loaded rule by
name is not a review.

1. **Discover and read the repository's own standards documents.** They vary per repository,
   so find them rather than assuming a fixed set. Typical locations include a coding-standards
   document, testing instructions, code-review instructions, the root `AGENTS.md`, and every
   subdirectory `AGENTS.md` covering a changed path. Also read whatever those documents
   reference: contributing guides, style guides, and lint configuration. If a document you
   expected is absent, note that and adapt; if the repository carries standards documents you
   did not expect, load those too.
2. **Read the operator's standing rules** and any project memory the environment provides.
3. **Extract a concrete, NAMED rule catalogue** from every document loaded so far — the enforceable rules
   with whatever identifiers or names the documents give them. That catalogue is the checklist
   the review runs against. You must know the rules before you look for violations.
4. **Every finding names the rule it violates** — the document plus the rule's identifier or
   name — or it is a named correctness or logic bug. No vague "this seems off": cite the
   standard.

If the `diff-semantics` module is installed, its base and endpoint rules determine which diff
Phase 0 precedes.

### Method — read EVERY line

Consume every changed hunk in every changed file and hold each against the catalogue built in
Phase 0. No grep-sampling. No skimming. No "I read the hot files." Grep is fine to LOCATE
things; it is never a substitute for reading the whole diff.

- For a **large diff, chunk it across subagents** so that 100% of the diff is assigned and read
  line by line. Track file and hunk coverage, and be able to prove no file went unread.
- Each finding cites a specific catalogued rule, or is a named correctness or logic bug.

### Narrower scopes

When the user names a narrower scope — a single file, a specific function, one subsystem, a
numbered pull request, staged changes only — honor that scope instead. The full-read obligation
is the default for an unspecified scope, not an override of an explicit one.
``````````
