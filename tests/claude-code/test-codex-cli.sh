#!/bin/bash

# Test: Codex CLI Functionality

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."
CLI="$REPO_ROOT/.codex/spellbook-codex"

echo "Testing Codex CLI..."

# Test CLI exists and is executable
assert_file_exists "$CLI" "Codex CLI exists"
assert_exit_code "test -x $CLI" 0 "Codex CLI is executable"

# Test --help command
assert_exit_code "$CLI --help" 0 "Help command exits successfully"
assert_output_matches "$CLI --help" "Usage:" "Help shows usage"

# Test --version command
assert_exit_code "$CLI --version" 0 "Version command exits successfully"
assert_output_matches "$CLI --version" "Spellbook" "Version shows Spellbook"

# Test invalid command
assert_exit_code "$CLI invalid-command" 2 "Invalid command returns exit code 2"

# Test use-skill without argument
assert_exit_code "$CLI use-skill" 2 "use-skill without argument returns exit code 2"

# Test use-skill with invalid name
assert_exit_code "$CLI use-skill '../etc/passwd'" 1 "use-skill rejects directory traversal"
assert_exit_code "$CLI use-skill 'my.skill'" 1 "use-skill rejects period in name"

echo ""
echo "Codex CLI tests complete"
