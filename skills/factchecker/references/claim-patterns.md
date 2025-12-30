# Claim Extraction Patterns

This reference documents patterns for identifying claims in code and documentation.

## Comment Patterns by Language

### JavaScript/TypeScript
```regex
\/\/\s*(.+)$                           # Single-line //
\/\*\s*([\s\S]*?)\s*\*\/               # Multi-line /* */
```

### Python
```regex
#\s*(.+)$                              # Single-line #
(["']{3})([\s\S]*?)\1                  # Docstrings """ or '''
```

### Ruby
```regex
#\s*(.+)$                              # Single-line #
=begin([\s\S]*?)=end                   # Multi-line =begin/=end
```

### Go
```regex
\/\/\s*(.+)$                           # Single-line //
\/\*\s*([\s\S]*?)\s*\*\/               # Multi-line /* */
```

### Rust
```regex
\/\/\s*(.+)$                           # Single-line //
\/\/\/\s*(.+)$                         # Doc comment ///
\/\*\s*([\s\S]*?)\s*\*\/               # Multi-line /* */
```

### HTML/XML
```regex
<!--\s*([\s\S]*?)\s*-->                # HTML comments
```

### SQL
```regex
--\s*(.+)$                             # Single-line --
\/\*\s*([\s\S]*?)\s*\*\/               # Multi-line /* */
```

### Shell/Bash
```regex
#\s*(.+)$                              # Single-line #
```

---

## Claim Indicator Keywords

These keywords often precede verifiable claims:

### Behavior Assertions
- `returns`, `return`, `returns null`, `returns undefined`
- `throws`, `raises`, `errors when`, `fails if`
- `ensures`, `guarantees`, `promises`
- `never`, `always`, `must`, `shall`
- `will`, `does`, `is`, `are`

### Technical Properties
- `O(`, `complexity`, `time complexity`, `space complexity`
- `thread-safe`, `threadsafe`, `thread safe`
- `atomic`, `lock-free`, `wait-free`, `reentrant`
- `pure`, `idempotent`, `side-effect free`, `no side effects`
- `immutable`, `readonly`, `const`

### Security Properties
- `sanitize`, `sanitized`, `sanitization`
- `escape`, `escaped`, `escaping`
- `validate`, `validated`, `validation`
- `secure`, `safe`, `xss`, `injection`
- `hash`, `hashed`, `encrypt`, `encrypted`
- `authenticate`, `authorize`

### Performance Claims
- `cached`, `memoized`, `lazy`
- `optimized`, `fast`, `efficient`
- `batched`, `bulk`, `parallel`
- benchmark numbers: `ms`, `seconds`, `ops/sec`, `%`

### Compatibility/Requirements
- `requires`, `needs`, `depends on`
- `compatible with`, `works with`, `supports`
- `version`, `v\d+`, `>=`, `<=`

### Historical/TODO
- `TODO`, `FIXME`, `HACK`, `XXX`, `BUG`
- `workaround`, `temporary`, `legacy`
- `deprecated`, `obsolete`
- `#\d+` (issue references)
- `fixes`, `closes`, `resolves`

---

## Naming Convention Patterns

Function/variable names that imply verifiable behavior:

### Validation Functions
```regex
(validate|verify|check|assert|ensure|confirm)[A-Z_]
is[A-Z][a-zA-Z]*                       # isValid, isEmpty, isAuthenticated
has[A-Z][a-zA-Z]*                      # hasPermission, hasAccess
can[A-Z][a-zA-Z]*                      # canEdit, canDelete
```

### Safety Functions
```regex
safe[A-Z][a-zA-Z]*                     # safeParseJSON, safeDivide
sanitize[A-Z][a-zA-Z]*                 # sanitizeInput, sanitizeHTML
escape[A-Z][a-zA-Z]*                   # escapeHTML, escapeRegex
```

### Pure/Immutable Functions
```regex
(get|compute|calculate|derive)[A-Z]    # Implies no side effects
(create|make|build)[A-Z]               # Implies returns new object
(clone|copy|duplicate)[A-Z]            # Implies immutable operation
```

### Async/Concurrent
```regex
(async|await|promise|defer)[A-Z_]
(lock|unlock|acquire|release)[A-Z_]
(atomic|sync|synchronized)[A-Z_]
```

---

## Numeric Claim Patterns

```regex
\d+\s*(ms|milliseconds?|seconds?|s|minutes?|min|hours?|hr)   # Time durations
\d+(\.\d+)?\s*%                                               # Percentages
\d+\s*(KB|MB|GB|bytes?)                                       # Sizes
\d+\s*(req|requests?|ops|operations?)\s*(/|per)\s*(s|sec|min) # Rates
O\(\s*[n\d\s\*\^log]+\s*\)                                    # Big-O notation
```

---

## Documentation File Patterns

### README Claims
- Feature lists (usually bullet points)
- Installation requirements
- API documentation
- Example code blocks
- Compatibility tables

### Changelog Claims
- "Added", "Fixed", "Changed", "Removed" entries
- Version compatibility notes
- Breaking change descriptions

### API Documentation
- Parameter descriptions
- Return value descriptions
- Error conditions
- Examples

---

## Extraction Priority

When extracting claims, prioritize:

1. **High confidence claims**: Use strong assertion words (guarantees, ensures, always, never)
2. **Security-related**: Any claim about safety, sanitization, authentication
3. **Numeric claims**: Specific numbers are easily verifiable
4. **Behavior contracts**: Return values, exceptions, state changes
5. **Compatibility claims**: Version requirements, platform support
6. **Lower priority**: General descriptions, subjective statements

---

## False Positive Filters

Skip these patterns (not verifiable claims):

```regex
# Attribution/authorship
(Author|Copyright|License|Created by|Maintained by)

# Formatting/style
(TODO: format|FIXME: style|cleanup)

# Obvious/tautological
(This function|This class|This module)\s+(is|does|handles)

# Questions
\?$

# Disabled/commented code
(\/\/|#)\s*(if|for|while|return|const|let|var|function|def|class)
```

---

## Output Format

For each extracted claim:

```json
{
  "id": "claim-001",
  "text": "returns null when user not found",
  "location": {
    "file": "src/api/users.ts",
    "line": 45,
    "column": 5
  },
  "source_type": "comment",
  "category": "behavior",
  "confidence": 0.9,
  "keywords": ["returns", "null", "when"],
  "context": {
    "function": "findUserById",
    "class": "UserService",
    "surrounding_code": "..."
  }
}
```
