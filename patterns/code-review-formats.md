# Code Review Formats

Structured data formats for machine-readable and human-readable code review output.

**Reference:** See [code-review-taxonomy.md](code-review-taxonomy.md) for severity levels, categories, and approval states.

---

## Finding Schema

Individual review finding with complete context for tooling and traceability.

```json
{
  "id": "string (unique identifier, e.g., 'F001')",
  "severity": "Critical | High | Medium | Low | Nit | Praise",
  "category": "Security | Logic | Error | Type | Test | Perf | Style | Doc",
  "location": {
    "file": "string (relative path from repo root)",
    "line_start": "number (1-indexed)",
    "line_end": "number (optional, for multi-line ranges)",
    "side": "LEFT | RIGHT (LEFT=base/before, RIGHT=head/after)"
  },
  "summary": "string (one-line description, max 80 chars)",
  "reason": "string (WHY this matters - required for Critical/High)",
  "evidence": "string (code snippet or observation supporting the finding)",
  "suggestion": "string (proposed fix code, optional but encouraged)"
}
```

### Field Requirements

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Sequential within review: F001, F002, ... |
| `severity` | Yes | Must match taxonomy values exactly |
| `category` | Yes | Must match taxonomy values exactly |
| `location.file` | Yes | Relative path, forward slashes |
| `location.line_start` | Yes | First line of the issue |
| `location.line_end` | No | Last line if multi-line; omit for single line |
| `location.side` | No | Default RIGHT; use LEFT for removed code |
| `summary` | Yes | One-line, actionable |
| `reason` | Critical/High: Yes | Explain impact; may omit for obvious issues |
| `evidence` | Yes | Code snippet or clear observation |
| `suggestion` | No | Encouraged for anything fixable |

### Example Finding

```json
{
  "id": "F003",
  "severity": "High",
  "category": "Error",
  "location": {
    "file": "src/api/client.ts",
    "line_start": 42,
    "line_end": 45,
    "side": "RIGHT"
  },
  "summary": "Unhandled promise rejection in fetch call",
  "reason": "Network failures will crash the application instead of showing user-friendly error",
  "evidence": "const data = await fetch(url).then(r => r.json());",
  "suggestion": "try {\n  const data = await fetch(url).then(r => r.json());\n} catch (error) {\n  throw new NetworkError('Failed to fetch data', { cause: error });\n}"
}
```

---

## Review Summary Schema

Complete review output including all findings and verdict.

```json
{
  "reviewed_sha": "string (40-char commit SHA that was reviewed)",
  "base_sha": "string (40-char merge base SHA)",
  "files_reviewed": ["array of relative file paths"],
  "findings": ["array of Finding objects"],
  "verdict": "APPROVED | CHANGES_REQUESTED | COMMENTED",
  "blocking_count": {
    "critical": "number",
    "high": "number"
  },
  "re_review_required": "boolean",
  "reviewer_notes": "string (optional summary or context)"
}
```

### Field Requirements

| Field | Required | Notes |
|-------|----------|-------|
| `reviewed_sha` | Yes | Exact commit reviewed; enables re-review detection |
| `base_sha` | Yes | Merge base for diff context |
| `files_reviewed` | Yes | Empty array if no files reviewed |
| `findings` | Yes | Empty array if no findings |
| `verdict` | Yes | Must follow approval decision matrix from taxonomy |
| `blocking_count` | Yes | Both fields required, can be 0 |
| `re_review_required` | Yes | True if substantial changes since last review |
| `reviewer_notes` | No | High-level summary for complex reviews |

### Verdict Logic

```
IF blocking_count.critical > 0 OR blocking_count.high > 0:
  verdict = "CHANGES_REQUESTED"
ELSE IF findings contains only Praise:
  verdict = "APPROVED"
ELSE IF findings.length == 0:
  verdict = "APPROVED"
ELSE:
  verdict = "COMMENTED" (reviewer may upgrade to "APPROVED")
```

### Example Review Summary

