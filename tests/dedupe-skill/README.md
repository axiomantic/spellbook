# Dedupe Skill Verification Suite

Verification scripts for the semantic-dedupe skill (`skills/dedupe/`,
`commands/dedupe-*.md`). Each script enforces a structural invariant
documented in the impl plan §2 Track D and design §16.

## Run all gates locally

From the repo root:

```sh
bash tests/dedupe-skill/verify-structure.sh
bash tests/dedupe-skill/verify-no-python.sh
bash tests/dedupe-skill/verify-no-python-neg.sh
bash tests/dedupe-skill/verify-anti-irony.sh
bash tests/dedupe-skill/verify-anti-irony-neg.sh
bash tests/dedupe-skill/verify-json-blocks.sh
bash tests/dedupe-skill/verify-json-blocks-neg.sh
bash tests/dedupe-skill/verify-markdown.sh
bash tests/dedupe-skill/verify-references.sh
```

All scripts must exit 0.

## Dependencies

- POSIX `sh` / `bash`
- GNU `grep` with `-E -r -n` (system `grep` on macOS works)
- `jq` for D4 (`brew install jq`) — HARD dependency, gate fails if absent
- `markdownlint-cli2` for D5 — HARD dependency, gate fails if absent.
  Install via `brew install markdownlint-cli2` or `npm install -g markdownlint-cli2`.
  D5 previously skipped silently when this was missing; the green-mirage audit
  treated that as a false-positive PASS and the gate now fails loudly instead.
- `perl` for D6 — HARD dependency, used by `verify-references.sh` to
  extract `/dedupe-<phase>` slash-command mentions with a left-boundary
  predicate that POSIX ERE cannot express. Present by default on macOS
  and on every mainstream Linux distribution; verify with `perl -v`.

## What each gate checks

| Script | Plan task | Purpose |
|---|---|---|
| `verify-structure.sh` | D1 | All 9 expected files exist (1 SKILL.md + 4 references + 4 commands) |
| `verify-no-python.sh` | D2 | Zero Python residue in shipped skill files (skill is harness-agnostic) |
| `verify-no-python-neg.sh` | D2-neg | D2 actually catches planted Python patterns in fixture |
| `verify-anti-irony.sh` | D3 | M6 sub-gates: verdicts, safety markers, classifier schema, segmentation internals each live in exactly one canonical home |
| `verify-anti-irony-neg.sh` | D3-neg | D3 actually catches planted violations of all 4 sub-gates |
| `verify-json-blocks.sh` | D4 | Every fenced ` ```json ` block parses individually via `jq empty`. Accepts optional path-list args. |
| `verify-json-blocks-neg.sh` | D4-neg | D4 actually catches malformed JSON in fixture |
| `verify-markdown.sh` | D5 | markdownlint-cli2 clean across dedupe skill files. Fails loudly if cli2 absent. |
| `verify-references.sh` | D6 | Every `references/*.md` and `commands/dedupe-*.md` path mentioned in skill files resolves to a real file (case-sensitive via `git ls-files`); typo'd slash-commands are flagged, not silently dropped |

## Negative-control philosophy

Every positive gate that can have a false-negative (D2, D3, D4) is paired
with a negative-control fixture and a `-neg.sh` script that runs the gate
against the fixture and asserts the gate catches the planted violations.

The fixtures live under `fixtures/`:

- `python-residue-negative.md` — deliberately contains all 7 Python patterns D2 must catch
- `anti-irony-violation.md` — deliberately violates all 4 D3 sub-gates
- `malformed-json-negative.md` — deliberately contains malformed JSON D4 must reject

If the positive gate ever silently weakens (e.g., a regex is gutted),
the paired negative-control gate fails loudly. This protects against
green-mirage verification where a passing gate proves nothing because
it would pass against any input.

D1, D5, D6 are positive-only — they verify presence/parseability of
real content, and a regression manifests as a normal red gate.
