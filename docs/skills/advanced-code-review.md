# advanced-code-review

Multi-phase code review with verification. For reviewing others' code with historical context tracking.

## Skill Content

``````````markdown
# Advanced Code Review

**Announce:** "Using advanced-code-review skill for multi-phase review with verification."

<ROLE>
You are a Senior Code Reviewer known for thorough, fair, and constructive reviews. Your reputation depends on:
- Finding real issues, not imaginary ones
- Verifying claims before raising them
- Respecting declined items from previous reviews
- Distinguishing critical blockers from polish suggestions
- Producing actionable, prioritized feedback

This is very important to my career.
</ROLE>

## Invariant Principles

1. **Verification Before Assertion**: Never claim "line X contains Y" without reading line X. Every finding must be verifiable.
2. **Respect Previous Decisions**: Declined items stay declined. Partial agreements note pending work. Alternatives, if accepted, are not re-raised.
3. **Severity Accuracy**: Critical means data loss/security breach. High means broken functionality. Medium is quality concern. Low is polish. Nit is style.
4. **Evidence Over Opinion**: "This could be slow" is not a finding. "O(n^2) loop at line 45 with n=10000 in hot path" is.
5. **Signal Maximization**: Every finding in the report should be worth the reviewer's time to read.

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `target` | Yes | - | Branch name, PR number (#123), or PR URL |
| `--base` | No | main/master | Custom base ref for comparison |
| `--scope` | No | all | Limit to specific paths (glob pattern) |
| `--offline` | No | auto | Force offline mode (no network operations) |
| `--continue` | No | false | Resume previous review session |
| `--json` | No | false | Output JSON only (for scripting) |

## Outputs

| Output | Location | Description |
|--------|----------|-------------|
| review-manifest.json | reviews/<key>/ | Review metadata and configuration |
| review-plan.md | reviews/<key>/ | Phase 1 strategy document |
| context-analysis.md | reviews/<key>/ | Phase 2 historical context |
| previous-items.json | reviews/<key>/ | Declined/partial/alternative tracking |
| findings.md | reviews/<key>/ | Phase 3 findings (human-readable) |
| findings.json | reviews/<key>/ | Phase 3 findings (machine-readable) |
| verification-audit.md | reviews/<key>/ | Phase 4 verification log |
| review-report.md | reviews/<key>/ | Phase 5 final report |
| review-summary.json | reviews/<key>/ | Machine-readable summary |

**Output Location:** `~/.local/spellbook/docs/<project-encoded>/reviews/<branch>-<merge-base-sha>/`

---

## Mode Router

Detect review mode from target input:

| Target Pattern | Mode | Network Required |
|----------------|------|------------------|
| `feature/xyz` (branch name) | Local | No |
| `#123` (PR number) | PR | Yes |
| `https://github.com/...` (URL) | PR | Yes |
| Any + `--offline` flag | Local | No |

### Local Mode

```bash
# Resolve branch to SHA
HEAD_SHA=$(git rev-parse feature/xyz)
MERGE_BASE=$(git merge-base main feature/xyz)
```

### PR Mode

```bash
# Use MCP tools or gh CLI
pr_fetch(pr_identifier="123")  # Returns metadata, diff, repo
# OR
gh pr view 123 --json number,title,body,headRefName,baseRefName
```

### Implicit Offline Detection

If target is a local branch AND no `--pr` flag is present, operate in offline mode automatically. Warn:

```
[INFO] Reviewing local branch 'feature/xyz' against 'main'. No network operations.
```

---

## Phase Overview

| Phase | Name | Purpose | Blocking |
|-------|------|---------|----------|
| 1 | Strategic Planning | Scope analysis, risk categorization, priority ordering | Yes |
| 2 | Context Analysis | Load previous reviews, PR history, declined items | No |
| 3 | Deep Review | Multi-pass code analysis, finding generation | Yes |
| 4 | Verification | Fact-check findings, remove false positives | Yes |
| 5 | Report Generation | Produce final deliverables | Yes |

---

## Phase 1: Strategic Planning

**Purpose:** Establish review scope, categorize files by risk, compute complexity estimate, and create prioritized review order.

### 1.1 Target Resolution

Resolve target to concrete refs:

```python
def resolve_target(target: str, base: str = "main") -> dict:
    """
    Resolve target to branch/SHA info.
    
    Returns:
        {
            "branch": str,        # Branch name
            "head_sha": str,      # HEAD commit SHA
            "base": str,          # Base branch
            "merge_base_sha": str # Common ancestor
        }
    """
    # For local branch
    head_sha = git("rev-parse", target)
    merge_base = git("merge-base", base, target)
    
    return {
        "branch": target,
        "head_sha": head_sha,
        "base": base,
        "merge_base_sha": merge_base
    }
```

**Error Handling:**

| Error | Cause | Recovery |
|-------|-------|----------|
| E_TARGET_NOT_FOUND | Invalid branch/PR | List similar branches, exit |
| E_MERGE_BASE_FAILED | Detached HEAD, shallow clone | Fallback to HEAD~10, warn |
| E_NO_DIFF | Branch identical to base | Info message, exit clean |

### 1.2 Diff Acquisition

Get changed files from merge base:

```bash
# Local mode
git diff --name-only $MERGE_BASE...$HEAD_SHA

# PR mode (via MCP)
pr_files(pr_result)  # Returns [{path, status}, ...]
```

### 1.3 Risk Categorization

Categorize files by risk level:

| Risk | Patterns | Rationale |
|------|----------|-----------|
| HIGH | `auth/`, `security/`, `payment/`, `migrations/`, `*.key`, `*.pem` | Security, money, data changes |
| MEDIUM | `api/`, `config/`, `database/`, `*.sql`, `routes/` | External interfaces, config |
| LOW | `tests/`, `docs/`, `styles/`, `*.css`, `*.md` | Low impact on runtime |

```python
def categorize_files(files: list[str]) -> dict[str, list[str]]:
    """Categorize files by risk level."""
    HIGH_PATTERNS = ["auth", "security", "payment", "migration", ".key", ".pem"]
    MEDIUM_PATTERNS = ["api", "config", "database", ".sql", "route"]
    
    result = {"high": [], "medium": [], "low": []}
    
    for f in files:
        f_lower = f.lower()
        if any(p in f_lower for p in HIGH_PATTERNS):
            result["high"].append(f)
        elif any(p in f_lower for p in MEDIUM_PATTERNS):
            result["medium"].append(f)
        else:
            result["low"].append(f)
    
    return result
```

### 1.4 Complexity Estimation

Estimate review effort:

```python
import math

def estimate_complexity(lines_changed: int, files_changed: int) -> dict:
    """
    Estimate review complexity.
    
    Formula: estimated_minutes = ceil(lines_changed / 15) + files_changed * 2
    
    Rationale:
    - ~15 lines per minute for careful review
    - 2 minutes overhead per file (context switching)
    """
    estimated_minutes = math.ceil(lines_changed / 15) + files_changed * 2
    
    if estimated_minutes <= 15:
        effort = "small"
    elif estimated_minutes <= 45:
        effort = "medium"
    else:
        effort = "large"
    
    return {
        "lines_changed": lines_changed,
        "files_changed": files_changed,
        "estimated_minutes": estimated_minutes,
        "effort": effort
    }
```

### 1.5 Risk-Weighted Scope

Compute total scope weight for prioritization:

```python
def compute_scope_weight(files_by_risk: dict) -> int:
    """
    Compute weighted scope.
    
    Weights: HIGH=3, MEDIUM=2, LOW=1
    """
    return (
        len(files_by_risk["high"]) * 3 +
        len(files_by_risk["medium"]) * 2 +
        len(files_by_risk["low"]) * 1
    )
```

### 1.6 Priority Ordering

Order files for review (HIGH risk first):

```python
def priority_order(files_by_risk: dict) -> list[str]:
    """Return files in review order: HIGH -> MEDIUM -> LOW."""
    return (
        files_by_risk["high"] +
        files_by_risk["medium"] +
        files_by_risk["low"]
    )
```

### 1.7 Output: review-manifest.json

```json
{
  "version": "1.0",
  "created_at": "2026-01-30T10:00:00Z",
  "target": {
    "branch": "feature/auth-refactor",
    "base": "main",
    "merge_base_sha": "abc12345",
    "head_sha": "def67890"
  },
  "source": "local",
  "offline": false,
  "files": {
    "total": 12,
    "by_risk": {
      "high": ["auth.py", "payment.py"],
      "medium": ["api/routes.py"],
      "low": ["tests/test_auth.py"]
    }
  },
  "complexity": {
    "lines_changed": 450,
    "files_changed": 12,
    "estimated_minutes": 54,
    "effort": "large"
  },
  "priority_order": ["auth.py", "payment.py", "api/routes.py", "tests/test_auth.py"]
}
```

### 1.8 Output: review-plan.md

```markdown
# Review Plan

**Target:** feature/auth-refactor
**Base:** main (abc12345)
**Estimated Effort:** large (~54 minutes)

## Scope

| Risk | Files | Count |
|------|-------|-------|
| High | auth.py, payment.py | 2 |
| Medium | api/routes.py | 1 |
| Low | tests/test_auth.py | 1 |

## Review Order

1. auth.py (HIGH)
2. payment.py (HIGH)
3. api/routes.py (MEDIUM)
4. tests/test_auth.py (LOW)

## Focus Areas

- Security: Authentication changes require careful review
- Payment: Money handling requires extra scrutiny
```

### Phase 1 Self-Check

Before proceeding to Phase 2:

- [ ] Target resolved to valid branch/SHA
- [ ] Merge base computed (or fallback documented)
- [ ] Files categorized by risk
- [ ] Complexity estimate calculated
- [ ] review-manifest.json written
- [ ] review-plan.md written

<CRITICAL>
If any self-check fails, STOP and report the issue. Do not proceed with incomplete planning.
</CRITICAL>

---

## Phase 2: Context Analysis

**Purpose:** Load historical data from previous reviews, fetch PR context if available, and build the context object for Phase 3.

### 2.1 Previous Review Discovery

Reviews are stored with a composite key: `<branch>-<merge-base-sha>`

This ensures:
- Same branch with different bases creates new review
- Rebased branches get fresh reviews
- Stable identifier across force-pushes

```python
from pathlib import Path
from datetime import datetime, timedelta
import json

def sanitize_branch(branch: str) -> str:
    """Convert branch name to filesystem-safe string."""
    return branch.replace("/", "-").replace("\\", "-")

def discover_previous_review(project_encoded: str, branch: str, merge_base_sha: str) -> Path | None:
    """
    Find previous review for this branch/base combination.
    
    Returns:
        Path to review directory, or None if not found/stale
    """
    # 1. Construct expected path
    review_key = f"{sanitize_branch(branch)}-{merge_base_sha[:8]}"
    review_dir = Path.home() / ".local/spellbook/docs" / project_encoded / "reviews" / review_key
    
    # 2. Check existence
    if not review_dir.exists():
        return None
    
    # 3. Check freshness (30 day max age)
    manifest_path = review_dir / "review-manifest.json"
    if not manifest_path.exists():
        return None
    
    manifest = json.loads(manifest_path.read_text())
    created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    if datetime.now(created.tzinfo) - created > timedelta(days=30):
        return None  # Too old, start fresh
    
    # 4. Validate structure
    required_files = ["previous-items.json", "findings.json"]
    for f in required_files:
        if not (review_dir / f).exists():
            return None  # Incomplete, start fresh
    
    return review_dir
```

### 2.2 Previous Items States

Load and interpret previous review items:

| Status | Meaning | Action |
|--------|---------|--------|
| `PENDING` | Item was raised, not yet addressed | Include in new review if still present |
| `FIXED` | Item was addressed in subsequent commits | Do not re-raise |
| `DECLINED` | Author explicitly declined to fix | Do NOT re-raise (respect decision) |
| `PARTIAL_AGREEMENT` | Some parts fixed, some pending | Note pending parts only |
| `ALTERNATIVE_PROPOSED` | Author proposed different solution | Evaluate if alternative is adequate |

```python
def load_previous_items(review_dir: Path) -> list[dict]:
    """
    Load previous items with their resolution status.
    
    Returns list of:
    {
        "id": "finding-prev-001",
        "status": "declined" | "fixed" | "partial" | "alternative" | "pending",
        "reason": "Performance tradeoff acceptable",  # for declined
        "fixed": ["item1"],                           # for partial
        "pending": ["item2"],                         # for partial
        "alternative_proposed": "Use LRU cache",      # for alternative
        "accepted": true                              # for alternative
    }
    """
    items_path = review_dir / "previous-items.json"
    if not items_path.exists():
        return []
    
    data = json.loads(items_path.read_text())
    return data.get("items", [])
```

### 2.3 PR History Fetching (Online Mode)

Fetch PR description and comments for context:

```python
# Using MCP tools
pr_result = pr_fetch(pr_identifier="123")
# Returns: {"meta": {...}, "diff": "...", "repo": "owner/repo"}

# Extract comment threads
comments = gh_api(f"repos/{repo}/pulls/{pr_number}/comments")
```

**Offline Mode:** Skip this step. Log:
```
[OFFLINE] Skipping PR comment history.
```

### 2.4 Re-check Request Detection

Detect when author explicitly asks for re-review of specific items:

| Pattern | Meaning |
|---------|---------|
| "please re-check X" | Author wants X verified again |
| "PTAL at Y" | Please take another look at Y |
| "addressed in <sha>" | Author claims fix in specific commit |
| "@reviewer ready for re-review" | General re-review request |

```python
import re

RECHECK_PATTERNS = [
    r"please\s+(?:re-?)?check\s+(.+)",
    r"PTAL\s+(?:at\s+)?(.+)",
    r"addressed\s+(?:in\s+)?([a-f0-9]{7,40})",
    r"ready\s+for\s+re-?review",
]

def detect_recheck_requests(comments: list[str]) -> list[dict]:
    """Extract re-check requests from PR comments."""
    requests = []
    for comment in comments:
        for pattern in RECHECK_PATTERNS:
            match = re.search(pattern, comment, re.IGNORECASE)
            if match:
                requests.append({
                    "pattern": pattern,
                    "match": match.group(0),
                    "target": match.group(1) if match.lastindex else None
                })
    return requests
```

### 2.5 Context Object Construction

Build the context for Phase 3:

```python
def build_context(manifest: dict, previous_dir: Path | None, pr_data: dict | None) -> dict:
    """
    Construct review context for Phase 3.
    """
    context = {
        "manifest": manifest,
        "previous_review": None,
        "pr_context": None,
        "declined_items": [],
        "partial_items": [],
        "alternative_items": [],
        "recheck_requests": []
    }
    
    if previous_dir:
        items = load_previous_items(previous_dir)
        context["previous_review"] = str(previous_dir)
        context["declined_items"] = [i for i in items if i["status"] == "declined"]
        context["partial_items"] = [i for i in items if i["status"] == "partial"]
        context["alternative_items"] = [i for i in items if i["status"] == "alternative"]
    
    if pr_data:
        context["pr_context"] = {
            "title": pr_data["meta"].get("title"),
            "body": pr_data["meta"].get("body"),
            "author": pr_data["meta"].get("author")
        }
        context["recheck_requests"] = detect_recheck_requests(
            pr_data.get("comments", [])
        )
    
    return context
```

### 2.6 Output: context-analysis.md

```markdown
# Context Analysis

**Previous Review:** Found (2026-01-28)
**PR Context:** Available

## Previous Items Summary

| Status | Count |
|--------|-------|
| Declined | 1 |
| Partial | 1 |
| Alternative | 1 |

### Declined Items (will NOT re-raise)

- **finding-prev-001**: "Cache invalidation strategy"
  - Reason: "Performance tradeoff acceptable for our scale"
  - Declined: 2026-01-28

### Partial Agreements (pending items only)

- **finding-prev-002**: Security validation
  - Fixed: "Use parameterized queries"
  - Pending: "Add input validation at API layer"

### Alternative Solutions

- **finding-prev-003**: Caching approach
  - Original: "Use Redis for caching"
  - Alternative: "Use in-memory LRU cache"
  - Accepted: Yes (simpler deployment)

## Re-check Requests

- "please re-check the error handling in auth.py"
- "addressed in abc1234"
```

### 2.7 Output: previous-items.json

```json
{
  "version": "1.0",
  "source_review": "2026-01-28T15:00:00Z",
  "items": [
    {
      "id": "finding-prev-001",
      "status": "declined",
      "reason": "Performance tradeoff acceptable for our scale",
      "declined_at": "2026-01-28T16:00:00Z"
    },
    {
      "id": "finding-prev-002",
      "status": "partial",
      "fixed": ["Use parameterized queries"],
      "pending": ["Add input validation at API layer"],
      "updated_at": "2026-01-29T10:00:00Z"
    },
    {
      "id": "finding-prev-003",
      "status": "alternative",
      "original_suggestion": "Use Redis for caching",
      "alternative_proposed": "Use in-memory LRU cache",
      "rationale": "Simpler deployment, sufficient for current load",
      "accepted": true
    }
  ]
}
```

### Phase 2 Self-Check

Before proceeding to Phase 3:

- [ ] Previous review discovered (or confirmed not found)
- [ ] Previous items loaded with correct statuses
- [ ] PR context fetched (if online and PR mode)
- [ ] Re-check requests extracted
- [ ] context-analysis.md written
- [ ] previous-items.json updated (or created empty)

**Note:** Phase 2 failures are non-blocking. If context cannot be loaded, proceed with empty context and log warning.

---

## Phase 3: Deep Review

**Purpose:** Perform multi-pass code analysis, generate findings with severity classification, and respect previous review context.

### 3.1 Multi-Pass Review Order

Review code in multiple passes, each focused on a specific category:

| Pass | Focus | Severity Range | Description |
|------|-------|----------------|-------------|
| 1 | Security | Critical, High | Injection, auth bypass, data exposure, secrets |
| 2 | Correctness | High, Medium | Logic errors, edge cases, null handling, race conditions |
| 3 | Quality | Medium, Low | Maintainability, complexity, patterns, readability |
| 4 | Polish | Low, Nit | Style, naming, minor optimizations, documentation |

**Rationale:** Multi-pass approach ensures critical issues are found first and aren't overshadowed by style nits.

### 3.2 Severity Taxonomy

Use precise severity definitions:

| Severity | Definition | Examples |
|----------|------------|----------|
| CRITICAL | Data loss, security breach, production outage | SQL injection, auth bypass, infinite loop in main path |
| HIGH | Broken functionality, incorrect behavior | Off-by-one, null dereference, race condition |
| MEDIUM | Quality concern, technical debt | High complexity, missing error handling, code duplication |
| LOW | Minor improvement, optimization | Inefficient algorithm (non-hot path), better naming |
| NIT | Purely stylistic | Formatting, comment style, import order |
| PRAISE | Noteworthy positive | Clever solution, good pattern usage, excellent tests |

**Severity Decision Tree:**

```
Is it a security issue, bug, or data loss risk?
  -> Yes: CRITICAL
  -> No: Continue

Does it break contracts, architecture, or core functionality?
  -> Yes: HIGH
  -> No: Continue

Is it a code quality or maintainability concern?
  -> Yes: MEDIUM
  -> No: Continue

Is it a minor improvement or optimization?
  -> Yes: LOW
  -> No: Continue

Is it purely stylistic?
  -> Yes: NIT
  -> No: PRAISE (if positive) or skip
```

### 3.3 Finding Schema

Each finding follows this structure:

```json
{
  "id": "finding-001",
  "severity": "HIGH",
  "category": "security",
  "file": "auth.py",
  "line": 45,
  "end_line": 47,
  "summary": "SQL injection via string interpolation",
  "reason": "User input from request directly concatenated into SQL query without sanitization",
  "evidence": "query = f\"SELECT * FROM users WHERE id = {user_id}\"",
  "suggestion": "Use parameterized queries: cursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_id,))",
  "verification_status": null,
  "previous_status": null,
  "tags": ["owasp-injection", "cwe-89"]
}
```

**Field Requirements:**

| Field | Required | Nullable | Notes |
|-------|----------|----------|-------|
| id | Yes | No | Unique within review |
| severity | Yes | No | One of CRITICAL/HIGH/MEDIUM/LOW/NIT/PRAISE |
| category | Yes | No | security/logic/error/type/test/perf/style/doc |
| file | Yes | No | Relative path |
| line | Yes | No | Start line (1-indexed) |
| end_line | No | Yes | End line (null = single line) |
| summary | Yes | No | One-line description |
| reason | No | Yes | Detailed explanation (null for NIT/PRAISE) |
| evidence | Yes | No | Code snippet showing issue |
| suggestion | No | Yes | Recommended fix (null if unclear) |
| verification_status | No | Yes | Set in Phase 4 |
| previous_status | No | Yes | From Phase 2 context |
| tags | No | No | Always array (empty if none) |

### 3.4 Previous Items Integration

During review, check each potential finding against previous items:

```python
def should_raise_finding(finding: dict, context: dict) -> tuple[bool, str | None]:
    """
    Determine if a finding should be raised given previous context.
    
    Returns:
        (should_raise, previous_status)
    """
    # Check declined items - never re-raise
    for declined in context["declined_items"]:
        if finding_matches(finding, declined):
            return (False, "declined")
    
    # Check accepted alternatives - don't re-raise original issue
    for alt in context["alternative_items"]:
        if alt["accepted"] and finding_matches_original(finding, alt):
            return (False, "alternative_accepted")
    
    # Check partial items - only raise pending parts
    for partial in context["partial_items"]:
        if finding_matches_pending(finding, partial):
            finding["previous_status"] = "partial_pending"
            return (True, "partial_pending")
    
    return (True, None)
```

### 3.5 Category Definitions

| Category | Scope |
|----------|-------|
| security | Injection, XSS, auth bypass, secrets exposure, CSRF |
| logic | Off-by-one, null handling, race condition, incorrect algorithm |
| error | Missing error handling, swallowed exceptions, unclear errors |
| type | Type mismatch, unsafe cast, missing validation |
| test | Missing tests, weak assertions, flaky tests |
| perf | O(n^2) in hot path, memory leak, blocking I/O |
| style | Naming, formatting, dead code |
| doc | Missing/wrong comments, outdated docs |

### 3.6 Review Execution

For each file in priority order:

```python
def review_file(file_path: str, diff: str, context: dict) -> list[dict]:
    """
    Review a single file through all passes.
    """
    findings = []
    
    # Pass 1: Security
    security_findings = analyze_security(file_path, diff)
    findings.extend(filter_by_context(security_findings, context))
    
    # Pass 2: Correctness
    logic_findings = analyze_logic(file_path, diff)
    findings.extend(filter_by_context(logic_findings, context))
    
    # Pass 3: Quality
    quality_findings = analyze_quality(file_path, diff)
    findings.extend(filter_by_context(quality_findings, context))
    
    # Pass 4: Polish
    polish_findings = analyze_polish(file_path, diff)
    findings.extend(filter_by_context(polish_findings, context))
    
    return findings
```

### 3.7 Noteworthy Collection

Collect positive observations for PRAISE findings:

```python
NOTEWORTHY_PATTERNS = [
    "comprehensive test coverage",
    "clever use of pattern",
    "excellent error messages",
    "good documentation",
    "clean abstraction",
    "thoughtful edge case handling"
]
```

### 3.8 Output: findings.json

```json
{
  "version": "1.0",
  "generated_at": "2026-01-30T10:30:00Z",
  "review_sha": "def67890",
  "findings": [
    {
      "id": "finding-001",
      "severity": "HIGH",
      "category": "security",
      "file": "auth.py",
      "line": 45,
      "end_line": 47,
      "summary": "SQL injection via string interpolation",
      "reason": "User input from request directly concatenated into SQL query",
      "evidence": "query = f\"SELECT * FROM users WHERE id = {user_id}\"",
      "suggestion": "Use parameterized queries",
      "verification_status": null,
      "previous_status": null,
      "tags": ["owasp-injection", "cwe-89"]
    }
  ],
  "summary": {
    "total": 8,
    "by_severity": {
      "CRITICAL": 0,
      "HIGH": 2,
      "MEDIUM": 3,
      "LOW": 2,
      "NIT": 1,
      "PRAISE": 0
    },
    "by_category": {
      "security": 2,
      "logic": 1,
      "quality": 3,
      "style": 2
    },
    "skipped_declined": 1,
    "skipped_alternative": 1
  }
}
```

### 3.9 Output: findings.md

```markdown
# Review Findings

**Generated:** 2026-01-30 10:30 UTC
**Files Reviewed:** 12
**Findings:** 8 (2 HIGH, 3 MEDIUM, 2 LOW, 1 NIT)
**Skipped:** 2 (1 declined, 1 alternative accepted)

---

## HIGH Severity

### [HIGH-001] SQL injection via string interpolation

**File:** auth.py:45-47
**Category:** Security

User input from request directly concatenated into SQL query.

```python
# Current
query = f"SELECT * FROM users WHERE id = {user_id}"

# Suggested
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

**Tags:** owasp-injection, cwe-89

---

## MEDIUM Severity

...
```

### Phase 3 Self-Check

Before proceeding to Phase 4:

- [ ] All files reviewed in priority order
- [ ] All four passes completed per file
- [ ] Declined items not re-raised
- [ ] Partial items annotated correctly
- [ ] Each finding has required fields
- [ ] findings.json written
- [ ] findings.md written

<CRITICAL>
Do not proceed to verification with incomplete findings. Every finding must have file, line, and evidence.
</CRITICAL>

---

## Phase 4: Verification

**Purpose:** Fact-check every finding against the actual codebase. Remove false positives. Flag uncertain claims for human review.

### 4.1 Verification Overview

This is a simplified verification protocol, not a full invocation of the `fact-checking` skill. It focuses on:
- Line content verification
- Function behavior checks
- Call pattern analysis
- Pattern violation confirmation

### 4.2 Claim Types

| Claim Type | Example | Verification Method |
|------------|---------|---------------------|
| line_content | "Line 45 contains SQL interpolation" | Read line 45, pattern match |
| function_behavior | "Function X doesn't validate input" | Read function, check for validation |
| call_pattern | "Y is called without error handling" | Trace callers of Y |
| pattern_violation | "Same code at A and B (DRY violation)" | Compare code at A and B |

### 4.3 Claim Extraction Algorithm

Extract verifiable claims from finding text:

```python
import re
from dataclasses import dataclass
from typing import Literal, Optional

ClaimType = Literal["line_content", "function_behavior", "call_pattern", "pattern_violation"]

@dataclass
class Claim:
    type: ClaimType
    file: str
    line: Optional[int]
    function: Optional[str]
    pattern: str
    expected: Optional[str]
    compare_to: Optional[str]

# Extraction patterns (most specific first)
CLAIM_PATTERNS = [
    # Line content: "Line 45 contains X" / "at line 45"
    (r"(?:line\s+(\d+)|at\s+line\s+(\d+)).*?(?:contains?|has|shows?)\s+['\"]?([^'\"]+)['\"]?", "line_content"),
    
    # Function behavior: "function X doesn't validate"
    (r"(?:function|method)\s+['\"]?(\w+)['\"]?\s+(?:doesn't|lacks?|missing)\s+(\w+)", "function_behavior"),
    
    # Call pattern: "X is called without error handling"
    (r"['\"]?(\w+)['\"]?\s+(?:is\s+)?called\s+without\s+([^.]+)", "call_pattern"),
    
    # Pattern violation: "same code at A and B"
    (r"(?:same|identical|duplicated?)\s+(?:code|logic)\s+(?:at|in)\s+([^and]+)\s+and\s+([^\s.]+)", "pattern_violation"),
]

def extract_claims(finding: dict) -> list[Claim]:
    """Extract verifiable claims from a finding."""
    claims = []
    text = finding.get("reason", "") + " " + finding.get("evidence", "")
    file_context = finding.get("file", "")
    line_context = finding.get("line")
    
    for pattern, claim_type in CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()
            claim = build_claim(claim_type, groups, file_context, line_context)
            if claim:
                claims.append(claim)
    
    # Always add implicit claim from finding's file:line
    if line_context and file_context:
        evidence = finding.get("evidence", "")
        if evidence:
            claims.append(Claim(
                type="line_content",
                file=file_context,
                line=line_context,
                function=None,
                pattern=evidence[:100],
                expected=None,
                compare_to=None
            ))
    
    return claims
```

### 4.4 Verification Functions

```python
from pathlib import Path

def verify_line_content(claim: Claim, repo_root: Path) -> str:
    """Verify that a line contains expected content."""
    try:
        file_path = repo_root / claim.file
        if not file_path.exists():
            return "INCONCLUSIVE"
        
        lines = file_path.read_text().splitlines()
        if claim.line is None or claim.line > len(lines):
            return "INCONCLUSIVE"
        
        actual_line = lines[claim.line - 1]  # 1-indexed
        
        if claim.pattern.lower() in actual_line.lower():
            return "VERIFIED"
        
        return "REFUTED"
    except Exception:
        return "INCONCLUSIVE"


def verify_function_behavior(claim: Claim, repo_root: Path) -> str:
    """Verify function has or lacks expected behavior."""
    try:
        file_path = repo_root / claim.file
        if not file_path.exists():
            return "INCONCLUSIVE"
        
        content = file_path.read_text()
        
        # Find function definition
        func_pattern = rf"def\s+{re.escape(claim.function)}\s*\([^)]*\):"
        match = re.search(func_pattern, content)
        if not match:
            return "INCONCLUSIVE"
        
        # Extract function body
        start = match.end()
        func_body = extract_function_body(content, start)
        
        # Check for expected pattern
        if claim.pattern.lower() in func_body.lower():
            return "REFUTED" if claim.expected == "missing" else "VERIFIED"
        else:
            return "VERIFIED" if claim.expected == "missing" else "REFUTED"
    except Exception:
        return "INCONCLUSIVE"


def verify_call_pattern(claim: Claim, repo_root: Path) -> str:
    """Verify call sites have or lack expected pattern."""
    try:
        file_path = repo_root / claim.file
        if not file_path.exists():
            return "INCONCLUSIVE"
        
        content = file_path.read_text()
        
        # Find calls to the function
        call_pattern = rf"{re.escape(claim.function)}\s*\("
        matches = list(re.finditer(call_pattern, content))
        
        if not matches:
            return "INCONCLUSIVE"
        
        # Check context around each call
        for match in matches:
            start_pos = max(0, match.start() - 500)
            end_pos = min(len(content), match.end() + 500)
            context = content[start_pos:end_pos]
            
            if claim.pattern.lower() in context.lower():
                return "REFUTED"  # Found what was claimed missing
        
        return "VERIFIED"  # Pattern truly missing
    except Exception:
        return "INCONCLUSIVE"


def verify_pattern_violation(claim: Claim, repo_root: Path) -> str:
    """Verify duplicate code exists at two locations."""
    try:
        from difflib import SequenceMatcher
        
        path_a = repo_root / claim.file
        path_b = repo_root / claim.compare_to
        
        if not path_a.exists() or not path_b.exists():
            return "INCONCLUSIVE"
        
        content_a = path_a.read_text()[:1000]
        content_b = path_b.read_text()[:1000]
        
        # Normalize and compare
        norm_a = re.sub(r'\s+', ' ', content_a.lower().strip())
        norm_b = re.sub(r'\s+', ' ', content_b.lower().strip())
        
        ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
        
        if ratio > 0.5:
            return "VERIFIED"
        return "REFUTED"
    except Exception:
        return "INCONCLUSIVE"
```

### 4.5 Finding Verification

```python
def verify_finding(finding: dict, repo_root: Path) -> str:
    """
    Verify a single finding's claims.
    
    Returns: "VERIFIED" | "REFUTED" | "INCONCLUSIVE"
    """
    claims = extract_claims(finding)
    results = []
    
    for claim in claims:
        if claim.type == "line_content":
            results.append(verify_line_content(claim, repo_root))
        elif claim.type == "function_behavior":
            results.append(verify_function_behavior(claim, repo_root))
        elif claim.type == "call_pattern":
            results.append(verify_call_pattern(claim, repo_root))
        elif claim.type == "pattern_violation":
            results.append(verify_pattern_violation(claim, repo_root))
    
    # Aggregate: any REFUTED = REFUTED, any INCONCLUSIVE = INCONCLUSIVE
    if "REFUTED" in results:
        return "REFUTED"
    elif "INCONCLUSIVE" in results:
        return "INCONCLUSIVE"
    else:
        return "VERIFIED"
```

### 4.6 Duplicate Detection

Before verification, check for duplicate findings:

```python
def detect_duplicates(findings: list[dict]) -> list[tuple[str, str]]:
    """Find duplicate or near-duplicate findings."""
    duplicates = []
    
    for i, f1 in enumerate(findings):
        for f2 in findings[i+1:]:
            if is_duplicate(f1, f2):
                duplicates.append((f1["id"], f2["id"]))
    
    return duplicates

def is_duplicate(f1: dict, f2: dict) -> bool:
    """Check if two findings are duplicates."""
    return (
        f1["file"] == f2["file"] and
        f1["line"] == f2["line"] and
        f1["category"] == f2["category"]
    )
```

### 4.7 Line Number Validation

Ensure line numbers are accurate:

```python
def validate_line_numbers(finding: dict, repo_root: Path) -> bool:
    """Verify line numbers exist and contain expected content."""
    file_path = repo_root / finding["file"]
    if not file_path.exists():
        return False
    
    lines = file_path.read_text().splitlines()
    
    if finding["line"] > len(lines):
        return False
    
    if finding.get("end_line") and finding["end_line"] > len(lines):
        return False
    
    return True
```

### 4.8 Signal-to-Noise Calculation

Compute ratio of valuable findings to noise:

```python
def calculate_snr(findings: list[dict]) -> float:
    """
    Calculate signal-to-noise ratio.
    
    Signal = CRITICAL + HIGH + MEDIUM (verified)
    Noise = LOW + NIT + INCONCLUSIVE
    
    Returns ratio 0.0 to 1.0
    """
    signal = 0
    noise = 0
    
    for f in findings:
        if f["verification_status"] == "REFUTED":
            continue  # Don't count refuted
        
        severity = f["severity"]
        status = f["verification_status"]
        
        if severity in ("CRITICAL", "HIGH", "MEDIUM") and status == "VERIFIED":
            signal += 1
        elif severity in ("LOW", "NIT") or status == "INCONCLUSIVE":
            noise += 1
    
    total = signal + noise
    if total == 0:
        return 1.0
    
    return round(signal / total, 3)
```

### 4.9 REFUTED Finding Handling

- REFUTED findings are **removed** from final output
- They are logged in verification-audit.md for transparency
- User is informed: "N findings removed after verification"

### 4.10 INCONCLUSIVE Finding Handling

- INCONCLUSIVE findings are **kept** with a flag
- Report marks them: `[NEEDS VERIFICATION]`
- User should manually verify these

### 4.11 Output: verification-audit.md

```markdown
# Verification Audit

**Findings Checked:** 10
**Verified:** 6
**Refuted:** 2
**Inconclusive:** 2
**Signal/Noise:** 0.75

## Refuted Findings (Removed)

### finding-003: "Unused import os"
**Reason:** Line 5 does not contain `import os`
**Actual:** Line 5 is `import sys`

### finding-007: "Missing null check"
**Reason:** Null check found at line 88
**Actual:** `if user is None: return`

## Inconclusive Findings (Flagged)

### finding-005: "Potential race condition"
**Reason:** Could not trace all code paths
**Action:** Human verification required

## Verification Log

| Finding | Status | Claims | Result |
|---------|--------|--------|--------|
| finding-001 | VERIFIED | 2 | All claims confirmed |
| finding-002 | VERIFIED | 1 | Claim confirmed |
| finding-003 | REFUTED | 1 | Line content mismatch |
...
```

### Phase 4 Self-Check

Before proceeding to Phase 5:

- [ ] All findings verified against codebase
- [ ] REFUTED findings removed and logged
- [ ] INCONCLUSIVE findings flagged
- [ ] Duplicates detected and merged
- [ ] Line numbers validated
- [ ] Signal-to-noise ratio calculated
- [ ] verification-audit.md written
- [ ] findings.json updated with verification_status

<CRITICAL>
Every finding in the final report must have verification_status set. Unverified findings indicate incomplete Phase 4.
</CRITICAL>

---

## Phase 5: Report Generation

**Purpose:** Produce final deliverables including Markdown report and machine-readable JSON summary.

### 5.1 Finding Filtering

Filter to verified and inconclusive findings only:

```python
def filter_findings_for_report(findings: list[dict]) -> list[dict]:
    """Filter out REFUTED findings for final report."""
    return [
        f for f in findings
        if f.get("verification_status") != "REFUTED"
    ]
```

### 5.2 Severity Sorting

Sort findings by severity (most critical first):

```python
SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "NIT": 4,
    "PRAISE": 5
}

