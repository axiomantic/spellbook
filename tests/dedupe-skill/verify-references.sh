#!/usr/bin/env bash
# D6: Verify every references/<name>.md and commands/dedupe-<phase>.md
# path mentioned in shipped skill files resolves to a real file.

set -u

SOURCES=(
    skills/dedupe/SKILL.md
    commands/dedupe-setup.md
    commands/dedupe-analyze.md
    commands/dedupe-report.md
    commands/dedupe-apply.md
)

MISSING=0
CHECKED=0

# Extract references/*.md mentions
for src in "${SOURCES[@]}"; do
    if [ ! -f "$src" ]; then
        echo "FAIL: source file missing: $src"
        MISSING=$((MISSING + 1))
        continue
    fi

    # references/<name>.md (relative path)
    while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        target="skills/dedupe/$ref"
        CHECKED=$((CHECKED + 1))
        if [ ! -f "$target" ]; then
            echo "FAIL: $src references missing file: $target"
            MISSING=$((MISSING + 1))
        fi
    done < <(grep -oE 'references/[A-Za-z0-9_.-]+\.md' "$src" | sort -u)

    # commands/dedupe-<phase>.md
    while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        CHECKED=$((CHECKED + 1))
        if [ ! -f "$ref" ]; then
            echo "FAIL: $src references missing file: $ref"
            MISSING=$((MISSING + 1))
        fi
    done < <(grep -oE 'commands/dedupe-[A-Za-z0-9_-]+\.md' "$src" | sort -u)

    # bare /dedupe-<phase> slash-command mentions resolve to commands/dedupe-<phase>.md
    while IFS= read -r cmd; do
        [ -z "$cmd" ] && continue
        phase="${cmd#/dedupe-}"
        target="commands/dedupe-${phase}.md"
        CHECKED=$((CHECKED + 1))
        if [ ! -f "$target" ]; then
            echo "FAIL: $src references missing command file: $target (from $cmd)"
            MISSING=$((MISSING + 1))
        fi
    done < <(grep -oE '/dedupe-(setup|analyze|report|apply)\b' "$src" | sort -u)
done

if [ "$MISSING" -gt 0 ]; then
    echo "FAIL: D6 ($MISSING reference(s) missing of $CHECKED checked)"
    exit 1
fi

echo "PASS: D6 (all $CHECKED references resolve)"
exit 0
