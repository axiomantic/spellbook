#!/usr/bin/env bash
# D3: M6 anti-irony grep gates (design §16).
#
# The dedupe skill itself contains a lot of language ABOUT duplication,
# safety markers, classifier schemas, and segmentation internals. To
# avoid being ironic (the dedupe skill containing dupes of its own
# concepts), each concept has ONE canonical home, and these gates
# reject inline mentions outside that home.
#
# Sub-gates:
#   (a) Verdict definitions outside references/verdict-taxonomy.md
#   (b) Safety markers outside references/safety-markers.md
#   (c) Classifier schema fields outside references/counterfactual-prompt.md
#       (commands/dedupe-apply.md is whitelisted: it shows journal-entry
#       output that legitimately echoes classifier verdicts)
#   (d) Segmentation internals outside references/segmentation-protocol.md
#
# Usage: verify-anti-irony.sh [target-files...]
#   With no args, scans the canonical skill+commands set with proper
#   exclusions. With args, scans those targets with NO exclusions
#   (used by D3-neg against a fixture).

set -u

OVERRIDE_TARGETS=0
EXTRA_TARGETS=()
for arg in "$@"; do
    EXTRA_TARGETS+=("$arg")
    OVERRIDE_TARGETS=1
done

# Canonical homes (these files are exempt from each respective sub-gate)
HOME_A="skills/dedupe/references/verdict-taxonomy.md"
HOME_B="skills/dedupe/references/safety-markers.md"
HOME_C="skills/dedupe/references/counterfactual-prompt.md"
WHITELIST_C="commands/dedupe-apply.md"
HOME_D="skills/dedupe/references/segmentation-protocol.md"

# Default scan set: SKILL.md + all dedupe-*.md commands
DEFAULT_TARGETS=(
    skills/dedupe/SKILL.md
    commands/dedupe-setup.md
    commands/dedupe-analyze.md
    commands/dedupe-report.md
    commands/dedupe-apply.md
)

FAIL=0

# Sub-gate (a): Verdict-name colon/dash definitions outside HOME_A
# Patterns: EXTRACT:, KEEP-placement:, KEEP-reinforcement:, KEEP-contextual:, RECONCILE-drifted:
# Also matches " - " dash-defn form.
PATTERN_A='^[[:space:]]*(EXTRACT|KEEP-placement|KEEP-reinforcement|KEEP-contextual|RECONCILE-drifted)[[:space:]]*[:-]'

# Sub-gate (b): Safety markers and imperative-lead-in language outside HOME_B
# Patterns: <CRITICAL>, <FORBIDDEN>, <RULE>, <ROLE>, <FINAL_EMPHASIS>,
#           "Inviolable Rules", "Git Safety", "production-quality or nothing",
#           table-cell imperative lead-ins (NEVER/ALWAYS/MUST/DO NOT)
PATTERN_B_TAGS='<(CRITICAL|FORBIDDEN|RULE|ROLE|FINAL_EMPHASIS)>'
PATTERN_B_PHRASES='Inviolable Rules?|Git Safety|production[- ]quality or nothing'
PATTERN_B_TABLECELL='^\|[[:space:]]*`?(NEVER|ALWAYS|MUST|DO NOT)\b'

# Sub-gate (c): Classifier schema field names in JSON-key syntax outside HOME_C and WHITELIST_C
PATTERN_C='"(verdict|rationale|confidence|counterfactual_loss|inline_mandatory|prompt_version)":'

# Sub-gate (d): Segmentation internals outside HOME_D
PATTERN_D='sha256\(|bucket_key|\\x1f|first_3_normalized_lines|<file-stem>:no-headings|code:python|marked:<file-stem>'

run_subgate() {
    local label="$1"
    local pattern="$2"
    local home="$3"
    local whitelist="${4:-}"
    shift 4 2>/dev/null || shift $#

    local targets=()
    if [ "$OVERRIDE_TARGETS" -eq 1 ]; then
        targets=("${EXTRA_TARGETS[@]}")
    else
        for t in "${DEFAULT_TARGETS[@]}"; do
            [ "$t" = "$home" ] && continue
            [ -n "$whitelist" ] && [ "$t" = "$whitelist" ] && continue
            targets+=("$t")
        done
    fi

    if [ "${#targets[@]}" -eq 0 ]; then
        echo "PASS: D3($label) (no targets to scan)"
        return 0
    fi

    local hits
    hits=$(grep -nE "$pattern" "${targets[@]}" 2>/dev/null || true)
    if [ -n "$hits" ]; then
        echo "FAIL: D3($label) matched forbidden pattern outside $home:"
        echo "$hits"
        FAIL=$((FAIL + 1))
        return 1
    fi
    echo "PASS: D3($label)"
    return 0
}

run_subgate a "$PATTERN_A" "$HOME_A" ""

# Sub-gate b is composite — run each pattern separately for clarity
{
    targets=()
    if [ "$OVERRIDE_TARGETS" -eq 1 ]; then
        targets=("${EXTRA_TARGETS[@]}")
    else
        for t in "${DEFAULT_TARGETS[@]}"; do
            [ "$t" = "$HOME_B" ] && continue
            targets+=("$t")
        done
    fi
    if [ "${#targets[@]}" -gt 0 ]; then
        hits_b=$(grep -nE "$PATTERN_B_TAGS|$PATTERN_B_PHRASES|$PATTERN_B_TABLECELL" "${targets[@]}" 2>/dev/null || true)
        if [ -n "$hits_b" ]; then
            echo "FAIL: D3(b) matched safety-marker pattern outside $HOME_B:"
            echo "$hits_b"
            FAIL=$((FAIL + 1))
        else
            echo "PASS: D3(b)"
        fi
    else
        echo "PASS: D3(b) (no targets)"
    fi
}

# Sub-gate c
{
    targets=()
    if [ "$OVERRIDE_TARGETS" -eq 1 ]; then
        targets=("${EXTRA_TARGETS[@]}")
    else
        for t in "${DEFAULT_TARGETS[@]}"; do
            [ "$t" = "$HOME_C" ] && continue
            [ "$t" = "$WHITELIST_C" ] && continue
            targets+=("$t")
        done
    fi
    if [ "${#targets[@]}" -gt 0 ]; then
        hits_c=$(grep -nE "$PATTERN_C" "${targets[@]}" 2>/dev/null || true)
        if [ -n "$hits_c" ]; then
            echo "FAIL: D3(c) matched classifier-schema pattern outside $HOME_C (and whitelist $WHITELIST_C):"
            echo "$hits_c"
            FAIL=$((FAIL + 1))
        else
            echo "PASS: D3(c)"
        fi
    else
        echo "PASS: D3(c) (no targets)"
    fi
}

run_subgate d "$PATTERN_D" "$HOME_D" ""

if [ "$FAIL" -gt 0 ]; then
    echo "FAIL: D3 ($FAIL sub-gate(s) failed)"
    exit 1
fi

echo "PASS: D3 (all 4 sub-gates clean)"
exit 0
