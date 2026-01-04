# Factchecker Report Template

Use this template structure when generating reports.

---

## Report Header

```markdown
# Factchecker Report

**Generated:** {{timestamp}}
**Scope:** {{scope_description}}
**Claims Found:** {{total_claims}}
**Verified:** {{verified_count}} | **Refuted:** {{refuted_count}} | **Inconclusive:** {{inconclusive_count}} | **Other:** {{other_count}}

---
```

### Scope Description Formats

- Branch: `Branch {{branch_name}} ({{commit_count}} commits since {{base_branch}})`
- Uncommitted: `Uncommitted changes ({{staged_count}} staged, {{unstaged_count}} unstaged files)`
- Full repo: `Full repository ({{file_count}} files scanned)`

---

## Summary Section

```markdown
## Summary

| Verdict | Count | Action Required |
|---------|-------|-----------------|
| ✅ Verified | {{verified_count}} | None |
| ❌ Refuted | {{refuted_count}} | Fix comments or code |
| ❓ Inconclusive | {{inconclusive_count}} | Manual review needed |
| ⚠️ Ambiguous | {{ambiguous_count}} | Clarify wording |
| ⚠️ Misleading | {{misleading_count}} | Rewrite for accuracy |
| 📚 Jargon-heavy | {{jargon_count}} | Simplify language |
| 🕐 Stale | {{stale_count}} | Update or remove |

### Key Findings

{{#if has_security_issues}}
- **Security:** {{security_issue_count}} claims need attention
{{/if}}
{{#if has_refuted}}
- **Accuracy:** {{refuted_count}} claims are factually incorrect
{{/if}}
{{#if has_stale}}
- **Maintenance:** {{stale_count}} outdated references found
{{/if}}

---
```

---

## Missing Context & Completeness

If missing facts mode was enabled, include this section after Summary:

### High Severity

For each INCOMPLETE verdict with high severity:

```markdown
#### [Title of incomplete item]
**Location:** `[file]:[line]`
**Type:** Context Gap | Completeness Gap
**Issue:** [Brief description of what's missing]

**Missing Elements:**
- [Element 1]
- [Element 2]

**Suggested Addition:**
```[language]
[Suggested content to add]
```
```

### Medium/Low Severity

Same format, grouped by severity.

---

## Extraneous Content

If extraneous info mode was enabled, include this section:

### Code-Restating Comments

For each EXTRANEOUS verdict with type code_restate:

```markdown
#### [file]:[line]
```[language]
[The extraneous comment]
[Adjacent code it describes]
```

**Reason:** [Why it's extraneous]
**Suggestion:** Remove (operation is self-evident)
```

### LLM Patterns

For each EXTRANEOUS verdict with type llm_pattern:

Same format as above.

### Verbose Explanations

For each EXTRANEOUS verdict with type verbose:

```markdown
#### [file]:[lines]
**Content:** [First 100 chars of verbose text]...
**Repetition Score:** [N]%
**Suggestion:** Simplify to:
```
[Simplified version]
```
```

---

## Findings Section

Organize by category, then by verdict (refuted first, then inconclusive, then verified).

```markdown
## Findings by Category

### {{category_name}} ({{category_claim_count}} claims)

#### ❌ REFUTED: "{{claim_text}}"
- **Location:** `{{file}}:{{line}}`
- **Claim:** `{{original_comment}}`
- **Evidence:** {{evidence_description}}
- **Depth:** {{depth_used}}
- **Correction:** {{suggested_fix}}
- **Sources:** {{source_references}}

#### ❓ INCONCLUSIVE: "{{claim_text}}"
- **Location:** `{{file}}:{{line}}`
- **Claim:** `{{original_comment}}`
- **Attempted:** {{verification_attempts}}
- **Blockers:** {{why_inconclusive}}
- **Recommendation:** {{next_steps}}
- **Sources:** {{source_references}}

#### ✅ VERIFIED: "{{claim_text}}"
- **Location:** `{{file}}:{{line}}`
- **Evidence:** {{evidence_description}}
- **Depth:** {{depth_used}}
- **Sources:** {{source_references}}

---
```