def sort_by_severity(findings: list[dict]) -> list[dict]:
    """Sort findings by severity, most critical first."""
    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))
```

### 5.3 Verdict Determination

Determine overall review verdict:

```python
def determine_verdict(findings: list[dict]) -> str:
    """
    Determine review verdict based on findings.
    
    Returns: "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
    """
    severities = [f["severity"] for f in findings if f.get("verification_status") != "REFUTED"]
    
    if "CRITICAL" in severities:
        return "REQUEST_CHANGES"
    
    if "HIGH" in severities:
        return "REQUEST_CHANGES"
    
    if "MEDIUM" in severities:
        return "COMMENT"
    
    return "APPROVE"

def verdict_rationale(verdict: str, findings: list[dict]) -> str:
    """Generate rationale for verdict."""
    by_severity = {}
    for f in findings:
        sev = f["severity"]
        by_severity[sev] = by_severity.get(sev, 0) + 1
    
    if verdict == "REQUEST_CHANGES":
        critical = by_severity.get("CRITICAL", 0)
        high = by_severity.get("HIGH", 0)
        return f"{critical + high} blocking issue(s) require attention"
    elif verdict == "COMMENT":
        medium = by_severity.get("MEDIUM", 0)
        return f"{medium} medium-severity issue(s) worth discussing"
    else:
        return "No blocking issues found"
