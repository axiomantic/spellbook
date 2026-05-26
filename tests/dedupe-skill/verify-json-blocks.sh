#!/usr/bin/env bash
# D4: Verify every fenced ```json block parses individually via jq.
#
# Scans:
#   skills/dedupe/references/counterfactual-prompt.md
#   commands/dedupe-apply.md
#
# Each fenced ```json ... ``` block is extracted and piped through
# `jq empty` separately (NOT concatenated). Any parse failure fails the gate.

set -u

if ! command -v jq >/dev/null 2>&1; then
    echo "FAIL: jq not installed (brew install jq)"
    exit 1
fi

FILES=(
    skills/dedupe/references/counterfactual-prompt.md
    commands/dedupe-apply.md
)

TOTAL=0
FAIL=0

for f in "${FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "FAIL: missing $f"
        FAIL=$((FAIL + 1))
        continue
    fi

    # Extract each ```json block into a numbered set of temp files.
    # Strategy: awk state machine tracking ``` fences and language tag.
    tmpdir=$(mktemp -d)
    awk -v out="$tmpdir/block" '
        /^```json[[:space:]]*$/ { in_json=1; n++; next }
        /^```[[:space:]]*$/ { if (in_json) { in_json=0 } ; next }
        { if (in_json) print > (out "_" n ".json") }
    ' "$f"

    for block in "$tmpdir"/block_*.json; do
        [ -f "$block" ] || continue
        TOTAL=$((TOTAL + 1))
        if ! jq empty "$block" >/dev/null 2>&1; then
            echo "FAIL: $f: block $(basename "$block") did not parse:"
            cat "$block"
            FAIL=$((FAIL + 1))
        fi
    done

    rm -rf "$tmpdir"
done

if [ "$FAIL" -gt 0 ]; then
    echo "FAIL: D4 ($FAIL block(s) failed of $TOTAL)"
    exit 1
fi

echo "PASS: D4 ($TOTAL json block(s) parsed cleanly)"
exit 0
