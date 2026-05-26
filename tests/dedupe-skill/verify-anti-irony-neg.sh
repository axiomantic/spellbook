#!/usr/bin/env bash
# D3-neg: Negative-control gate for verify-anti-irony.sh.
#
# Runs D3 against the anti-irony-violation.md fixture (which deliberately
# violates each of the 4 sub-gates). Asserts:
#   - overall exit code is non-zero
#   - each sub-gate fires ≥ 1 hit
#
# This protects against false-negatives in D3.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$SCRIPT_DIR/fixtures/anti-irony-violation.md"

if [ ! -f "$FIXTURE" ]; then
    echo "FAIL: fixture missing: $FIXTURE"
    exit 1
fi

OUTPUT=$(bash "$SCRIPT_DIR/verify-anti-irony.sh" "$FIXTURE" 2>&1)
RC=$?

if [ "$RC" -eq 0 ]; then
    echo "FAIL: D3 missed planted violations in fixture (exit=0)"
    echo "$OUTPUT"
    exit 1
fi

# Verify each sub-gate fired
MISSING=()
for sub in a b c d; do
    if ! echo "$OUTPUT" | grep -q "FAIL: D3($sub)"; then
        MISSING+=("$sub")
    fi
done

if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "FAIL: D3 sub-gate(s) did not fire on fixture: ${MISSING[*]}"
    echo "Output was:"
    echo "$OUTPUT"
    exit 1
fi

echo "PASS: D3 catches anti-irony violations (all 4 sub-gates fired, exit=$RC)"
exit 0