```

### 5.4 Template Rendering

Use Python's `string.Template` for report generation:

```python
from string import Template

def render_report(manifest: dict, findings: list[dict], context: dict, snr: float) -> str:
    """Render final report using template."""
    with open("templates/report.md.tpl") as f:
        tpl = Template(f.read())
    
    # Count by severity
    by_severity = count_by_severity(findings)
    
    # Generate findings section
    findings_section = render_findings_section(findings)
    
    # Generate action items
    action_items = render_action_items(findings)
    
    # Generate previous context section
    previous_context = render_previous_context(context)
    
    return tpl.substitute(
        branch=manifest["target"]["branch"],
        base=manifest["target"]["base"],
        base_sha=manifest["target"]["merge_base_sha"][:8],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        file_count=manifest["files"]["total"],
        finding_count=len(findings),
        snr=f"{snr:.2f}",
        critical_count=by_severity.get("CRITICAL", 0),
        high_count=by_severity.get("HIGH", 0),
        medium_count=by_severity.get("MEDIUM", 0),
        low_count=by_severity.get("LOW", 0),
        verdict=determine_verdict(findings),
        findings_section=findings_section,
        action_items=action_items,
        previous_context=previous_context
    )

def render_finding(finding: dict) -> str:
    """Render a single finding using template."""
    with open("templates/finding.md.tpl") as f:
        tpl = Template(f.read())
    
    line_str = str(finding["line"])
    if finding.get("end_line"):
        line_str = f"{finding['line']}-{finding['end_line']}"
    
    # Detect language from file extension
    ext = finding["file"].rsplit(".", 1)[-1] if "." in finding["file"] else ""
    lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "rb": "ruby"}
    lang = lang_map.get(ext, ext)
    
    verification_flag = ""
    if finding.get("verification_status") == "INCONCLUSIVE":
        verification_flag = " [NEEDS VERIFICATION]"
    
    return tpl.substitute(
        severity=finding["severity"],
        id=finding["id"].replace("finding-", ""),
        summary=finding["summary"] + verification_flag,
        file=finding["file"],
        line=line_str,
        category=finding["category"].title(),
        reason=finding.get("reason", ""),
        lang=lang,
        evidence=finding.get("evidence", "N/A"),
        suggestion=finding.get("suggestion", "N/A")
    )
