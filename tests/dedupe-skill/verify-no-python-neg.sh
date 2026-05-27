#!/usr/bin/env bash
# D2-neg: Negative-control gate for verify-no-python.sh.
#
# Runs verify-no-python.sh against the python-residue-negative.md fixture
# (with the fixture exclusion overridden). Asserts the gate exits NON-ZERO,
# i.e., catches the planted patterns.
#
# This protects against false-negatives: if someone weakens the D2 pattern,
# this gate fails and surfaces the regression.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$SCRIPT_DIR/fixtures/python-residue-negative.md"

if [ ! -f "$FIXTURE" ]; then
    echo "FAIL: fixture missing: $FIXTURE"
    exit 1
fi

# Run D2 against the fixture, with fixture exclusion disabled
bash "$SCRIPT_DIR/verify-no-python.sh" --no-default-excludes "$FIXTURE" >/dev/null 2>&1
RC=$?

if [ "$RC" -eq 0 ]; then
    echo "FAIL: D2 missed planted Python patterns in fixture (exit=0)"
    exit 1
fi

echo "PASS: D2 catches Python residue (exit=$RC)"
exit 0