### Category Order

1. Security
2. Correctness
3. Performance
4. Concurrency
5. Configuration
6. Documentation
7. Historical

### Within Category Order

1. Refuted (highest priority)
2. Misleading
3. Inconclusive
4. Ambiguous
5. Jargon-heavy
6. Stale
7. Verified (lowest priority - no action needed)

---

## Bibliography Section

```markdown
## Bibliography

{{#each sources}}
[{{index}}] {{formatted_citation}}
{{/each}}

---
```

### Citation Formats by Type

**Code trace:**
```
[1] Code trace: src/auth/password.ts:34-60 - bcryptjs.hash() call with cost factor 12
```

**Test execution:**
```
[2] Test: npm test -- --grep "password hashing" - 5/5 passing, verified bcrypt usage
```

**Web source:**
```
[3] OWASP Password Storage Cheat Sheet - https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html - "Use bcrypt, scrypt, Argon2id, or PBKDF2"
```

**Git history:**
```
[4] Git: Issue #142 (closed 2024-01-15) - Bug fixed in v2.3.0, workaround no longer needed
```

**Documentation:**
```
[5] Docs: Node.js crypto module - randomBytes() - https://nodejs.org/api/crypto.html#cryptorandombytessize-callback
```

**Benchmark:**
```
[6] Benchmark: Binary search on 10,000 elements - avg 0.003ms, confirms O(log n)
```

**Paper/RFC:**
```
[7] RFC 5322 Section 3.4.1 - Email address format specification - https://tools.ietf.org/html/rfc5322#section-3.4.1
```

**Runtime inspection:**
```
[8] Runtime: Environment variable AUTH_SECRET read at startup, controls JWT signing key
```

---

## Implementation Plan Section

```markdown
## Implementation Plan

### High Priority (Refuted Claims)

These claims are factually incorrect and should be fixed immediately.

{{#each refuted_claims}}
{{index}}. [ ] `{{file}}:{{line}}` - {{description}}
   - **Current:** {{current_text}}
   - **Issue:** {{what_is_wrong}}
   - **Suggested fix:** {{suggested_fix}}
{{/each}}

### Medium Priority (Misleading/Stale)

These claims may confuse readers or reference outdated information.

{{#each misleading_stale_claims}}
{{index}}. [ ] `{{file}}:{{line}}` - {{description}}
   - **Issue:** {{what_is_wrong}}
   - **Suggested fix:** {{suggested_fix}}
{{/each}}

### Low Priority (Ambiguous/Jargon)

These claims could be improved for clarity.

{{#each ambiguous_jargon_claims}}
{{index}}. [ ] `{{file}}:{{line}}` - {{description}}
   - **Issue:** {{what_is_wrong}}
   - **Suggested improvement:** {{suggested_fix}}
{{/each}}

### Requires Manual Review

These claims could not be verified automatically.

{{#each inconclusive_claims}}
{{index}}. [ ] `{{file}}:{{line}}` - {{description}}
   - **Attempted:** {{what_was_tried}}
   - **Blocked by:** {{why_blocked}}
   - **Recommendation:** {{next_steps}}
{{/each}}

---
```

---

## Clarity Mode Output

If clarity mode was enabled, include this section after all findings:

```markdown
## Clarity Mode Output

Generated glossary and key facts for AI configuration files.

**Updated Files:**
- [File 1]
- [File 2]

**Glossary Entries:** [N]
**Key Facts:** [M]

See updated AI config files for details.
```

---

## Appendix (Optional)

For detailed reports, include:

