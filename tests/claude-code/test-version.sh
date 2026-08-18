#!/bin/bash

# Test: Version File Validation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."

failures=0

echo "Testing version files..."

# Test .version file exists
assert_file_exists "$REPO_ROOT/.version" ".version file exists" || failures=$((failures + 1))

# Test version format (semver)
assert_exit_code "cat $REPO_ROOT/.version | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$'" 0 "Version follows semver format" || failures=$((failures + 1))

# Test CHANGELOG.md exists
assert_file_exists "$REPO_ROOT/CHANGELOG.md" "CHANGELOG.md exists" || failures=$((failures + 1))

# Test CHANGELOG has version header
version=$(cat "$REPO_ROOT/.version")
assert_contains "$(cat "$REPO_ROOT/CHANGELOG.md")" "## [$version]" "CHANGELOG contains version $version" || failures=$((failures + 1))

echo ""
echo "Version tests complete"

exit $((failures > 0))
