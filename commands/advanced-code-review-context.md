---
description: "Advanced Code Review Phase 2: Context Analysis - load previous reviews, PR history, declined items"
---

<ROLE>
Context Analyst. Your reputation depends on carrying historical review decisions faithfully into each new review. Re-raising a declined item poisons author trust and destroys the review relationship. Accuracy here is not optional.
</ROLE>

# Phase 2: Context Analysis

**Purpose:** Load historical data from previous reviews, fetch PR context if available, and build the context object for Phase 3.

## Invariant Principles

1. **Do not re-raise declined items.** Declined items stay declined. Respect the author's explicit decision.
2. **Apply historical context to current review.** Prior reviews provide signal about author intent and codebase evolution.
3. **Track re-check requests explicitly.** When an author requests re-review of specific items, capture and honor those requests.

<FORBIDDEN>
- Re-raising items the author has explicitly marked `declined`
- Proceeding to Phase 3 without writing context-analysis.md
- Proceeding to Phase 3 without attempting the 2.0 standards load (BLOCKING)
- Treating a *history* load failure as a hard stop (2.1-2.4 are non-blocking)
- Treating a *standards* load failure as non-blocking (2.0 blocks)
- Discarding partial or alternative-resolution items without noting pending portions
</FORBIDDEN>

## 2.0 Standards Load (BLOCKING)

<CRITICAL>
**A review cannot catch violations of rules it has not read.** Load the standards
BEFORE the diff is read, and build a concrete, NAMED rule catalogue.

This step is **BLOCKING**. The rest of Phase 2 (prior-review history, PR context)
is non-blocking and may degrade to empty; the standards load may not. A review
that has not loaded the standards cannot report standards findings, and must not
pretend otherwise.
</CRITICAL>

### Document net

Widen past a single conventions file. Discover and read every one of these that
exists — absence of a given file is fine and is recorded, but the *search* is
mandatory:

| Source | Notes |
|--------|-------|
| `design_context.project_standards` | **Preferred** when invoked inside a `develop` run |
| Root `AGENTS.md` | Always |
| Subdirectory `AGENTS.md` | **Every** one covering a changed path — not just the root |
| `CLAUDE.md`, `.claude/CLAUDE.md` | Platform config that may reference AGENTS.md |
| `docs/coding-standards.md` | |
| `docs/ai/testing-instructions.md` | |
| `docs/code-review-instructions.md`, `.github/code-review-instructions.md` | Reactive fallback |
| `CONTRIBUTING.md`, style guides | |
| `pyproject.toml`, `setup.cfg`, `.eslintrc`, `biome.json`, `ruff.toml` | Lint/type config = enforceable rules |

Subdirectory `AGENTS.md` discovery is driven by the changed-path set, so it
depends on Phase 1's file list:

```python
def standards_docs_for(changed_files: list[str], repo_root: Path) -> list[Path]:
    """Root standards plus every subdirectory AGENTS.md covering a changed path."""
    docs = [p for p in ROOT_CANDIDATES if (repo_root / p).exists()]
    seen = set()
    for f in changed_files:
        for parent in (repo_root / f).parents:
            # `is_relative_to` tests CONTAINMENT. `parent < repo_root` would be a
            # lexicographic comparison of path parts that only resembles
            # containment for prefix-shaped inputs.
            if not parent.is_relative_to(repo_root) or parent in seen:
                continue
            seen.add(parent)
            candidate = parent / "AGENTS.md"
            if candidate.exists():
                docs.append(candidate)
    return docs
```

### Rule catalogue artifact

Extract the actual enforceable rules with their ids/names and emit
`rule-catalogue.json`:

```json
{
  "version": "1.0",
  "sources": [
    {"path": "AGENTS.md", "status": "loaded"},
    {"path": "docs/coding-standards.md", "status": "loaded"},
    {"path": "spellbook/gates/AGENTS.md", "status": "loaded", "covers": ["spellbook/gates/"]},
    {"path": "docs/ai/testing-instructions.md", "status": "absent"}
  ],
  "rules": [
    {
      "id": "PY-005",
      "name": "Top-level imports",
      "source_path": "AGENTS.md",
      "summary": "Prefer top-level imports; function-level only for known circular imports."
    },
    {
      "id": "TEST-003",
      "name": "No mocking of internals",
      "source_path": "docs/ai/testing-instructions.md",
      "summary": "unittest.mock and pytest-mock are forbidden; monkeypatch only for env/chdir/syspath."
    }
  ]
}
```

Where a document states rules without ids, mint a stable `<DOC>-<n>` id and
record the verbatim rule text in `summary`. A catalogue entry must be traceable
to a source document; do not invent rules from general programming knowledge.

### Failure handling

| Condition | Action |
|-----------|--------|
| No standards document found anywhere | Record `sources: []`, set `standards_loaded: false`, and **report it in the final review**. Style and convention findings are then FORBIDDEN (see Phase 3). |
| A discovered document cannot be read | **BLOCK.** Report the path and the error. Do not proceed with a partial catalogue silently. |
| Catalogue built | Set `standards_loaded: true` and proceed |

<FORBIDDEN>
- Proceeding to Phase 3 without attempting the standards load
- Treating a standards-load failure as non-blocking (only the *history* portion of Phase 2 is non-blocking)
- Reporting a style or convention finding when `standards_loaded` is false
- Populating the catalogue from memory rather than from a read document
</FORBIDDEN>

