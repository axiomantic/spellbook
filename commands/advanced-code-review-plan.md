---
description: "Advanced Code Review Phase 1: Strategic Planning - scope analysis, risk categorization, priority ordering"
---

# Phase 1: Strategic Planning

## Invariant Principles

1. **Risk-based prioritization**: Higher risk files are reviewed first. Security, payment, and migration files take precedence over tests and documentation.
2. **Scope clarity**: All files in scope must be identified before review starts. No file should be discovered mid-review.
3. **Complexity honesty**: Estimates must reflect actual review effort required. Underestimating leads to rushed reviews; overestimating wastes planning time.

**Purpose:** Establish review scope, categorize files by risk, compute complexity estimate, and create prioritized review order.

## 1.1 Target Resolution

<CRITICAL>
The base is **DETECTED, never assumed**. Do not hardcode a default-branch name
(the usual two), bare or remote-qualified, here or anywhere downstream. Delegate
to `branch-context.sh` / `branch-context.py`, which fetch before computing the
merge base and report how the target was resolved.
</CRITICAL>

```bash
# Single source of truth for base, merge base, and provenance.
"$SPELLBOOK_DIR/scripts/branch-context.sh" json
```

That emits, among other fields:

| Field | Meaning |
|-------|---------|
| `merge_target` | Detected base branch — never a hardcoded literal |
| `merge_base` | Common ancestor SHA |
| `base_ref` | The concrete ref the base was computed against |
| `resolved_via` | `pr-base-ref` / `upstream-tracking` / `remote-head` / `fallback-literal` |
| `fetch` | `ok`, `skipped (...)`, or `FAILED (...) - merge base may be STALE` |
| `detached_head` | True when HEAD has no branch identity |

```python
def resolve_target(target: str, base: str | None = None) -> dict:
    """
    Resolve target to branch/SHA info.

    `base` is an OPTIONAL explicit override. When it is None (the normal case)
    the base is detected by branch-context, NOT defaulted to a literal.

    Returns:
        {
            "branch": str,          # Branch name
            "head_sha": str,        # HEAD commit SHA
            "base": str,            # Detected (or overridden) base branch
            "base_ref": str,        # Concrete ref used
            "merge_base_sha": str,  # Common ancestor
            "resolved_via": str,    # How the base was determined
            "fetch": str,           # Fetch status before merge-base
            "detached_head": bool
        }
    """
    ctx = json.loads(sh(f'"{SPELLBOOK_DIR}/scripts/branch-context.sh" json'))
    head_sha = git("rev-parse", target)

    if base is not None:
        # Explicit override: recompute against it and SAY it was overridden.
        return {
            "branch": target,
            "head_sha": head_sha,
            "base": base,
            "base_ref": base,
            "merge_base_sha": git("merge-base", base, target),
            "resolved_via": "explicit-override",
            "fetch": ctx["fetch"],
            "detached_head": ctx["detached_head"],
            # E_NO_DIFF is keyed on the COMMITTED count. `files_changed` is the
            # working-tree number and would let a 0-commit branch look reviewable.
            "files_changed_committed": ctx["files_changed_committed"],
        }

    return {
        "branch": ctx["branch"],
        "head_sha": head_sha,
        "base": ctx["merge_target"],
        "base_ref": ctx["base_ref"],
        "merge_base_sha": ctx["merge_base"],
        "resolved_via": ctx["resolved_via"],
        "fetch": ctx["fetch"],
        "detached_head": ctx["detached_head"],
        "files_changed_committed": ctx["files_changed_committed"],
    }


def check_no_diff(preflight: dict) -> None:
    """E_NO_DIFF, keyed on the COMMITTED endpoint."""
    if preflight["files_changed_committed"] == 0:
        raise SystemExit(
            "E_NO_DIFF: nothing is committed ahead of "
            f"{preflight['base']}. There is nothing to review."
        )
```

**Error Handling:**

| Error | Cause | Recovery |
|-------|-------|----------|
| E_TARGET_NOT_FOUND | Invalid branch/PR | List similar branches, exit |
| E_MERGE_BASE_FAILED | Shallow clone, unrelated histories | Report the failure and STOP. Never silently substitute a different base. |
| E_NO_DIFF | `files_changed_committed` is 0 -- nothing is committed ahead of the base | Info message, exit clean. Key this on `files_changed_committed`, NEVER on `files_changed`: the latter counts the WORKING TREE, so a branch with 0 commits and dirty files reads as a reviewable diff and the review proceeds to build an empty manifest. |
| E_DETACHED_HEAD | `detached_head` is true | Proceed only with an explicit `--base`; otherwise report and STOP |
| W_STALE_BASE | `fetch` is not `ok` | Proceed, but flag the base as possibly stale in the manifest and report |
| W_GUESSED_BASE | `resolved_via` is `fallback-literal` | Proceed, but flag prominently — the base was GUESSED, not detected |

## 1.2 Diff Acquisition

<CRITICAL>
ENDPOINT is a separate decision from BASE. This phase plans a review of **what
will merge**, so it uses the committed-only endpoint. Use `diff` (working tree
included) only for a pre-commit self-review or when describing the branch for a
changelog/PR body. State which endpoint was used.
</CRITICAL>

