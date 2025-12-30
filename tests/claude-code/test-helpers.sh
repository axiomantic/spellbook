#!/bin/bash

# Test Helper Functions for Spellbook Integration Tests

# assert_contains <output> <pattern> <test_name>
# Verifies that output contains the exact pattern (case-sensitive, literal match)
assert_contains() {
  local output="$1"
  local pattern="$2"
  local test_name="$3"

  if echo "$output" | grep -F -q "$pattern"; then
    echo "✓ $test_name"
    return 0
  else
    echo "✗ $test_name: Expected to find '$pattern'"
    return 1
  fi
}

# assert_not_contains <output> <pattern> <test_name>
# Verifies that output does NOT contain the pattern (case-sensitive, literal match)
assert_not_contains() {
  local output="$1"
  local pattern="$2"
  local test_name="$3"

  if echo "$output" | grep -F -q "$pattern"; then
    echo "✗ $test_name: Expected NOT to find '$pattern'"
    return 1
  else
    echo "✓ $test_name"
    return 0
  fi
}

# assert_file_exists <path> <test_name>
# Verifies that a file or directory exists at the given path
assert_file_exists() {
  local path="$1"
  local test_name="$2"

  if [ -e "$path" ]; then
    echo "✓ $test_name"
    return 0
  else
    echo "✗ $test_name: File not found at '$path'"
    return 1
  fi
}

# assert_symlink <path> <target> <test_name>
# Verifies that path is a symlink pointing to target
assert_symlink() {
  local path="$1"
  local expected_target="$2"
  local test_name="$3"

  if [ ! -L "$path" ]; then
    echo "✗ $test_name: '$path' is not a symlink"
    return 1
  fi

  local actual_target
  actual_target=$(readlink "$path")

  if [ "$actual_target" = "$expected_target" ]; then
    echo "✓ $test_name"
    return 0
  else
    echo "✗ $test_name: Expected symlink to '$expected_target', got '$actual_target'"
    return 1
  fi
}

# assert_exit_code <command> <expected_code> <test_name>
# Runs command and verifies it exits with expected code
assert_exit_code() {
  local command="$1"
  local expected_code="$2"
  local test_name="$3"

  eval "$command" >/dev/null 2>&1
  local actual_code=$?

  if [ "$actual_code" -eq "$expected_code" ]; then
    echo "✓ $test_name"
    return 0
  else
    echo "✗ $test_name: Expected exit code $expected_code, got $actual_code"
    return 1
  fi
}

# assert_output_matches <command> <pattern> <test_name>
# Runs command and verifies output contains pattern
assert_output_matches() {
  local command="$1"
  local pattern="$2"
  local test_name="$3"

  local output
  output=$(eval "$command" 2>&1)

  if echo "$output" | grep -F -q "$pattern"; then
    echo "✓ $test_name"
    return 0
  else
    echo "✗ $test_name: Output does not contain '$pattern'"
    echo "  Output was: $output"
    return 1
  fi
}
