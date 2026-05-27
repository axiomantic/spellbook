#!/usr/bin/env bash
# D2: Verify zero Python residue in the dedupe skill.
#
# The dedupe skill is harness-agnostic. Any Python idioms (imports,
# .py mentions, pip, shebangs, `python -m`) are residue from the
# implementation plan and must NOT leak into shipped skill files.
#
# Scans: skills/dedupe/, commands/dedupe-*.md, tests/dedupe-skill/
# Excludes: this script itself + tests/dedupe-skill/fixtures/ (intentionally Python-rich)
#
# Optional override: pass scan targets as args. Pass --no-default-excludes
# to disable the fixture exclusion (used by D2-neg).

set -u

EXCLUDE_FIXTURES=1
TARGETS=()
for arg in "$@"; do
    case "$arg" in
        --no-default-excludes) EXCLUDE_FIXTURES=0 ;;
        *) TARGETS+=("$arg") ;;
    esac
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
    TARGETS=(skills/dedupe commands tests/dedupe-skill)
fi

# Canonical ERE pattern: imports, .py files, shebangs, python interpreter, pip, python -m
PATTERN='(^[[:space:]]*(import|from)[[:space:]]+[A-Za-z_])|(\.py($|[^A-Za-z]))|(^#!.*python)|(\bpython[23]?([[:space:]]|[(),;|&]|$))|(\bpip[23]?[[:space:]]+install)|(python[[:space:]]+-m)'

# Build grep args
GREP_ARGS=(-rnE --include='*.md' --include='*.sh')
GREP_ARGS+=(--exclude=verify-no-python.sh)
GREP_ARGS+=(--exclude=verify-no-python-neg.sh)
# verify-anti-irony.sh contains regex pattern literals that mention "python"
# as part of forbidden-pattern definitions (e.g., `code:python` in a marker
# token); excluded for the same reason this script excludes itself.
GREP_ARGS+=(--exclude=verify-anti-irony.sh)
if [ "$EXCLUDE_FIXTURES" -eq 1 ]; then
    GREP_ARGS+=(--exclude-dir=fixtures)
fi

# When TARGETS contains a single specific file, restrict --include to allow it
if [ "${#TARGETS[@]}" -eq 1 ] && [ -f "${TARGETS[0]}" ]; then
    # Drop --include filters when targeting a single file directly
    GREP_ARGS=(-nE)
    if [ "$EXCLUDE_FIXTURES" -eq 1 ]; then
        : # no exclude needed for single file
    fi
fi

# Filter commands/ to only dedupe-*.md
FILTERED_TARGETS=()
for t in "${TARGETS[@]}"; do
    if [ "$t" = "commands" ]; then
        for f in commands/dedupe-*.md; do
            [ -f "$f" ] && FILTERED_TARGETS+=("$f")
        done
    else
        FILTERED_TARGETS+=("$t")
    fi
done

# Guard: if all targets filter to empty, grep would read stdin and hang.
if [ "${#FILTERED_TARGETS[@]}" -eq 0 ]; then
    echo "PASS: D2 (no targets to scan)"
    exit 0
fi

MATCHES=$(grep "${GREP_ARGS[@]}" "$PATTERN" "${FILTERED_TARGETS[@]}" 2>/dev/null || true)

if [ -n "$MATCHES" ]; then
    echo "FAIL: D2 found Python residue:"
    echo "$MATCHES"
    exit 1
fi

echo "PASS: D2 (no Python residue in $(IFS=','; echo "${FILTERED_TARGETS[*]}"))"
exit 0