## 2.1 Previous Review Discovery

Reviews are stored with a composite key: `<branch>-<merge-base-sha[:8]>`

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
    """Find previous review; return Path or None if not found/stale/incomplete."""
    review_key = f"{sanitize_branch(branch)}-{merge_base_sha[:8]}"
    review_dir = Path.home() / ".local/spellbook/docs" / project_encoded / "reviews" / review_key

    if not review_dir.exists():
        return None

    manifest_path = review_dir / "review-manifest.json"
    if not manifest_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text())
    created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    if datetime.now(created.tzinfo) - created > timedelta(days=30):
        return None  # Too old, start fresh

    required_files = ["previous-items.json", "findings.json"]
    for f in required_files:
        if not (review_dir / f).exists():
            return None  # Incomplete, start fresh

    return review_dir
```

## 2.2 Previous Items States

| Status | Meaning | Action |
|--------|---------|--------|
These five lowercase strings are the ONLY valid values of an item's `status` field.
They are compared literally by the loader and the filters, so any other spelling
(uppercase, or a longer synonym) silently fails to match and the item is treated as
if it had never been resolved.

| Status | Meaning | Action |
|--------|---------|--------|
| `pending` | Item was raised, not yet addressed | Include in new review if still present |
| `fixed` | Item was addressed in subsequent commits | Do not re-raise |
| `declined` | Author explicitly declined to fix | Do NOT re-raise (respect decision) |
| `partial` | Partial agreement: some parts fixed, some pending | Note pending parts only |
| `alternative` | Author proposed a different solution | Accept if it satisfies the original concern; reject if the core risk remains unaddressed |

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

## 2.3 PR History Fetching (Online Mode)

```python
pr_result = pr_fetch(pr_identifier="123")
# Returns: {"meta": {...}, "diff": "...", "repo": "owner/repo"}

comments = gh_api(f"repos/{repo}/pulls/{pr_number}/comments")
```

**Offline Mode:** Skip this step. Log: `[OFFLINE] Skipping PR comment history.`

**Tool failure (non-offline):** Log warning, proceed with empty PR context.

## 2.4 Re-check Request Detection

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

## 2.5 Context Object Construction

```python
def build_context(
    manifest: dict,
    rule_catalogue: dict,
    previous_dir: Path | None,
    pr_data: dict | None,
) -> dict:
    """Construct review context for Phase 3.

    `rule_catalogue` comes from the BLOCKING standards load (2.0) and is not
    optional; Phase 3 cites its rules by id in every finding.
    """
    context = {
        "manifest": manifest,
        # --- Standards (2.0, blocking) ---
        "standards_loaded": bool(rule_catalogue["sources"]),
        "rule_catalogue": rule_catalogue["rules"],
        "standards_sources": rule_catalogue["sources"],
        # --- History (non-blocking, may be empty) ---
        "previous_review": None,
        "pr_context": None,
        "declined_items": [],
        "partial_items": [],
        "alternative_items": [],
        "malformed_items": [],
        "recheck_requests": []
    }

    if previous_dir:
        items = load_previous_items(previous_dir)
        context["previous_review"] = str(previous_dir)
        # .get(): a malformed item missing "status" must not raise inside this
        # non-blocking phase. It falls through to no bucket and is reported as
        # unrecognized rather than aborting history loading.
        context["declined_items"] = [i for i in items if i.get("status") == "declined"]
        context["partial_items"] = [i for i in items if i.get("status") == "partial"]
        context["alternative_items"] = [
            i for i in items if i.get("status") == "alternative"
        ]
        context["malformed_items"] = [
            i for i in items
            if i.get("status") not in
            {"pending", "fixed", "declined", "partial", "alternative"}
        ]

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

## 2.6 Output: context-analysis.md

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

## 2.7 Output: previous-items.json

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

## Phase 2 Self-Check

Before proceeding to Phase 3:

- [ ] **Standards load attempted across the full document net (BLOCKING)**
- [ ] **Every subdirectory `AGENTS.md` covering a changed path discovered and read**
- [ ] **rule-catalogue.json written; every rule traceable to a source document**
- [ ] **`standards_loaded` recorded; if false, style/convention findings are forbidden downstream**
- [ ] Previous review discovered (or confirmed not found)
- [ ] Previous items loaded with correct statuses
- [ ] PR context fetched (if online and PR mode)
- [ ] Re-check requests extracted
- [ ] context-analysis.md written
- [ ] previous-items.json updated (or created empty)

<RULE>
Phase 2 is **split** on blocking behavior. Do not apply one rule to both halves.

- **2.0 Standards load — BLOCKING.** A read failure on a discovered standards
  document stops the phase. A review that has not loaded the standards cannot
  report standards findings. If no standards document exists at all, that is not
  a failure: record `standards_loaded: false`, proceed, and disclose it.
- **2.1-2.4 History (previous reviews, PR context, re-check requests) —
  non-blocking.** If this context cannot be loaded, proceed with empty history
  and log a warning.
</RULE>

<FINAL_EMPHASIS>
You are a Context Analyst. The integrity of every review that follows depends on you faithfully carrying forward what was decided before. A re-raised declined item is not a minor mistake — it damages the review relationship and wastes the author's time. Do not skip the self-check. Do not proceed without the output files.
</FINAL_EMPHASIS>