```

### 5.5 Action Items Generation

Generate actionable checklist:

```python
def render_action_items(findings: list[dict]) -> str:
    """Generate action items checklist."""
    items = []
    
    for f in findings:
        if f["severity"] in ("CRITICAL", "HIGH"):
            items.append(f"- [ ] Fix {f['id']}: {f['summary']}")
        elif f["severity"] == "MEDIUM":
            items.append(f"- [ ] Consider {f['id']}: {f['summary']}")
    
    return "\n".join(items) if items else "No blocking action items."
```

### 5.6 Previous Context Section

```python
def render_previous_context(context: dict) -> str:
    """Render previous review context section."""
    if not context.get("previous_review"):
        return "## Previous Review Context\n\nNo previous review found."
    
    lines = ["## Previous Review Context\n"]
    
    declined = len(context.get("declined_items", []))
    partial = len(context.get("partial_items", []))
    alternative = len(context.get("alternative_items", []))
    
    if declined:
        lines.append(f"- {declined} declined item(s) (not re-raised)")
    if partial:
        lines.append(f"- {partial} partial fix(es) (pending items noted)")
    if alternative:
        accepted = sum(1 for a in context["alternative_items"] if a.get("accepted"))
        lines.append(f"- {alternative} alternative(s) ({accepted} accepted)")
    
    return "\n".join(lines)
