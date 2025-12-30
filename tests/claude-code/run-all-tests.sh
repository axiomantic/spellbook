#!/bin/bash

# Test Suite Runner for Spellbook Integration Tests

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "Spellbook Integration Test Suite"
echo "========================================="
echo ""

# Track test results
total_tests=0
passed_tests=0
failed_tests=0

# Function to run a test script
run_test() {
  local test_script="$1"
  local test_name=$(basename "$test_script" .sh)

  echo "Running $test_name..."
  if "$test_script"; then
    ((passed_tests++))
  else
    ((failed_tests++))
  fi
  ((total_tests++))
  echo ""
}

# Run all test scripts
run_test "$SCRIPT_DIR/test-version.sh"
run_test "$SCRIPT_DIR/test-bootstrap.sh"
run_test "$SCRIPT_DIR/test-codex-cli.sh"

# Print summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Total:  $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $failed_tests"
echo ""

if [ $failed_tests -eq 0 ]; then
  echo "✓ All tests passed!"
  exit 0
else
  echo "✗ Some tests failed"
  exit 1
fi
