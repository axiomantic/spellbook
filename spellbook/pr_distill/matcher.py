"""Pattern matching for PR distillation.

Applies heuristic patterns to file diffs to categorize changes.
Ported from lib/pr-distill/matcher.js.
"""

from typing import Optional

from .patterns import Pattern
from .types import FileDiff, PatternMatch


def check_pattern_match(pattern: Pattern, file: FileDiff) -> Optional[dict]:
    """Check if a pattern matches a file.

    Args:
        pattern: Pattern definition to test
        file: FileDiff object to match against

    Returns:
        Match result with lines list, or None if no match
    """
    # Check file path pattern
    file_matches = True
    if pattern.match_file is not None:
        file_matches = bool(pattern.match_file.search(file["path"]))

    if not file_matches:
        return None

    # If pattern has line matcher, check lines
    if pattern.match_line is not None:
        matched_lines: list[tuple[str, int]] = []

        for hunk in file.get("hunks", []):
            for line in hunk.get("lines", []):
                # Only match add or remove lines, not context
                if line["type"] == "context":
                    continue

                if pattern.match_line.search(line["content"]):
                    # Use new_line_num for adds, old_line_num for removes
                    line_num = (
                        line["new_line_num"]
                        if line["type"] == "add"
                        else line["old_line_num"]
                    )
                    matched_lines.append((file["path"], line_num))

        # If we have a line matcher but no lines matched, return None
        if len(matched_lines) == 0:
            return None

        return {"lines": matched_lines}

    # File-only pattern matched
    return {"lines": []}


def sort_patterns_by_precedence(
    patterns: list[Pattern],
    blessed_pattern_ids: list[str],
) -> list[Pattern]:
    """Sort patterns by precedence order.

    Order: always_review > blessed > high > medium

    Args:
        patterns: List of patterns to sort
        blessed_pattern_ids: Pattern IDs that should be elevated

    Returns:
        Sorted list of patterns
    """
    blessed_set = set(blessed_pattern_ids)

    always_review = []
    blessed = []
    high = []
    medium = []

    other = []

    for pattern in patterns:
        if pattern.priority == "always_review":
            always_review.append(pattern)
        elif pattern.id in blessed_set:
            blessed.append(pattern)
        elif pattern.priority == "high":
            high.append(pattern)
        elif pattern.priority == "medium":
            medium.append(pattern)
        else:
            # Unknown priority - append at lowest precedence
            other.append(pattern)

    return always_review + blessed + high + medium + other


def match_patterns(
    files: list[FileDiff],
    patterns: list[Pattern],
    blessed_pattern_ids: list[str] = None,
) -> dict:
    """Match patterns against a list of file diffs.

    For each file, finds the first matching pattern in precedence order.
    First match wins for a given file.

    Args:
        files: List of FileDiff objects to analyze
        patterns: List of patterns to match against
        blessed_pattern_ids: Pattern IDs to elevate in precedence

    Returns:
        Dict with "matched" (dict of pattern_id -> PatternMatch) and
        "unmatched" (list of FileDiff)
    """
    if blessed_pattern_ids is None:
        blessed_pattern_ids = []

    sorted_patterns = sort_patterns_by_precedence(patterns, blessed_pattern_ids)

    matched: dict[str, PatternMatch] = {}
    unmatched: list[FileDiff] = []

    for file in files:
        file_matched = False

        for pattern in sorted_patterns:
            result = check_pattern_match(pattern, file)

            if result is not None:
                file_matched = True

                # Add to or create pattern match entry
                if pattern.id not in matched:
                    matched[pattern.id] = PatternMatch(
                        pattern_id=pattern.id,
                        confidence=pattern.confidence,
                        matched_files=[file["path"]],
                        matched_lines=result["lines"],
                        first_occurrence_file=file["path"],
                    )
                else:
                    existing = matched[pattern.id]
                    existing["matched_files"].append(file["path"])
                    existing["matched_lines"].extend(result["lines"])

                # First matching pattern wins for this file
                break

        if not file_matched:
            unmatched.append(file)

    return {"matched": matched, "unmatched": unmatched}