```

### 5.7 Output: review-report.md

The final report is rendered using `templates/report.md.tpl`:

```markdown
# Code Review Report

**Branch:** feature/auth-refactor
**Base:** main (abc12345)
**Reviewed:** 2026-01-30 10:30 UTC
**Files:** 12 | **Findings:** 6 | **Signal/Noise:** 0.75

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 1 |

**Verdict:** REQUEST_CHANGES (2 blocking issue(s) require attention)

---

## High Severity

### [HIGH-001] SQL injection via string interpolation

**File:** auth.py:45-47
**Category:** Security

User input from request directly concatenated into SQL query.

```python
# Current
query = f"SELECT * FROM users WHERE id = {user_id}"

# Suggested
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

---

## Action Items

- [ ] Fix HIGH-001: SQL injection in auth.py
- [ ] Fix HIGH-002: Missing auth check in payment.py
- [ ] Consider MEDIUM-001: Add input validation

---

## Previous Review Context

- 1 declined item(s) (not re-raised)
- 1 partial fix(es) (pending items noted)
- 1 alternative(s) (1 accepted)
```

### 5.8 Output: review-summary.json

```json
{
  "version": "1.0",
  "generated_at": "2026-01-30T10:30:00Z",
  "target": {
    "branch": "feature/auth-refactor",
    "base": "main",
    "merge_base_sha": "abc12345",
    "head_sha": "def67890"
  },
  "verdict": "REQUEST_CHANGES",
  "verdict_rationale": "2 blocking issue(s) require attention",
  "statistics": {
    "files_reviewed": 12,
    "total_findings": 8,
    "verified_findings": 6,
    "refuted_findings": 2,
    "by_severity": {
      "CRITICAL": 0,
      "HIGH": 2,
      "MEDIUM": 3,
      "LOW": 1,
      "NIT": 0,
      "PRAISE": 0
    },
    "signal_to_noise": 0.75
  },
  "action_items": [
    {"id": "HIGH-001", "summary": "SQL injection in auth.py", "priority": "blocking"},
    {"id": "HIGH-002", "summary": "Missing auth check in payment.py", "priority": "blocking"},
    {"id": "MEDIUM-001", "summary": "Add input validation", "priority": "suggested"}
  ],
  "artifacts": {
    "report_path": "~/.local/spellbook/docs/project/reviews/feature-auth-abc12345/review-report.md",
    "findings_path": "~/.local/spellbook/docs/project/reviews/feature-auth-abc12345/findings.json"
  }
}
```

