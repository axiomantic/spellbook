#!/usr/bin/env bash
# Aggregating runner for the dedupe-skill verification gates (plan §2 Track D).
#
# Every gate is uniformly exit-0-is-pass. The `-neg` gates already invert
# internally -- each runs its positive gate against a negative-control
# fixture and exits 0 only when that gate returns non-zero. This runner
# therefore MUST NOT invert any child's status; doing so would break the
# calibration rather than complete it.
#
# The gates must run from the repository root: they reference `skills/...`
# and `commands/...` as relative paths and shell out to `git ls-files`.
#
# Discovery floor: the gate list is globbed, not hardcoded, so a new gate
# is picked up without editing this file. A glob that silently collects
# nothing (or fewer gates than the floor) is the failure mode this runner
# exists to make loud, so the discovered count is asserted before any gate
# runs. Raise MIN_GATES when gates are added; it may never be lowered to
# accommodate a deletion.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MIN_GATES=9

cd "$REPO_ROOT" || {
    echo "FAIL: cannot cd to repo root $REPO_ROOT"
    exit 1
}

# `nullglob` so a non-matching pattern yields an empty array rather than the
# literal pattern string, which would otherwise be "run" as a missing file
# and muddy the floor check with a spurious gate.
shopt -s nullglob
GATES=("$SCRIPT_DIR"/verify-*.sh)
shopt -u nullglob

DISCOVERED=${#GATES[@]}

echo "========================================="
echo "Dedupe Skill Verification Gates"
echo "========================================="
echo "Discovered $DISCOVERED gate script(s) in $SCRIPT_DIR (floor: $MIN_GATES)"
echo ""

if [ "$DISCOVERED" -lt "$MIN_GATES" ]; then
    echo "FAIL: gate discovery floor breached -- found $DISCOVERED, require at least $MIN_GATES."
    echo "      Either a gate script was deleted/renamed, or discovery is broken."
    exit 1
fi

failures=0
passed=0

for gate in "${GATES[@]}"; do
    name="$(basename "$gate")"
    echo "--- $name"
    if bash "$gate"; then
        passed=$((passed + 1))
        echo "PASS: $name"
    else
        status=$?
        failures=$((failures + 1))
        echo "FAIL: $name (exit $status)"
    fi
    echo ""
done

echo "========================================="
echo "Gate Summary"
echo "========================================="
echo "Discovered: $DISCOVERED"
echo "Passed:     $passed"
echo "Failed:     $failures"
echo ""

if [ "$failures" -gt 0 ]; then
    echo "FAIL: dedupe-skill gates ($failures of $DISCOVERED failed)"
    exit 1
fi

echo "PASS: dedupe-skill gates (all $DISCOVERED passed)"
exit 0
