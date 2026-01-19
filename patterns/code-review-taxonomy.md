# Code Review Taxonomy

Shared definitions for code review severity, categories, and approval states.

## Severity Levels

| Severity | Definition | Action Required |
|----------|------------|-----------------|
| **Critical** | Bugs, security vulnerabilities, data loss risks, crashes | MUST fix before merge |
| **High** | Architecture problems, missing required features, poor error handling, broken contracts | SHOULD fix before merge |
| **Medium** | Code quality issues, minor test gaps, maintainability concerns | FIX or justify deferral in response |
| **Low** | Minor improvements, edge case optimizations, nice-to-haves | OPTIONAL - fix if easy |
| **Nit** | Style, naming, formatting preferences | OPTIONAL - use GitHub suggestion blocks |
| **Praise** | Good patterns, clever solutions, exemplary code to acknowledge | NO action required |

### Severity Decision Tree

```
Is it a security issue, bug, or data loss risk?
  → Yes: CRITICAL
  → No: Continue

Does it break contracts, architecture, or core functionality?
  → Yes: HIGH
  → No: Continue

Is it a code quality or maintainability concern?
  → Yes: MEDIUM
  → No: Continue

Is it a minor improvement or optimization?
  → Yes: LOW
  → No: Continue

Is it purely stylistic?
  → Yes: NIT
  → No: PRAISE (if positive) or skip comment
```

## Category Types

| Category | Scope | Examples |
|----------|-------|----------|
| **Security** | Auth, injection, secrets, permissions | Exposed credentials, SQL injection, missing auth checks, overly permissive CORS |
| **Logic** | Bugs, edge cases, incorrect behavior | Off-by-one errors, null pointer exceptions, race conditions, incorrect conditionals |
| **Error** | Missing handling, silent failures, wrong types | Uncaught exceptions, swallowed errors, generic catch blocks, incorrect error propagation |
| **Type** | Type safety, inference issues, type escape hatches | `any` usage, incorrect type assertions, missing generics, unsafe casts |
| **Test** | Coverage gaps, weak assertions, anti-patterns | Missing edge case tests, `toBeTruthy()` on objects, mocked-out logic, flaky tests |
| **Perf** | Performance issues, unnecessary computation | N+1 queries, missing memoization, blocking I/O in async context, memory leaks |
| **Style** | Formatting, naming, code organization | Inconsistent naming, long functions, poor file structure, missing comments |
| **Doc** | Missing or incorrect documentation | Missing JSDoc, outdated README, incorrect API docs, missing type annotations |

## Approval States

| State | Meaning | When to Use |
|-------|---------|-------------|
| **APPROVED** | Ready to merge | No Critical/High issues remain; all items addressed or justified |
| **CHANGES_REQUESTED** | Must fix before merge | Critical or High severity issues present |
| **COMMENTED** | Non-blocking feedback | Review complete with only Medium/Low/Nit items |
| **PENDING** | Review in progress | Partial review, more files to examine |
| **RE_REVIEW_REQUIRED** | Substantial changes since last review | Author pushed significant changes that invalidate previous review |

### Approval Decision Matrix

| Remaining Issues | Approval State |
|------------------|----------------|
| Any Critical | CHANGES_REQUESTED |
| Any High (no Critical) | CHANGES_REQUESTED |
| Only Medium/Low/Nit | COMMENTED or APPROVED (reviewer discretion) |
| Only Praise | APPROVED |
| None | APPROVED |

## Comment Format

When using these categories in reviews:

```markdown
**[SEVERITY/CATEGORY]** Brief description

Detailed explanation if needed.

<!-- For nits, use GitHub suggestion blocks: -->
```suggestion
improved code here
```
```

### Examples

```markdown
**[CRITICAL/Security]** API key exposed in client-side code

This key will be visible in the browser. Move to server-side environment variable.

---

**[HIGH/Error]** Missing error handling for network failure

If fetch fails, the promise rejection is unhandled. Wrap in try-catch or add .catch().

---

**[MEDIUM/Test]** Test doesn't verify error message

The test checks that an error is thrown but not what error. Add assertion on error.message.

---

**[NIT/Style]** Consider more descriptive variable name

```suggestion
const userAuthenticationToken = response.token;
```

---

**[PRAISE]** Excellent use of discriminated unions here - makes the state machine crystal clear.
```