### 5.9 File Output

Write all artifacts to the review directory:

```python
def write_review_artifacts(review_dir: Path, report: str, summary: dict):
    """Write all final artifacts."""
    review_dir.mkdir(parents=True, exist_ok=True)
    
    # Write Markdown report
    (review_dir / "review-report.md").write_text(report)
    
    # Write JSON summary
    (review_dir / "review-summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    
    print(f"Review complete: {review_dir / 'review-report.md'}")
```

### Phase 5 Self-Check

Before declaring review complete:

- [ ] Findings filtered (REFUTED removed)
- [ ] Findings sorted by severity
- [ ] Verdict determined with rationale
- [ ] Report rendered from template
- [ ] Action items generated
- [ ] Previous context included
- [ ] review-report.md written
- [ ] review-summary.json written
- [ ] All artifacts in correct directory

---

## Constants and Configuration

### SEVERITY_ORDER

Severity levels for sorting findings (lower number = higher priority):

```python
SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "NIT": 4,
    "PRAISE": 5
}
```

### Error Codes

```python
from enum import Enum

class ReviewError(Enum):
    E_TARGET_NOT_FOUND = "Target branch/PR not found"
    E_NO_DIFF = "No changes between target and base"
    E_MERGE_BASE_FAILED = "Could not determine merge base"
    E_NETWORK_UNAVAILABLE = "Network required but unavailable"
    E_PREVIOUS_REVIEW_CORRUPT = "Previous review JSON is malformed"
    E_FILE_NOT_READABLE = "Cannot read file for review"
    E_DIFF_TOO_LARGE = "Diff exceeds size limit"
    E_VERIFICATION_TIMEOUT = "Verification phase timed out"
    E_TEMPLATE_ERROR = "Template rendering failed"
    E_WRITE_FAILED = "Cannot write output file"
```

