# Assertion Quality Standard

## Invariant Principles

1. **Deterministic output demands exact equality.** If a function produces the same output for the same input, the test MUST assert `result == expected_complete_output`. No substring checks. No partial matches. No exceptions. (See: The Deterministic Output Principle below.)
2. **Assertions must catch garbage.** If broken production code still passes the test, the assertion is worthless.
3. **Position matters, not just presence.** Proving X exists SOMEWHERE is not proving X is WHERE it should be.
4. **Stronger is always better.** Downgrade from exact match only with written justification.
5. **Every assertion must name its kill.** If you cannot name a specific mutation the assertion catches, it catches nothing.

## The Deterministic Output Principle

<CRITICAL>
When testing a function with deterministic output (same input always produces same output), you MUST assert exact equality against the COMPLETE expected output. Always. No exceptions.

```python
# CORRECT: exact equality on complete output
assert result == "the entire expected string, every character"

# WRONG: partial assertion. Extra garbage, missing declarations,
# wrong ordering, malformed syntax all slip through undetected.
assert "some substring" in result

# WRONG: meaningless
assert len(result) > 0

# WRONG: still partial. Doesn't verify structure, ordering,
# completeness, or absence of unexpected content.
assert "foo" in result and "bar" in result
```

**Deterministic functions include:** writers, serializers, formatters, code generators, template renderers, config builders, query builders, and any function where the same input always produces the same output.

**There is never a reason to use partial assertions on deterministic output.** The fact that the output is long does not justify partial assertions. Use triple-quoted strings, dedent helpers, or computed expected values for multi-line output.

**The ONLY exception** is when output contains genuinely non-deterministic elements (timestamps, random IDs, memory addresses, PIDs). In that case: normalize or strip the non-deterministic parts first, THEN assert exact equality on the rest. Document which parts are non-deterministic and why.

```python
# CORRECT: non-deterministic element handled, then exact equality
result = generate_report(data)
# Normalize timestamp (non-deterministic) before comparing
normalized = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', 'TIMESTAMP', result)
assert normalized == expected_output_with_timestamp_placeholder

# WRONG: using "in" because output has a timestamp somewhere
assert "report title" in result  # Ignores everything else!
```

This principle is the FOUNDATION of assertion quality. Every other rule in this document supports it. If you remember nothing else, remember: deterministic output demands exact equality.
</CRITICAL>

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
| "Output is too long for exact match" | Never | Use triple-quoted strings or dedent helpers. Length is not a justification for partial assertions. |
| "I'll just check the key parts" | Never | Deterministic output demands complete verification. Partial checks miss structural errors, ordering bugs, and extra garbage. |

## Usage Reference

```markdown
Read assertion quality standard (patterns/assertion-quality-standard.md) in full.
Classify each assertion on the Assertion Strength Ladder.
```
