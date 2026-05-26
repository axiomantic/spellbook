#!/usr/bin/env bash
# D1: Verify the 9 expected dedupe skill files exist AND are non-empty AND
# no unexpected (orphan) files are shipped alongside them.
#
# Layout:
#   skills/dedupe/SKILL.md
#   skills/dedupe/references/{verdict-taxonomy,safety-markers,counterfactual-prompt,segmentation-protocol}.md
#   commands/dedupe-{setup,analyze,report,apply}.md
#
# Hardening (post green-mirage audit):
#  - Use `[ -s "$f" ]` (size > 0) instead of `[ -f "$f" ]` so empty files fail.
#  - Enumerate actual `skills/dedupe/references/*.md` and `commands/dedupe-*.md`
#    and flag any not in the expected set (orphan detection).

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

FAILURES=0

# Presence + non-empty check
for f in "${EXPECTED[@]}"; do
    if [ -s "$f" ]; then
        echo "PASS: $f"
    elif [ -f "$f" ]; then
        echo "FAIL: empty (0-byte) file: $f"
        FAILURES=$((FAILURES + 1))
    else
        echo "FAIL: missing $f"
        FAILURES=$((FAILURES + 1))
    fi
done

# Orphan detection: any *.md under skills/dedupe/references/ or
# commands/dedupe-*.md that is NOT in EXPECTED is suspicious.
is_expected() {
    local needle="$1"
    local e
    for e in "${EXPECTED[@]}"; do
        [ "$e" = "$needle" ] && return 0
    done
    return 1
}

# References directory
if [ -d skills/dedupe/references ]; then
    while IFS= read -r actual; do
        [ -z "$actual" ] && continue
        if ! is_expected "$actual"; then
            echo "FAIL: orphan file (not in expected set): $actual"
            FAILURES=$((FAILURES + 1))
        fi
    done < <(find skills/dedupe/references -maxdepth 1 -type f -name '*.md' 2>/dev/null | sort)
fi

# Top-level SKILL.md is the only allowed top-level .md under skills/dedupe/
while IFS= read -r actual; do
    [ -z "$actual" ] && continue
    if ! is_expected "$actual"; then
        echo "FAIL: orphan file (not in expected set): $actual"
        FAILURES=$((FAILURES + 1))
    fi
done < <(find skills/dedupe -maxdepth 1 -type f -name '*.md' 2>/dev/null | sort)

# commands/dedupe-*.md
while IFS= read -r actual; do
    [ -z "$actual" ] && continue
    if ! is_expected "$actual"; then
        echo "FAIL: orphan file (not in expected set): $actual"
        FAILURES=$((FAILURES + 1))
    fi
done < <(find commands -maxdepth 1 -type f -name 'dedupe-*.md' 2>/dev/null | sort)

if [ "$FAILURES" -gt 0 ]; then
    echo "FAIL: D1 ($FAILURES issue(s) detected)"
    exit 1
fi

echo "PASS: D1 (all 9 expected files present, non-empty, no orphans)"
exit 0