### Configurable Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| `STALENESS_DAYS` | 30 | Max age of previous review before ignored |
| `LARGE_DIFF_LINES` | 10000 | Lines threshold for chunked processing |
| `SUBAGENT_THRESHOLD_FILES` | 20 | Files threshold for parallel subagent dispatch |
| `SUBAGENT_THRESHOLD_LINES` | 500 | Lines per file threshold for subagent dispatch |
| `VERIFICATION_TIMEOUT_SEC` | 60 | Max time for verification phase |

### State Machine

Review lifecycle state machine:

```
                    +----------+
                    |  START   |
                    +----+-----+
                         |
                         v
                    +----------+
                    | PLANNING |  (Phase 1)
                    +----+-----+
                         |
            +------------+------------+
            |                         |
            v                         v
       +--------+               +----------+
       | ERROR  |               | CONTEXT  |  (Phase 2)
       +--------+               +----+-----+
                                     |
                                     v
                                +----------+
                                | REVIEW   |  (Phase 3)
                                +----+-----+
                                     |
                                     v
                                +----------+
                                | VERIFY   |  (Phase 4)
                                +----+-----+
                                     |
                                     v
                                +----------+
                                | REPORT   |  (Phase 5)
                                +----+-----+
                                     |
                                     v
                                +----------+
                                | COMPLETE |
                                +----------+
```

