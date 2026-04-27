# Crystallize Fixtures

Each subdirectory is a fixture: input + expected output(s) + metadata.

To run a fixture: read `metadata.yaml` for `test_target`, then invoke the
named command (`/crystallize` or `/crystallize-verify`) on `input.md` and
compare the output against `expected_rules.md` (and optionally
`expected_general.md`) plus `expected_verdict`.

Until a programmatic slash-command harness exists, fixtures are runnable
manually. The fixture format is harness-agnostic.

## Structure

```
crystallize-fixtures/
├── README.md            (this file)
├── mixed-format/        (PASS — three input rule forms in one document)
├── no-rules/            (PASS — placeholder Rules section emission)
├── re-crystallize/      (PASS — preserves canonical Rules verbatim, advances last-confirmed)
├── byte-drift/          (FAIL — verifier catches one-character drift in a rule body)
└── mixed-tag-block/     (PASS — splits mixed `<CRITICAL>` block at paragraph boundary)
```

Each fixture directory contains:

- `metadata.yaml` — `test_target`, `description`, `expected_verdict`, and (when failing) `expected_findings`.
- `input.md` — the source document the command operates on.
- `expected_rules.md` (crystallize fixtures) — byte-exact expected canonical `## Rules` section.
- `expected_general.md` (some fixtures) — byte-exact expected General Instructions tail when content is split.
- `corrupted.md` (verifier fixtures) — the second document passed to `/crystallize-verify` alongside `input.md`.

All provenance dates inside fixtures are deterministic literals (`2026-04-27`,
or `2026-04-20` for prior-pass timestamps in `re-crystallize`). Fixtures must
be byte-stable across runs; do not introduce dynamic dates.

## Verdict schema

Every `metadata.yaml` uses the standardized verdict schema:

```yaml
expected_verdict: PASS  # or FAIL
expected_findings:      # only when FAIL
  - severity: CRITICAL  # or HIGH | MEDIUM | LOW | ADVISORY
    type: "exact phrasing from design §4.8 severity table row"
```

The `type` field, when present, MUST quote a row label from the
`/crystallize-verify` severity table verbatim.
