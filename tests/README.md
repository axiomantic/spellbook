# Spellbook Test Suite

This directory contains test infrastructure for spellbook.

## Test Organization

```
tests/
├── claude-code/          # Integration tests (bash)
│   ├── test-helpers.sh   # Assertion utilities
│   ├── test-bootstrap.sh # Bootstrap content tests
│   ├── test-version.sh   # Version file validation
│   ├── test-codex-cli.sh # Codex CLI tests
│   └── run-all-tests.sh  # Test suite runner
├── unit/                 # Unit tests (Vitest)
│   ├── package.json      # Test dependencies
│   └── test-skills-core.mjs # Core library tests
└── README.md            # This file
```

## Running Tests

### All Tests

```bash
# From repository root
tests/claude-code/run-all-tests.sh
```

### Unit Tests Only

```bash
cd tests/unit
npm test

# Watch mode for development
npm run test:watch
```

### Specific Integration Test

```bash
tests/claude-code/test-bootstrap.sh
tests/claude-code/test-version.sh
tests/claude-code/test-codex-cli.sh
```

## Test Categories

### Integration Tests

Bash scripts that test end-to-end functionality:

- **test-version.sh**: Validates .version file format and RELEASE-NOTES.md
- **test-bootstrap.sh**: Verifies bootstrap files contain correct content
- **test-codex-cli.sh**: Tests Codex CLI commands and error handling

### Unit Tests

Vitest tests for core library functions:

- **test-skills-core.mjs**: Tests for lib/skills-core.js functions
  - `extractFrontmatter()` - Parse YAML frontmatter
  - `stripFrontmatter()` - Remove frontmatter from content
  - `findSkillsInDir()` - Recursive skill discovery
  - `resolveSkillPath()` - Priority-based skill resolution
  - Skill name validation patterns

## Test Helpers

Integration tests use helper functions from `test-helpers.sh`:

- `assert_contains` - Verify output contains pattern
- `assert_not_contains` - Verify output does NOT contain pattern
- `assert_file_exists` - Verify file/directory exists
- `assert_symlink` - Verify symlink points to correct target
- `assert_exit_code` - Verify command exits with expected code
- `assert_output_matches` - Run command and verify output

## CI/CD

Tests run automatically on:
- Push to main branch
- Pull requests to main branch

See `.github/workflows/test.yml` for CI configuration.

## Writing New Tests

### Integration Test Template

```bash
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

REPO_ROOT="$SCRIPT_DIR/../.."

echo "Testing [feature name]..."

# Your test assertions here
assert_file_exists "$REPO_ROOT/path/to/file" "Test description"

echo ""
echo "[Feature name] tests complete"
```

### Unit Test Template

```javascript
import { describe, it, expect } from 'vitest';
import { functionName } from '../../lib/module.js';

describe('functionName', () => {
  it('should do expected behavior', () => {
    const result = functionName(input);
    expect(result).toBe(expected);
  });
});
```

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed
- `2` - Invalid usage or command

## Requirements

- Bash 4.0+
- Node.js 20+
- npm (for unit tests)