```bash
# Local mode - committed only (reviewing what will merge).
# The file list and the diff MUST share one endpoint. Pairing `files`
# (working tree) with `diff-committed` builds a coverage manifest of files
# that the diff does not contain, so reconcile_coverage can certify N-of-N
# against zero hunks.
"$SPELLBOOK_DIR/scripts/branch-context.sh" files-committed
"$SPELLBOOK_DIR/scripts/branch-context.sh" diff-committed

# PR mode (via gh CLI)
# gh pr view <PR_NUMBER> --json files  # Returns [{path, additions, deletions, status}, ...]
```

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

## 1.6.1 Coverage Manifest (per-hunk)

<CRITICAL>
Build the coverage manifest from ALL changed hunks **BEFORE** review begins. A
manifest built during or after review is not a manifest — it is a record of what
you happened to read. Phase 3 reconciles against it and reports N-of-N.

`priority_order` is already a file-level manifest; it has simply never been
reconciled. The coverage manifest extends it to hunk granularity and makes
reconciliation mandatory.
</CRITICAL>

Enumerate every hunk in the diff. Each hunk gets a stable id and starts unread:

```python
def build_coverage_manifest(diff: str, priority_order: list[str]) -> dict:
    """Enumerate every hunk so coverage is COUNTABLE, not asserted."""
    units = []
    for file_path in priority_order:                 # highest risk first
        for hunk in hunks_of(diff, file_path):       # @@ -a,b +c,d @@
            units.append({
                "id": f"{file_path}#{hunk.new_start}-{hunk.new_end}",
                "file": file_path,
                "start_line": hunk.new_start,
                "end_line": hunk.new_end,
                "lines": hunk.line_count,
                "reviewed": False,       # Phase 3 flips this
                "skipped_reason": None,  # non-null REQUIRES disclosure
            })
    return {
        "total_files": len(priority_order),
        "total_hunks": len(units),
        "total_lines": sum(u["lines"] for u in units),
        "units": units,
    }
```

<FORBIDDEN>
- Using grep, ripgrep, or any search as a substitute for reading a hunk. Grep
  **LOCATES**; it never **COVERS**. A hunk is `reviewed` only after its lines
  were read.
- Sampling ("I read the hot files", "the rest is boilerplate") and marking the
  remainder reviewed.
- Marking a hunk reviewed because its file was opened.
- Building the manifest after review instead of before.
</FORBIDDEN>

### Chunked dispatch (the consumer of the size thresholds)

`SUBAGENT_THRESHOLD_FILES` and `LARGE_DIFF_LINES` govern this step. When the
diff exceeds either threshold, 100% of the manifest is **assigned** across
subagents — partitioned, never sampled:

```python
def plan_chunks(manifest: dict, cfg: dict) -> list[list[dict]]:
    """Partition coverage units across subagents. Every unit lands in exactly one chunk."""
    if (manifest["total_files"] <= cfg["SUBAGENT_THRESHOLD_FILES"]
            and manifest["total_lines"] <= cfg["LARGE_DIFF_LINES"]):
        return [manifest["units"]]                    # single reviewer

    chunks, current, budget = [], [], 0
    for unit in manifest["units"]:                    # already priority-ordered
        if current and budget + unit["lines"] > cfg["LARGE_DIFF_LINES"]:
            chunks.append(current)
            current, budget = [], 0
        current.append(unit)
        budget += unit["lines"]
    if current:
        chunks.append(current)

    # Partition invariant: nothing dropped, nothing duplicated.
    assert sum(len(c) for c in chunks) == manifest["total_hunks"]
    return chunks
```

Write the manifest to `coverage-manifest.json` alongside the other Phase 1
artifacts. Phase 3 cannot pass its self-check without it.

## 1.7 Output: review-manifest.json

```json
{
  "version": "1.0",
  "created_at": "2026-01-30T10:00:00Z",
  "target": {
    "branch": "feature/auth-refactor",
    "base": "<detected-base-branch>",
    "base_ref": "<remote>/<detected-base-branch>",
    "merge_base_sha": "abc12345",
    "head_sha": "def67890",
    "resolved_via": "pr-base-ref",
    "fetch": "ok",
    "detached_head": false,
    "endpoint": "committed-only"
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
**Base:** <detected-base-branch> @ abc12345 (resolved via pr-base-ref, fetch ok)
**Endpoint:** committed-only (reviewing what will merge)
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

- [ ] Target resolved to valid branch/SHA
- [ ] Base DETECTED via `branch-context.sh` — no hardcoded base literal anywhere
- [ ] `resolved_via` and `fetch` recorded; `fallback-literal` or non-`ok` fetch flagged
- [ ] Endpoint (committed-only vs. working tree) chosen deliberately and recorded
- [ ] Merge base computed (or failure reported and STOPPED — never silently substituted)
- [ ] Files categorized by risk
- [ ] Coverage manifest built from ALL hunks BEFORE review, `reviewed: false` throughout
- [ ] Chunk plan produced when thresholds exceeded; partition invariant asserted
- [ ] Complexity estimate calculated
- [ ] review-manifest.json written
- [ ] coverage-manifest.json written
- [ ] review-plan.md written

<CRITICAL>
If any self-check fails, STOP and report the issue. Do not proceed with incomplete planning.
</CRITICAL>
