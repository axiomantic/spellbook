#!/bin/bash

# Test: Bootstrap Content Accuracy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."

failures=0

echo "Testing bootstrap files..."

# Test Claude Code bootstrap
assert_file_exists "$REPO_ROOT/.claude-plugin/bootstrap.md" "Claude Code bootstrap exists" || failures=$((failures + 1))
assert_contains "$(cat "$REPO_ROOT/.claude-plugin/bootstrap.md")" "Personal skills" "Priority model documented" || failures=$((failures + 1))
assert_contains "$(cat "$REPO_ROOT/.claude-plugin/bootstrap.md")" "spellbook:skill-name" "Namespace syntax shown" || failures=$((failures + 1))
assert_not_contains "$(cat "$REPO_ROOT/.claude-plugin/bootstrap.md")" "automatically loaded" "No auto-load claim" || failures=$((failures + 1))

# Test Codex bootstrap
assert_file_exists "$REPO_ROOT/.codex/spellbook-bootstrap.md" "Codex bootstrap exists" || failures=$((failures + 1))
assert_contains "$(cat "$REPO_ROOT/.codex/spellbook-bootstrap.md")" "TodoWrite" "Tool mapping documented" || failures=$((failures + 1))
assert_contains "$(cat "$REPO_ROOT/.codex/spellbook-bootstrap.md")" "update_plan" "Codex equivalent documented" || failures=$((failures + 1))
assert_contains "$(cat "$REPO_ROOT/.codex/spellbook-bootstrap.md")" "<CRITICAL>" "Codex emphasis tags present" || failures=$((failures + 1))

echo ""
echo "Bootstrap tests complete"

exit $((failures > 0))
