"""MCP tools for PR distillation."""

__all__ = [
    "pr_fetch",
    "pr_diff",
    "pr_files",
    "pr_match_patterns",
    "pr_bless_pattern",
    "pr_list_patterns",
]

from spellbook.mcp.server import mcp
from spellbook.sessions.injection import inject_recovery_context
from spellbook.pr_distill.bless import (
    bless_pattern as do_bless_pattern,
    list_blessed_patterns,
)
from spellbook.pr_distill.config import load_config as load_pr_config
from spellbook.pr_distill.fetch import fetch_pr as do_fetch_pr, parse_pr_identifier
from spellbook.pr_distill.matcher import match_patterns
from spellbook.pr_distill.parse import parse_diff
from spellbook.pr_distill.patterns import BUILTIN_PATTERNS


@mcp.tool()
@inject_recovery_context
def pr_fetch(pr_identifier: str) -> dict:
    """
    Fetch PR metadata and diff from GitHub.

    Args:
        pr_identifier: PR number or full GitHub PR URL

    Returns:
        {
            "meta": {...PR metadata...},
            "diff": "...raw diff...",
            "repo": "owner/repo"
        }

    Raises:
        PRDistillError for authentication, network, or not-found errors
    """
    parsed = parse_pr_identifier(pr_identifier)
    result = do_fetch_pr(parsed)

    # Spotlight-wrap the diff (external content from GitHub)
    try:
        from spellbook.core.config import config_get
        from spellbook.security.spotlight import spotlight_wrap
        if config_get("security.spotlighting.enabled"):
            diff = result.get("diff", "")
            if diff:
                result["diff"] = spotlight_wrap(diff, "pr_fetch", tier="standard")
    except ImportError:
        pass  # Fail-open: spotlighting module not available

    return result


@mcp.tool()
@inject_recovery_context
def pr_diff(raw_diff: str) -> dict:
    """
    Parse unified diff into FileDiff objects.

    Args:
        raw_diff: Raw unified diff string (e.g., from git diff or gh pr diff)

    Returns:
        {
            "files": [FileDiff objects],
            "warnings": [parse warning messages]
        }
    """
    return parse_diff(raw_diff)


@mcp.tool()
@inject_recovery_context
def pr_files(pr_result: dict) -> list:
    """
    Extract file list from pr_fetch result.

    Args:
        pr_result: Result from pr_fetch containing meta.files

    Returns:
        List of file dicts with path and status (added/deleted/modified)
    """
    files = pr_result.get("meta", {}).get("files", [])
    result = []

    for f in files:
        path = f.get("path", "")
        additions = f.get("additions", 0)
        deletions = f.get("deletions", 0)

        # Determine status based on additions/deletions
        if additions > 0 and deletions == 0:
            status = "added"
        elif deletions > 0 and additions == 0:
            status = "deleted"
        else:
            status = "modified"

        result.append({
            "path": path,
            "additions": additions,
            "deletions": deletions,
            "status": status,
        })

    return result


@mcp.tool()
@inject_recovery_context
def pr_match_patterns(
    files: list,
    project_root: str,
    custom_patterns: list = None,
) -> dict:
    """
    Match heuristic patterns against file diffs.

    Args:
        files: List of FileDiff objects to analyze
        project_root: Absolute path to project root for config loading
        custom_patterns: Optional list of additional patterns

    Returns:
        {
            "matched": {pattern_id: PatternMatch},
            "unmatched": [FileDiff objects],
            "patterns_checked": int
        }
    """
    # Load blessed patterns from config
    config = load_pr_config(project_root)
    blessed_pattern_ids = config.get("blessed_patterns", [])

    # Combine builtin patterns with any custom patterns
    patterns = list(BUILTIN_PATTERNS)
    if custom_patterns:
        patterns.extend(custom_patterns)

    # Match patterns
    result = match_patterns(files, patterns, blessed_pattern_ids)

    return {
        "matched": result["matched"],
        "unmatched": result["unmatched"],
        "patterns_checked": len(patterns),
    }


@mcp.tool()
@inject_recovery_context
def pr_bless_pattern(project_root: str, pattern_id: str) -> dict:
    """
    Bless a pattern for elevated precedence.

    Args:
        project_root: Absolute path to project root
        pattern_id: Pattern ID to bless (2-50 chars, lowercase/numbers/hyphens)

    Returns:
        {
            "success": True/False,
            "pattern_id": str,
            "already_blessed": bool (if already in list),
            "error": str (if validation failed)
        }
    """
    # Check if already blessed first
    existing = list_blessed_patterns(project_root)
    already_blessed = pattern_id in existing

    # Call the blessing function
    result = do_bless_pattern(project_root, pattern_id)

    if result.get("success"):
        return {
            "success": True,
            "pattern_id": pattern_id,
            "already_blessed": already_blessed,
        }
    else:
        return {
            "success": False,
            "pattern_id": pattern_id,
            "error": result.get("error", "Unknown validation error"),
        }


@mcp.tool()
@inject_recovery_context
def pr_list_patterns(project_root: str = None) -> dict:
    """
    List all available patterns (builtin and blessed).

    Args:
        project_root: Optional path to project root for blessed patterns

    Returns:
        {
            "builtin": [pattern dicts with id, confidence, priority, description],
            "blessed": [pattern_id strings],
            "total": int
        }
    """
    # Convert builtin patterns to dicts (they're dataclass instances)
    builtin = [
        {
            "id": p.id,
            "confidence": p.confidence,
            "priority": p.priority,
            "description": p.description,
            "default_category": p.default_category,
        }
        for p in BUILTIN_PATTERNS
    ]

    # Get blessed patterns if project_root provided
    blessed = []
    if project_root:
        blessed = list_blessed_patterns(project_root)

    return {
        "builtin": builtin,
        "blessed": blessed,
        "total": len(builtin) + len(blessed),
    }