```markdown
## Appendix

### A. Verification Methodology

This report was generated using the factchecker skill with the following configuration:
- Scope: {{scope}}
- Agents: {{agents_used}}
- Verification depths: {{depth_breakdown}}
- Time elapsed: {{total_time}}

### B. Files Analyzed

{{#each files}}
- `{{path}}` ({{claim_count}} claims)
{{/each}}

### C. Agent Performance

| Agent | Claims | Verified | Refuted | Time |
|-------|--------|----------|---------|------|
{{#each agents}}
| {{name}} | {{claims}} | {{verified}} | {{refuted}} | {{time}} |
{{/each}}

### D. Raw Claim Data

<details>
<summary>Click to expand raw claim data (JSON)</summary>

```json
{{claims_json}}
```

</details>
```

---

## Verdicts Reference

Use these consistently throughout the report:

| Verdict | Emoji | Meaning |
|---------|-------|---------|
| Verified | ✅ | Claim is accurate, supported by evidence |
| Refuted | ❌ | Claim is false, contradicted by evidence |
| Inconclusive | ❓ | Cannot determine, needs manual review |
| Ambiguous | ⚠️ | Wording unclear, multiple interpretations |
| Misleading | ⚠️ | Technically true but implies falsehood |
| Jargon-heavy | 📚 | Too technical for intended audience |
| Stale | 🕐 | Was true, no longer applies |

---

## Example Complete Report

```markdown
# Factchecker Report

**Generated:** 2025-12-21T15:30:00Z
**Scope:** Branch feature/auth-refactor (12 commits since main)
**Claims Found:** 8
**Verified:** 5 | **Refuted:** 1 | **Inconclusive:** 1 | **Other:** 1

---

## Summary

| Verdict | Count | Action Required |
|---------|-------|-----------------|
| ✅ Verified | 5 | None |
| ❌ Refuted | 1 | Fix comments or code |
| ❓ Inconclusive | 1 | Manual review needed |
| 🕐 Stale | 1 | Update or remove |

### Key Findings

- **Accuracy:** 1 claim is factually incorrect
- **Maintenance:** 1 outdated reference found

---

## Findings by Category

### Security (2 claims)

#### ✅ VERIFIED: "passwords hashed with bcrypt"
- **Location:** `src/auth/password.ts:34`
- **Evidence:** Code confirms bcryptjs.hash() with cost factor 12
- **Depth:** Medium
- **Sources:** [1], [2]

#### ❌ REFUTED: "session tokens cryptographically random"
- **Location:** `src/auth/session.ts:78`
- **Claim:** `// Generate cryptographically random session token`
- **Evidence:** Uses Math.random().toString(36) - NOT cryptographically secure
- **Depth:** Medium
- **Correction:** Use crypto.randomBytes() or uuid v4
- **Sources:** [3], [4]

### Historical (1 claim)

#### 🕐 STALE: "TODO: remove after #142 resolved"
- **Location:** `src/utils/legacy.ts:15`
- **Claim:** `// TODO: remove this workaround after issue #142 is resolved`
- **Evidence:** Issue #142 closed on 2024-01-15, workaround still present
- **Depth:** Shallow
- **Correction:** Remove workaround code, issue has been resolved for 11 months
- **Sources:** [5]

---

## Bibliography

[1] Code trace: src/auth/password.ts:34-60 - bcryptjs.hash() with cost factor 12
[2] OWASP Password Storage Cheat Sheet - https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html - "bcrypt with cost 10+ recommended"
[3] Code trace: src/auth/session.ts:78-85 - Math.random().toString(36) usage
[4] MDN Math.random() - https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Math/random - "does not provide cryptographically secure random numbers"
[5] Git: Issue #142 (closed 2024-01-15) - https://github.com/example/repo/issues/142

---

## Implementation Plan

### High Priority (Refuted Claims)

1. [ ] `src/auth/session.ts:78` - Session token generation not cryptographically secure
   - **Current:** `Math.random().toString(36).substring(2)`
   - **Issue:** Math.random() is predictable, not suitable for security
   - **Suggested fix:** Replace with `crypto.randomBytes(32).toString('hex')`

### Medium Priority (Stale)

2. [ ] `src/utils/legacy.ts:15` - Workaround for resolved issue still present
   - **Issue:** Issue #142 resolved 11 months ago
   - **Suggested fix:** Remove workaround code and TODO comment

---
```
