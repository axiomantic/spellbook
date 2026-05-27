#!/usr/bin/env bash
# D4-neg: Negative control for verify-json-blocks.sh.
#
# Runs verify-json-blocks.sh against tests/dedupe-skill/fixtures/malformed-json-negative.md
# (which contains deliberately malformed JSON blocks) and asserts the gate
# FAILS. If D4 silently passes against this fixture, the gate is gutted.

set -u

FIXTURE=tests/dedupe-skill/fixtures/malformed-json-negative.md

if [ ! -f "$FIXTURE" ]; then
    echo "FAIL: D4-neg fixture missing: $FIXTURE"
    exit 1
fi

# Run verify-json-blocks.sh against the malformed fixture. Capture output for
# diagnostics but discard from stdout (we only care about exit status).
if bash tests/dedupe-skill/verify-json-blocks.sh "$FIXTURE" >/dev/null 2>&1; then
    echo "FAIL: D4-neg (verify-json-blocks.sh silently passed against malformed fixture; gate is broken)"
    exit 1
fi

echo "PASS: D4-neg (verify-json-blocks.sh correctly rejected malformed JSON fixture)"
exit 0
