#!/usr/bin/env bash
# D1: Verify the 9 expected dedupe skill files exist.
#
# Layout:
#   skills/dedupe/SKILL.md
#   skills/dedupe/references/{verdict-taxonomy,safety-markers,counterfactual-prompt,segmentation-protocol}.md
#   commands/dedupe-{setup,analyze,report,apply}.md

set -u

EXPECTED=(
    skills/dedupe/SKILL.md
    skills/dedupe/references/verdict-taxonomy.md
    skills/dedupe/references/safety-markers.md
    skills/dedupe/references/counterfactual-prompt.md
    skills/dedupe/references/segmentation-protocol.md
    commands/dedupe-setup.md
    commands/dedupe-analyze.md
    commands/dedupe-report.md
    commands/dedupe-apply.md
)

MISSING=0
for f in "${EXPECTED[@]}"; do
    if [ -f "$f" ]; then
        echo "PASS: $f"
    else
        echo "FAIL: missing $f"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -gt 0 ]; then
    echo "FAIL: $MISSING expected file(s) missing"
    exit 1
fi

echo "PASS: D1 (all 9 expected files present)"
exit 0
