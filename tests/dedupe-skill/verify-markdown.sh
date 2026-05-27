#!/usr/bin/env bash
# D5: Markdownlint clean for dedupe skill files.
#
# Uses markdownlint-cli2 (configured at repo root via .markdownlint-cli2.jsonc).
# Acceptance: zero new violations vs. repo baseline.

set -u

if ! command -v markdownlint-cli2 >/dev/null 2>&1; then
    echo "FAIL: markdownlint-cli2 is required but not installed. Install via 'brew install markdownlint-cli2' or 'npm install -g markdownlint-cli2'."
    exit 1
fi

TARGETS=(
    'skills/dedupe/**/*.md'
    'commands/dedupe-*.md'
)

if markdownlint-cli2 "${TARGETS[@]}" 2>&1; then
    echo "PASS: D5 (markdownlint clean)"
    exit 0
fi

echo "FAIL: D5 (markdownlint violations)"
exit 1