```json
{
  "reviewed_sha": "a1b2c3d4e5f6789012345678901234567890abcd",
  "base_sha": "fedcba0987654321098765432109876543210fed",
  "files_reviewed": [
    "src/api/client.ts",
    "src/api/types.ts",
    "tests/api/client.test.ts"
  ],
  "findings": [
    {
      "id": "F001",
      "severity": "High",
      "category": "Error",
      "location": { "file": "src/api/client.ts", "line_start": 42, "side": "RIGHT" },
      "summary": "Unhandled promise rejection",
      "reason": "Network failures crash the app",
      "evidence": "await fetch(url).then(r => r.json())"
    },
    {
      "id": "F002",
      "severity": "Medium",
      "category": "Test",
      "location": { "file": "tests/api/client.test.ts", "line_start": 15, "side": "RIGHT" },
      "summary": "Missing test for error case",
      "evidence": "Only tests happy path"
    },
    {
      "id": "F003",
      "severity": "Praise",
      "category": "Style",
      "location": { "file": "src/api/types.ts", "line_start": 1, "side": "RIGHT" },
      "summary": "Excellent use of discriminated unions",
      "evidence": "type Result = Success | Failure"
    }
  ],
  "verdict": "CHANGES_REQUESTED",
  "blocking_count": {
    "critical": 0,
    "high": 1
  },
  "re_review_required": false,
  "reviewer_notes": "Good progress on the API client. Address the error handling before merge."
}
```

---

## Markdown Output Format

Human-readable format that maps 1:1 with the JSON schema.

### Template

```markdown
# Code Review: [PR Title or Branch Name]

**Reviewed SHA:** `{reviewed_sha}`
**Base SHA:** `{base_sha}`
**Verdict:** {verdict}
**Blocking Issues:** {blocking_count.critical} Critical, {blocking_count.high} High

---

## Files Reviewed

- `{file_1}`
- `{file_2}`
- ...

---

## Findings

### {id}: [{severity}/{category}] {summary}

**File:** `{location.file}:{location.line_start}`{-line_end if present}

{reason if present}

**Evidence:**
```{language}
{evidence}
```

{if suggestion present}
**Suggested Fix:**
```{language}
{suggestion}
```
{endif}

---

## Reviewer Notes

{reviewer_notes if present, otherwise omit section}
```

### Example Markdown Output

```markdown
# Code Review: Add API Client Retry Logic

**Reviewed SHA:** `a1b2c3d4e5f6789012345678901234567890abcd`
**Base SHA:** `fedcba0987654321098765432109876543210fed`
**Verdict:** CHANGES_REQUESTED
**Blocking Issues:** 0 Critical, 1 High

---

## Files Reviewed

- `src/api/client.ts`
- `src/api/types.ts`
- `tests/api/client.test.ts`

---

## Findings

### F001: [High/Error] Unhandled promise rejection

**File:** `src/api/client.ts:42`

Network failures crash the app

**Evidence:**
```typescript
await fetch(url).then(r => r.json())
```

**Suggested Fix:**
```typescript
try {
  const data = await fetch(url).then(r => r.json());
} catch (error) {
  throw new NetworkError('Failed to fetch data', { cause: error });
}
```

---

### F002: [Medium/Test] Missing test for error case

**File:** `tests/api/client.test.ts:15`

**Evidence:**
```typescript
Only tests happy path
```

---

### F003: [Praise/Style] Excellent use of discriminated unions

**File:** `src/api/types.ts:1`

**Evidence:**
```typescript
type Result = Success | Failure
```

---

## Reviewer Notes

Good progress on the API client. Address the error handling before merge.
```

---

## Parsing Notes

### JSON to Markdown

Tools should use this mapping:
- `severity` + `category` -> `[{severity}/{category}]` header
- `location` -> `File:` line with optional range
- `reason` -> paragraph after file line (omit if empty)
- `evidence` -> fenced code block with language detection
- `suggestion` -> "Suggested Fix:" section (omit if empty)

### Markdown to JSON

When parsing markdown reviews back to JSON:
1. Extract SHA values from header
2. Parse file list from "Files Reviewed" section
3. Split findings by `### F###:` pattern
4. Extract severity/category from bracket notation
5. Parse location from "File:" line (handle optional line ranges)
