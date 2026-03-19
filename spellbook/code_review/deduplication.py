"""Deduplication for code-review findings.

Merges duplicate findings at the same location, keeping highest severity
and concatenating descriptions.
"""

from .models import Finding, Severity


# Severity ordering: CRITICAL > IMPORTANT > MINOR
_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.IMPORTANT: 1,
    Severity.MINOR: 2,
}


def _dedup_key(finding: Finding) -> str:
    """Generate deduplication key for a finding.

    Key format: {file}:{line}

    Args:
        finding: Finding to generate key for

    Returns:
        Deduplication key string
    """
    return f"{finding.file}:{finding.line}"


def _merge_findings(findings: list[Finding]) -> Finding:
    """Merge multiple findings at the same location.

    - Takes highest severity
    - Concatenates descriptions
    - Keeps first non-None suggestion
    - Preserves first finding's code_snippet and line_end

    Args:
        findings: List of findings to merge (must be non-empty)

    Returns:
        Merged Finding
    """
    if len(findings) == 1:
        return findings[0]

    # Sort by severity (highest first)
    sorted_findings = sorted(
        findings,
        key=lambda f: _SEVERITY_ORDER.get(f.severity, 99),
    )

    # Use highest severity
    best = sorted_findings[0]

    # Concatenate all descriptions
    descriptions = [f.description for f in findings]
    merged_description = " | ".join(descriptions)

    # Find first non-None suggestion
    suggestion = None
    for f in findings:
        if f.suggestion is not None:
            suggestion = f.suggestion
            break

    # Preserve first finding's other fields
    first = findings[0]

    return Finding(
        severity=best.severity,
        file=first.file,
        line=first.line,
        description=merged_description,
        line_end=first.line_end,
        suggestion=suggestion,
        code_snippet=first.code_snippet,
    )


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Deduplicate findings by location, merging duplicates.

    Findings at the same file:line are merged:
    - Highest severity is kept
    - Descriptions are concatenated
    - First non-None suggestion is kept

    Args:
        findings: List of findings to deduplicate

    Returns:
        Deduplicated list of findings
    """
    if not findings:
        return []

    # Group by dedup key
    groups: dict[str, list[Finding]] = {}
    for finding in findings:
        key = _dedup_key(finding)
        if key not in groups:
            groups[key] = []
        groups[key].append(finding)

    # Merge each group
    result = []
    for group in groups.values():
        merged = _merge_findings(group)
        result.append(merged)

    return result
