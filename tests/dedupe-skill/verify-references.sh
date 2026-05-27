#!/usr/bin/env bash
# D6: Verify every references/<name>.md and commands/dedupe-<phase>.md
# path mentioned in shipped skill files resolves to a real file.
#
# Hardening (post green-mirage audit):
#  - Case-sensitive lookup via `git ls-files` (the git index is always
#    case-sensitive, unlike macOS APFS where `[ -f Foo.md ]` matches `foo.md`).
#  - Permissive slash-command extraction: extracts ANY `/dedupe-<token>`
#    mention, then validates the phase against the known phase set. Typos
#    like `/dedupe-aply` are surfaced as FAIL, not silently dropped.

set -u

SOURCES=(
    skills/dedupe/SKILL.md
    commands/dedupe-setup.md
    commands/dedupe-analyze.md
    commands/dedupe-report.md
    commands/dedupe-apply.md
)

KNOWN_PHASES="setup analyze report apply"

# Snapshot tracked + non-ignored untracked files once (case-sensitive
# index view). Including `--others --exclude-standard` makes the gate
# usable during local development before a referenced file is staged,
# without picking up gitignored noise. Falls back to `find` if not in
# a git checkout (unlikely in CI but kept for robustness).
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    TRACKED=$(git ls-files --cached --others --exclude-standard)
else
    TRACKED=$(find skills commands -type f 2>/dev/null)
fi

# Case-sensitive existence check: is $1 an exact (byte-for-byte) entry in $TRACKED?
# Uses a bash here-string to avoid spawning printf and a pipe per lookup.
exists_exact() {
    local needle="$1"
    grep -Fxq -- "$needle" <<<"$TRACKED"
}

MISSING=0
CHECKED=0

for src in "${SOURCES[@]}"; do
    if ! exists_exact "$src"; then
        echo "FAIL: source file missing (case-sensitive): $src"
        MISSING=$((MISSING + 1))
        continue
    fi

    # references/<name>.md (relative to skills/dedupe/)
    while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        target="skills/dedupe/$ref"
        CHECKED=$((CHECKED + 1))
        if ! exists_exact "$target"; then
            echo "FAIL: $src references missing file (case-sensitive): $target"
            MISSING=$((MISSING + 1))
        fi
    done < <(grep -oE 'references/[A-Za-z0-9_.-]+\.md' "$src" | sort -u)

    # commands/dedupe-<phase>.md (full path mention)
    while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        CHECKED=$((CHECKED + 1))
        if ! exists_exact "$ref"; then
            echo "FAIL: $src references missing file (case-sensitive): $ref"
            MISSING=$((MISSING + 1))
        fi
    done < <(grep -oE 'commands/dedupe-[A-Za-z0-9_-]+\.md' "$src" | sort -u)

    # Bare /dedupe-<token> slash-command mentions: permissive extraction,
    # explicit phase-set validation. Catches typos like /dedupe-aply.
    #
    # A real slash-command appears at the start of a line, after whitespace,
    # or after a backtick/quote — NEVER as a path tail like
    # `<project-encoded>/dedupe-manifest-YYYY-MM-DD-...md`. We pre-filter with
    # perl to enforce that left-boundary, then extract the command token.
    while IFS= read -r cmd; do
        [ -z "$cmd" ] && continue
        # The perl regex above captures only [A-Za-z0-9_-], so no trailing
        # punctuation can leak into $cmd. No strip needed.
        phase="${cmd#/dedupe-}"
        CHECKED=$((CHECKED + 1))
        # Native shell `case` membership test against KNOWN_PHASES
        # (avoids spawning printf+grep for each token).
        case " $KNOWN_PHASES " in
            *" $phase "*) ;;
            *)
                echo "FAIL: $src uses unknown slash-command phase: $cmd (known: $KNOWN_PHASES)"
                MISSING=$((MISSING + 1))
                continue
                ;;
        esac
        target="commands/dedupe-${phase}.md"
        if ! exists_exact "$target"; then
            echo "FAIL: $src references missing command file (case-sensitive): $target (from $cmd)"
            MISSING=$((MISSING + 1))
        fi
    done < <(perl -nle 'while (/(?:^|[\s\`\x27"(\[])(\/dedupe-[A-Za-z][A-Za-z0-9_-]*)/g) { print $1 }' "$src" | sort -u)
done

if [ "$MISSING" -gt 0 ]; then
    echo "FAIL: D6 ($MISSING reference(s) missing of $CHECKED checked)"
    exit 1
fi

echo "PASS: D6 (all $CHECKED references resolve, case-sensitive)"
exit 0
