#!/bin/bash

# Test: Bootstrap Content Accuracy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."

echo "Testing bootstrap files..."

# Test Claude Code bootstrap
assert_file_exists "$REPO_ROOT/.claude-plugin/bootstrap.md" "Claude Code bootstrap exists"
assert_contains "$(cat $REPO_ROOT/.claude-plugin/bootstrap.md)" "Personal skills" "Priority model documented"
assert_contains "$(cat $REPO_ROOT/.claude-plugin/bootstrap.md)" "spellbook:skill-name" "Namespace syntax shown"
assert_not_contains "$(cat $REPO_ROOT/.claude-plugin/bootstrap.md)" "automatically loaded" "No auto-load claim"

# Test Codex bootstrap
assert_file_exists "$REPO_ROOT/.codex/spellbook-bootstrap.md" "Codex bootstrap exists"
assert_contains "$(cat $REPO_ROOT/.codex/spellbook-bootstrap.md)" "TodoWrite → update_plan" "Tool mapping documented"
assert_contains "$(cat $REPO_ROOT/.codex/spellbook-bootstrap.md)" "EXTREMELY_IMPORTANT" "Codex emphasis tags present"

echo ""
echo "Bootstrap tests complete"