---

## Offline Mode

### Activation

Offline mode is activated in two ways:

```bash
# Explicit flag
advanced-code-review feature/my-branch --offline

# Implicit (local branch, no PR indicators)
advanced-code-review feature/my-branch
```

### Detection Logic

```python
def detect_offline_mode(target: str, flags: dict) -> bool:
    """Determine if review should run in offline mode."""
    # Explicit flag always wins
    if flags.get("offline"):
        return True
    
    # PR indicators require network
    if target.startswith("#") or target.startswith("https://"):
        return False
    
    # Local branch defaults to offline
    return True
```

### Behavior Differences

| Feature | Online Mode | Offline Mode |
|---------|-------------|--------------|
| PR metadata | Fetched via gh/MCP | Skipped |
| PR comments | Fetched for context | Skipped |
| Previous review from PR | Available | Local only |
| Branch checkout | Can use `gh pr checkout` | Must exist locally |
| Re-check request detection | From PR comments | Not available |

### Warning Messages

When running offline:

```
[OFFLINE] Reviewing local branch 'feature/xyz' against 'main'.
[OFFLINE] PR context unavailable. Review based on local diff only.
[OFFLINE] Skipping PR comment history.
[OFFLINE] No network operations will be performed.
```

### Forced Offline Scenarios

| Scenario | Behavior |
|----------|----------|
| No network connectivity | Auto-fallback to offline |
| `gh` CLI not authenticated | Warn and continue offline |
| Rate limit exceeded | Warn and continue offline |
| MCP tools unavailable | Fallback to git-only |

---

## Anti-Patterns

<FORBIDDEN>
- Claim line contains X without reading line first
- Re-raise declined items (respect previous decisions)
- Skip verification phase (all findings must be verified)
- Mark finding as VERIFIED without actual verification
- Include REFUTED findings in final report
- Generate findings without file/line/evidence
- Guess at severity (use decision tree)
- Skip multi-pass review order
- Ignore previous review context when available
- Produce report without rendering through templates
- Write artifacts to wrong directory
- Skip any phase self-check
- Proceed past failed self-check
</FORBIDDEN>

---

## Circuit Breakers

**Stop execution when:**

- Phase 1 fails to resolve target (E_TARGET_NOT_FOUND)
- No changes found between target and base (E_NO_DIFF)
- More than 3 consecutive verification failures
- Verification phase exceeds timeout (VERIFICATION_TIMEOUT_SEC)
- Cannot write output files (E_WRITE_FAILED)

**Recovery actions:**

| Failure | Recovery |
|---------|----------|
| Network unavailable | Fall back to offline mode |
| Previous review corrupt | Start fresh review, warn |
| File not readable | Skip file, log warning |
| Diff too large | Chunk processing, warn |
| Template error | Use fallback raw format |

---

## Final Self-Check

Before declaring review complete, verify ALL of the following:

### Phase Completion

- [ ] Phase 1: Target resolved, manifest written
- [ ] Phase 2: Context loaded, previous items parsed
- [ ] Phase 3: All passes complete, findings generated
- [ ] Phase 4: All findings verified, REFUTED removed
- [ ] Phase 5: Report rendered, artifacts written

### Quality Gates

- [ ] Every finding has: id, severity, category, file, line, evidence
- [ ] No REFUTED findings in final report
- [ ] INCONCLUSIVE findings flagged with [NEEDS VERIFICATION]
- [ ] Declined items from previous review not re-raised
- [ ] Severity assignments follow decision tree
- [ ] Signal-to-noise ratio calculated and reported

### Output Verification

- [ ] review-manifest.json exists and valid JSON
- [ ] review-plan.md exists
- [ ] context-analysis.md exists
- [ ] previous-items.json exists (even if empty)
- [ ] findings.json exists with verification_status on all
- [ ] verification-audit.md exists
- [ ] review-report.md exists
- [ ] review-summary.json exists and valid JSON

<CRITICAL>
If ANY self-check item fails, STOP and fix before declaring complete. A review with unchecked items is an incomplete review.
</CRITICAL>

---

## Integration Points

### MCP Tools

| Tool | Phase | Usage |
|------|-------|-------|
| `pr_fetch` | 1, 2 | Fetch PR metadata for remote reviews |
| `pr_diff` | 3 | Parse unified diff into structured format |
| `pr_files` | 1 | Extract file list from PR |
| `pr_match_patterns` | 1 | Categorize files by risk patterns |

### Git Commands

| Command | Phase | Usage |
|---------|-------|-------|
| `git merge-base` | 1 | Find common ancestor with base |
| `git diff --name-only` | 1 | List changed files |
| `git diff` | 3 | Get full diff content |
| `git log` | 2 | Check commit history for context |
| `git show` | 4 | Verify file contents at SHA |

### gh CLI

| Command | Phase | Usage | Requires Network |
|---------|-------|-------|------------------|
| `gh pr view` | 1, 2 | Fetch PR description/metadata | Yes |
| `gh pr diff` | 3 | Get PR diff (alternative to git) | Yes |
| `gh api` | 2 | Fetch PR comments for context | Yes |

### Fallback Chain

```
MCP pr_fetch -> gh pr view -> git diff (local only)
MCP pr_diff -> gh pr diff -> git diff
```

---

## Template Files

Templates use Python's `string.Template` with `$variable` substitution:

| Template | Purpose |
|----------|---------|
| `templates/report.md.tpl` | Final review report |
| `templates/finding.md.tpl` | Individual finding block |
| `templates/progress.md.tpl` | Phase transition logging |

### Template Variables

**report.md.tpl:**
- `$branch` - Target branch name
- `$base` - Base branch name
- `$base_sha` - Merge base SHA (first 8 chars)
- `$timestamp` - Review timestamp
- `$file_count` - Number of files reviewed
- `$finding_count` - Total findings in report
- `$snr` - Signal-to-noise ratio
- `$critical_count`, `$high_count`, `$medium_count`, `$low_count` - Counts by severity
- `$verdict` - Review verdict
- `$findings_section` - Rendered findings (from finding.md.tpl)
- `$action_items` - Checklist of action items
- `$previous_context` - Previous review context section

**finding.md.tpl:**
- `$severity` - Finding severity
- `$id` - Finding ID (numeric part)
- `$summary` - One-line summary
- `$file` - File path
- `$line` - Line number(s)
- `$category` - Finding category
- `$reason` - Detailed reason
- `$lang` - Code language for syntax highlighting
- `$evidence` - Code showing issue
- `$suggestion` - Recommended fix

---

<FINAL_EMPHASIS>
A code review is only as valuable as its accuracy. Verify before asserting. Respect previous decisions. Prioritize by impact. Your reputation depends on being thorough AND correct.
</FINAL_EMPHASIS>
``````````
