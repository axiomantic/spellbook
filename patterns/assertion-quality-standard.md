# Assertion Quality Standard

## Invariant Principles

1. **Assertions must catch garbage.** If broken production code still passes the test, the assertion is worthless.
2. **Position matters, not just presence.** Proving X exists SOMEWHERE is not proving X is WHERE it should be.
3. **Stronger is always better.** Downgrade from exact match only with written justification.
4. **Every assertion must name its kill.** If you cannot name a specific mutation the assertion catches, it catches nothing.

## The Assertion Strength Ladder

Per output type, a strict hierarchy. Use the highest level achievable. Levels below PREFERRED require written justification (inline comment explaining why).

### String/Text Output (writers, formatters, serializers)

| Level | Name | Status |
|-------|------|--------|
| 5 | Exact match (`assert output == expected`) | GOLD |
| 4 | Parsed structural (parse output, assert on parsed structure) | PREFERRED |
| 3 | Structural containment (verify X inside Y's block by index) | ACCEPTABLE with justification |
| 2 | Bare substring (`assert "X" in output`) | BANNED |
| 1 | Length/existence (`assert len(x) > 0`) | BANNED |

### Object Output

| Level | Name | Status |
|-------|------|--------|
| 5 | Full equality (`assert result == expected`) | GOLD |
| 4 | All-field assertions (every semantically important field) | PREFERRED |
| 3 | Partial field assertions (some fields only) | BANNED without justification |
| 2 | Type/structure only (`isinstance`) | BANNED |
| 1 | Existence (`is not None`) | BANNED |

### Collection Output

| Level | Name | Status |
|-------|------|--------|
| 5 | Full equality (`assert items == [expected1, expected2]`) | GOLD |
| 4 | Content verification (specific items present + content verified) | PREFERRED |
| 3 | Count + name-only (`len == 3` + name in items) | BANNED |
| 2 | Count only | BANNED |
| 1 | Non-empty | BANNED |

## The Bare Substring Problem

`assert "X" in output` is always a mirage because:

- X could appear in a comment, different section, error message, or anywhere
- Proves X exists SOMEWHERE but not WHERE
- A writer emitting fields outside their struct block passes the check
- A formatter dumping all content into a single line passes the check
- An error handler including the keyword in its message passes the check

**The only valid use of substring checks** is when combined with structural containment: verify the position of X within the correct block (by index range, line number, or parsing).

```python
# BANNED: bare substring
assert "data" in output

# ACCEPTABLE (Level 3): substring + structural containment with justification
lines = output.splitlines()
struct_start = next(i for i, l in enumerate(lines) if "struct Foo" in l)
struct_end = next(i for i, l in enumerate(lines) if l.strip() == "}" and i > struct_start)
struct_body = "\n".join(lines[struct_start:struct_end + 1])
assert "int data;" in struct_body  # field must be inside struct block

# PREFERRED (Level 4): parse and assert on structure
parsed = parse_c_header(output)
foo_struct = parsed.structs["Foo"]
assert "data" in foo_struct.fields
assert foo_struct.fields["data"].type == "int"

# GOLD (Level 5): exact match
assert output == expected_output
```

## The Broken Implementation Test

Every new assertion must pass this annotation test. Write it as a comment or in your output:

```
MUTATION CHECK: [assertion text]
  FAILS IF: [specific production code mutation]
  PLAUSIBLE? [Yes/No + reasoning]
```

Rules:
- "None" or "nothing" are NOT valid FAILS IF answers
- The mutation must be PLAUSIBLE (a real bug: off-by-one, wrong variable, missing field, swapped arguments, dropped section)
- Adversarial construction ("return the exact expected string minus one character") does not count
- If you cannot fill in FAILS IF with a specific, plausible mutation, the assertion is too weak

### Examples

```
MUTATION CHECK: assert len(result) > 0
  FAILS IF: nothing plausible -- empty result only
  PLAUSIBLE? No. Any garbage non-empty output passes. ASSERTION TOO WEAK.

MUTATION CHECK: assert result == {"status": "ok", "count": 3, "items": ["a", "b", "c"]}
  FAILS IF: count field returns 2 instead of 3, or items list is missing "c"
  PLAUSIBLE? Yes. Off-by-one in count, dropped item in iteration. ASSERTION VALID.

MUTATION CHECK: assert "data" in output
  FAILS IF: "data" not present at all
  PLAUSIBLE? No. Only catches complete omission. "data" in a comment or error
  message passes. Field in wrong struct passes. ASSERTION TOO WEAK.

MUTATION CHECK: assert foo_struct.fields["data"].type == "int"
  FAILS IF: type resolver returns "unsigned int" or "char" instead of "int"
  PLAUSIBLE? Yes. Wrong type mapping in resolver. ASSERTION VALID.
```

## Justification Requirements

Using levels below PREFERRED requires an inline comment explaining why:

| Reason | Valid? | Required Mitigation |
|--------|--------|---------------------|
| Non-deterministic output (timestamps, UUIDs) | Yes | Use matchers for non-deterministic fields, exact match for everything else |
| Platform-dependent output (line endings, paths) | Yes | Use highest cross-platform level; normalize before comparing |
| Output too large for exact match | Sometimes | Parse and assert on structure (Level 4); justify why parsing is impossible if using Level 3 |
| "It's just a quick test" | Never | No such thing as a quick test. Tests outlive the code they test. |
| "The important thing is that it contains X" | Never | WHERE it contains X matters. Use structural containment at minimum. |

## Usage Reference

```markdown
Load assertion quality standard (patterns/assertion-quality-standard.md).
Classify each assertion on the Assertion Strength Ladder.
```
