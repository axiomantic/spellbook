# Code Review Taxonomy

<ROLE>Code Review Authority. Apply these definitions consistently across every review. Misclassifying severity misleads authors and degrades engineering standards.</ROLE>

## Severity Levels

<CRITICAL>
Severity names are **UPPERCASE tokens**, not prose. This file is the definition;
no code declares the vocabulary. The consumers that gate merges (`SEVERITY_ORDER`
and `determine_verdict` in `/advanced-code-review-report`) match on the exact
token, and nothing validates a token you invent. Emitting
`Critical` in Title Case matched no branch of the old gate and fell through to
APPROVE — a blocking finding merged under "No blocking issues found."

The vocabulary is exactly these seven tokens. There is no eighth.
</CRITICAL>

| Severity | Definition | Action Required |
|----------|------------|-----------------|
| `CRITICAL` | Security vulnerabilities, data loss, production outage | MUST fix before merge |
| `HIGH` | **Bugs and broken functionality**, broken contracts, architecture problems, missing required features, poor error handling | MUST fix before merge (blocking) |
| `MEDIUM` | Code quality issues, minor test gaps, maintainability concerns | FIX or justify deferral in response |
| `LOW` | Minor improvements, edge case optimizations, nice-to-haves | OPTIONAL - fix if easy |
| `NIT` | Style, naming, formatting preferences | OPTIONAL - use GitHub suggestion blocks |
| `QUESTION` | Needs author input before a judgment can be made | Author answers before merge |
| `PRAISE` | Good patterns, clever solutions, exemplary code to acknowledge | NO action required |

<CRITICAL>
**Bugs are HIGH, never CRITICAL.** `CRITICAL` is reserved for security
vulnerabilities, data loss, and production outages. A crash or an off-by-one is
a bug: it is `HIGH`. Both are blocking, so nothing merges that should not — but
the distinction keeps `CRITICAL` meaningful.

`IMPORTANT`, `MINOR`, and `SUGGESTION` are **RETIRED**. Do not emit them.
</CRITICAL>

### Severity Decision Tree

<CRITICAL>
Use this decision tree for every finding. Do not skip levels or guess severity from context alone.
</CRITICAL>

```
Is it a security vulnerability, data loss risk, or production outage?
  → Yes: CRITICAL
  → No: Continue

Is it a BUG, or does it break contracts, architecture, or core functionality?
  → Yes: HIGH        (bugs land HERE, not in CRITICAL)
  → No: Continue

Is it a code quality or maintainability concern?
  → Yes: MEDIUM
  → No: Continue

Is it a minor improvement or optimization?
  → Yes: LOW
  → No: Continue

Is it purely stylistic?
  → Yes: NIT
  → No: Continue

Do you need the author to answer something before you can judge it?
  → Yes: QUESTION
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
| **APPROVED** | Ready to merge | No `CRITICAL`/`HIGH` issues remain; all items addressed or justified |
| **CHANGES_REQUESTED** | Must fix before merge | Any `CRITICAL` or `HIGH` finding, **or any severity the gate does not recognise** |
| **COMMENTED** | Non-blocking feedback | Review complete with only `MEDIUM`/`LOW`/`NIT`/`QUESTION` items |
| **PENDING** | Review in progress | Partial review, more files to examine |
| **RE_REVIEW_REQUIRED** | Substantial changes since last review | Author pushed significant changes that invalidate previous review |

### Approval Decision Matrix

| Remaining Issues | Approval State |
|------------------|----------------|
| Any `CRITICAL` | CHANGES_REQUESTED |
| Any `HIGH` (no `CRITICAL`) | CHANGES_REQUESTED |
| Any severity outside the seven tokens | CHANGES_REQUESTED (**fail closed** — the gate cannot rank it, so it must not assume harmless) |
| Only `MEDIUM`/`LOW`/`NIT`/`QUESTION` | COMMENTED or APPROVED (reviewer discretion) |
| Only `PRAISE` | APPROVED |
| None | APPROVED |

## Comment Format

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

**[HIGH/Logic]** Off-by-one drops the last element of the batch

`range(0, len(items) - 1)` never yields the final index. This is a BUG, so it is
HIGH — not CRITICAL.

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

<FINAL_EMPHASIS>This taxonomy is the authoritative reference for all code review classification. Severity determines merge gates, and the gate matches the UPPERCASE token exactly. Inconsistent application erodes trust and lets real defects through. When uncertain, classify higher and note the ambiguity in the comment.</FINAL_EMPHASIS>
