---
description: "Advanced Code Review Phase 1: Strategic Planning - scope analysis, risk categorization, priority ordering"
---

# Phase 1: Strategic Planning

## Invariant Principles

1. **Risk-based prioritization**: Higher risk files are reviewed first. Security, payment, and migration files take precedence over tests and documentation.
2. **Scope clarity**: All files in scope must be identified before review starts. No file should be discovered mid-review.
3. **Complexity honesty**: Estimates must reflect actual review effort required. Underestimating leads to rushed reviews; overestimating wastes planning time.

**Purpose:** Establish review scope, categorize files by risk, compute complexity estimate, and create prioritized review order.

<CRITICAL>
**Scope is the branch's GitHub-PR diff: three-dot `base...HEAD` against the DETECTED
merge target.** Do not hardcode `main`. Detect the base, fetch it so the merge-base is
current, and use merge-base / three-dot semantics so commits merged IN from the target
(e.g. a `master` merge dragging in unrelated migrations) are EXCLUDED — only
branch-authored changes are in scope. Only `--base` (operator-supplied) overrides
detection.
</CRITICAL>

## 1.0 Phase 0 Prerequisite — Standards Must Already Be Loaded

<CRITICAL>
**A review cannot catch violations of rules it has not read.** Phase 0 (load +
catalogue the standards) runs BEFORE this planning phase resolves any target or
computes any diff. Confirm before proceeding:

1. **The repo's standards docs were discovered + read** (they vary per repo — FIND
   them): `docs/coding-standards.md`, `docs/ai/testing-instructions.md`,
   `docs/code-review-instructions.md`, the repo ROOT `AGENTS.md` AND every
   subdirectory `AGENTS.md` covering a changed path, plus any other referenced
   standards (CONTRIBUTING, style guides, lint config). Absent doc → noted; extra
   standards → also loaded.
2. **The operator's global rules were read**: `~/.claude-work/CLAUDE.md`,
   `~/.claude/AGENTS.md`, and the operator memory index
   (`~/.claude-work/projects/<project-encoded>/memory/MEMORY.md` + linked files).
3. **A concrete, NAMED rule catalogue was extracted** (rule IDs/names like
   `SEC-001`, `TEST-003`/`TEST-004`, `MODEL-008`, `PY-005`, `CODE-009`, plus global
   rules such as terse-code-no-verbose-docstrings, naive-datetimes-by-design,
   no-PII-logging, no-`mock.patch`-of-internals). The Phase 3 deep review holds every
   line against THIS catalogue; each finding names the specific rule (document +
   id/name) it violates, or is a named correctness/logic bug.

If Phase 0 has NOT run, STOP and run it now — do not resolve the target or compute
the diff against an empty rule catalogue. **Canonical order:** Phase 0 (load +
catalogue standards) → branch diff (three-dot merge-base vs DETECTED target) → read
every line → hold each block against the named catalogue → report findings naming
the specific rule.
</CRITICAL>

## 1.1 Target Resolution

Detect the merge target (don't assume), fetch it, then resolve to concrete refs:

```python
def detect_base(explicit_base: str | None) -> str:
    """Detect the merge target. Explicit --base wins; else PR base; else origin/main|master."""
    if explicit_base:
        return explicit_base
    pr_base = git_safe("pr", "view", "--json", "baseRefName", "--jq", ".baseRefName")  # via gh
    if pr_base:
        return f"origin/{pr_base}"
    for candidate in ("origin/main", "origin/master"):
        if ref_exists(candidate):
            return candidate
    raise RuntimeError("E_NO_BASE: could not detect merge target; pass --base")

def resolve_target(target: str, base_arg: str | None = None) -> dict:
    """
    Resolve target to branch/SHA info. Base is DETECTED, not assumed.

    Returns:
        {"branch": str, "head_sha": str, "base": str, "merge_base_sha": str}
    """
    base = detect_base(base_arg)
    # Fetch so the merge-base is current (strip any origin/ prefix for the remote ref)
    remote_ref = base.split("origin/", 1)[-1]
    git("fetch", "origin", remote_ref)

    head_sha = git("rev-parse", target)
    merge_base = git("merge-base", base, target)   # three-dot semantics for the diff

    return {
        "branch": target,
        "head_sha": head_sha,
        "base": base,
        "merge_base_sha": merge_base,
    }
```

**Error Handling:**

| Error | Cause | Recovery |
|-------|-------|----------|
| E_TARGET_NOT_FOUND | Invalid branch/PR | List similar branches, exit |
| E_MERGE_BASE_FAILED | Detached HEAD, shallow clone | Fallback to HEAD~10, warn |
| E_NO_DIFF | Branch identical to base | Info message, exit clean |

## 1.2 Diff Acquisition

Get changed files from merge base (THREE-dot — branch-authored changes only,
merged-in target commits excluded):

```bash
# Local mode
git diff --name-only $MERGE_BASE...$HEAD_SHA

# PR mode (via MCP)
pr_files(pr_result)  # Returns [{path, status}, ...]
```

Every file listed here is in scope and MUST be read line-by-line in Phase 3 — the
risk categorization below sets review ORDER, never license to skip or sample any file.

## 1.3 Risk Categorization

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

## 1.4 Complexity Estimation

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

## 1.5 Risk-Weighted Scope

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

## 1.6 Priority Ordering

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

## 1.7 Output: review-manifest.json

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

## 1.8 Output: review-plan.md

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

## Phase 1 Self-Check

Before proceeding to Phase 2:

- [ ] Phase 0 ran: standards docs discovered + read, operator global rules read, NAMED rule catalogue extracted (review cannot flag rules it never loaded)
- [ ] Target resolved to valid branch/SHA
- [ ] Merge target DETECTED (not hardcoded) and fetched; base recorded in manifest
- [ ] Merge base computed via three-dot / merge-base (or fallback documented)
- [ ] Files categorized by risk
- [ ] Complexity estimate calculated
- [ ] review-manifest.json written
- [ ] review-plan.md written

<CRITICAL>
If any self-check fails, STOP and report the issue. Do not proceed with incomplete planning.
</CRITICAL>
