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
bash tests/dedupe-skill/verify-markdown.sh
bash tests/dedupe-skill/verify-references.sh
```

All scripts must exit 0.

## Dependencies

- POSIX `sh` / `bash`
- GNU `grep` with `-E -r -n` (system `grep` on macOS works)
- `jq` for D4 (`brew install jq`)
- `markdownlint-cli2` for D5 (`npm i -g markdownlint-cli2` or `brew install markdownlint-cli2`); D5 skips gracefully if absent

## What each gate checks

| Script | Plan task | Purpose |
|---|---|---|
| `verify-structure.sh` | D1 | All 9 expected files exist (1 SKILL.md + 4 references + 4 commands) |
| `verify-no-python.sh` | D2 | Zero Python residue in shipped skill files (skill is harness-agnostic) |
| `verify-no-python-neg.sh` | D2-neg | D2 actually catches planted Python patterns in fixture |
| `verify-anti-irony.sh` | D3 | M6 sub-gates: verdicts, safety markers, classifier schema, segmentation internals each live in exactly one canonical home |
| `verify-anti-irony-neg.sh` | D3-neg | D3 actually catches planted violations of all 4 sub-gates |
| `verify-json-blocks.sh` | D4 | Every fenced ` ```json ` block parses individually via `jq empty` |
| `verify-markdown.sh` | D5 | markdownlint-cli2 clean across dedupe skill files |
| `verify-references.sh` | D6 | Every `references/*.md` and `commands/dedupe-*.md` path mentioned in skill files resolves to a real file |

## Negative-control philosophy

Every positive gate that can have a false-negative (D2 and D3) is paired
with a negative-control fixture and a `-neg.sh` script that runs the gate
against the fixture and asserts the gate catches the planted violations.

The fixtures live under `fixtures/`:

- `python-residue-negative.md` — deliberately contains all 7 Python patterns D2 must catch
- `anti-irony-violation.md` — deliberately violates all 4 D3 sub-gates

If the positive gate ever silently weakens (e.g., a regex is gutted),
the paired negative-control gate fails loudly. This protects against
green-mirage verification where a passing gate proves nothing because
it would pass against any input.

D1, D4, D5, D6 are positive-only — they verify presence/parseability of
real content, and a regression manifests as a normal red gate.
