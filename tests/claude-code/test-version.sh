#!/bin/bash

# Test: Version File Validation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."

echo "Testing version files..."

# Test .version file exists
assert_file_exists "$REPO_ROOT/.version" ".version file exists"

# Test version format (semver)
assert_exit_code "cat $REPO_ROOT/.version | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$'" 0 "Version follows semver format"

# Test RELEASE-NOTES.md exists
assert_file_exists "$REPO_ROOT/RELEASE-NOTES.md" "RELEASE-NOTES.md exists"

# Test RELEASE-NOTES has version header
version=$(cat $REPO_ROOT/.version)
assert_contains "$(cat $REPO_ROOT/RELEASE-NOTES.md)" "## $version" "RELEASE-NOTES contains version $version"

echo ""
echo "Version tests complete"
