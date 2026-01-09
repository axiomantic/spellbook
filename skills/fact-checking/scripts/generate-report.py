#!/usr/bin/env python3
"""
Generate fact-checking report from verification findings.

Usage:
    python generate-report.py <findings.json> [--output report.md]
    python generate-report.py <findings.json> --format json

Input: JSON file with verification findings.
Output: Markdown report or JSON summary.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERDICT_EMOJI = {
    "verified": "✅",
    "refuted": "❌",
    "inconclusive": "❓",
    "ambiguous": "⚠️",
    "misleading": "⚠️",
    "jargon-heavy": "📚",
    "stale": "🕐",
}

VERDICT_ORDER = [
    "refuted",
    "misleading",
    "inconclusive",
    "ambiguous",
    "jargon-heavy",
    "stale",
    "verified",
]

CATEGORY_ORDER = [
    "security",
    "correctness",
    "performance",
    "concurrency",
    "configuration",
    "documentation",
    "historical",
    "unknown",
]


def format_bibliography_entry(source: dict, index: int) -> str:
    """Format a single bibliography entry."""
    source_type = source.get("type", "unknown")

    if source_type == "code_trace":
        return f"[{index}] Code trace: {source['file']}:{source.get('lines', '')} - {source.get('description', '')}"

    elif source_type == "test":
        return f"[{index}] Test: {source['command']} - {source.get('result', '')}"

    elif source_type == "web":
        excerpt = source.get('excerpt', '')
        if excerpt:
            excerpt = f' - "{excerpt[:100]}..."' if len(excerpt) > 100 else f' - "{excerpt}"'
        return f"[{index}] {source.get('title', 'Web source')} - {source['url']}{excerpt}"

    elif source_type == "git":
        return f"[{index}] Git: {source.get('reference', '')} - {source.get('description', '')}"

    elif source_type == "docs":
        return f"[{index}] Docs: {source.get('source', '')} - {source.get('section', '')} - {source.get('url', '')}"

    elif source_type == "benchmark":
        return f"[{index}] Benchmark: {source.get('method', '')} - {source.get('results', '')}"

    elif source_type == "rfc":
        return f"[{index}] {source.get('citation', '')} - {source.get('section', '')} - {source.get('url', '')}"

    else:
        return f"[{index}] {source.get('description', str(source))}"


def generate_markdown_report(
    findings: list[dict],
    scope: dict,
    bibliography: list[dict],
) -> str:
    """Generate markdown report from findings."""

    # Count by verdict
    verdict_counts = defaultdict(int)
    for f in findings:
        verdict_counts[f.get("verdict", "unknown")] += 1

    total = len(findings)
    verified = verdict_counts.get("verified", 0)
    refuted = verdict_counts.get("refuted", 0)
    inconclusive = verdict_counts.get("inconclusive", 0)
    other = total - verified - refuted - inconclusive

    # Group by category
    by_category = defaultdict(list)
    for f in findings:
        by_category[f.get("category", "unknown")].append(f)

    # Build report
    lines = []

    # Header
    lines.append("# Factchecker Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Scope:** {scope.get('description', 'Unknown scope')}")
    lines.append(f"**Claims Found:** {total}")
    lines.append(f"**Verified:** {verified} | **Refuted:** {refuted} | **Inconclusive:** {inconclusive} | **Other:** {other}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Verdict | Count | Action Required |")
    lines.append("|---------|-------|-----------------|")

    action_map = {
        "verified": "None",
        "refuted": "Fix comments or code",
        "inconclusive": "Manual review needed",
        "ambiguous": "Clarify wording",
        "misleading": "Rewrite for accuracy",
        "jargon-heavy": "Simplify language",
        "stale": "Update or remove",
    }

    for verdict in VERDICT_ORDER:
        count = verdict_counts.get(verdict, 0)
        if count > 0:
            emoji = VERDICT_EMOJI.get(verdict, "")
            action = action_map.get(verdict, "Review")
            lines.append(f"| {emoji} {verdict.capitalize()} | {count} | {action} |")

    lines.append("")

    # Key findings
    if refuted > 0 or verdict_counts.get("stale", 0) > 0:
        lines.append("### Key Findings")
        lines.append("")
        if refuted > 0:
            lines.append(f"- **Accuracy:** {refuted} claim(s) are factually incorrect")
        if verdict_counts.get("stale", 0) > 0:
            lines.append(f"- **Maintenance:** {verdict_counts['stale']} outdated reference(s) found")
        if verdict_counts.get("misleading", 0) > 0:
            lines.append(f"- **Clarity:** {verdict_counts['misleading']} misleading claim(s) found")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Findings by category
    lines.append("## Findings by Category")
    lines.append("")

    for category in CATEGORY_ORDER:
        category_findings = by_category.get(category, [])
        if not category_findings:
            continue

        lines.append(f"### {category.capitalize()} ({len(category_findings)} claims)")
        lines.append("")

        # Sort by verdict order
        category_findings.sort(key=lambda f: VERDICT_ORDER.index(f.get("verdict", "unknown")) if f.get("verdict") in VERDICT_ORDER else 99)

        for finding in category_findings:
            verdict = finding.get("verdict", "unknown")
            emoji = VERDICT_EMOJI.get(verdict, "")
            claim_text = finding.get("claim", finding.get("text", "Unknown claim"))

            lines.append(f"#### {emoji} {verdict.upper()}: \"{claim_text[:80]}{'...' if len(claim_text) > 80 else ''}\"")
            lines.append(f"- **Location:** `{finding.get('file', 'unknown')}:{finding.get('line', '?')}`")

            if finding.get("original_comment"):
                lines.append(f"- **Claim:** `{finding['original_comment'][:200]}`")

            if finding.get("evidence"):
                lines.append(f"- **Evidence:** {finding['evidence']}")

            if finding.get("depth"):
                lines.append(f"- **Depth:** {finding['depth'].capitalize()}")

            if finding.get("correction"):
                lines.append(f"- **Correction:** {finding['correction']}")

            if finding.get("source_refs"):
                refs = ", ".join(f"[{r}]" for r in finding["source_refs"])
                lines.append(f"- **Sources:** {refs}")

            lines.append("")

        lines.append("---")
        lines.append("")

    # Bibliography
    if bibliography:
        lines.append("## Bibliography")
        lines.append("")
        for i, source in enumerate(bibliography, 1):
            lines.append(format_bibliography_entry(source, i))
        lines.append("")
        lines.append("---")
        lines.append("")

    # Implementation plan
    action_needed = [f for f in findings if f.get("verdict") not in ("verified", None)]
    if action_needed:
        lines.append("## Implementation Plan")
        lines.append("")

        # High priority - refuted
        refuted_findings = [f for f in action_needed if f.get("verdict") == "refuted"]
        if refuted_findings:
            lines.append("### High Priority (Refuted Claims)")
            lines.append("")
            lines.append("These claims are factually incorrect and should be fixed immediately.")
            lines.append("")
            for i, f in enumerate(refuted_findings, 1):
                lines.append(f"{i}. [ ] `{f.get('file', '?')}:{f.get('line', '?')}` - {f.get('claim', '')[:60]}")
                if f.get("correction"):
                    lines.append(f"   - **Suggested fix:** {f['correction']}")
            lines.append("")

        # Medium priority - misleading, stale
        medium_findings = [f for f in action_needed if f.get("verdict") in ("misleading", "stale")]
        if medium_findings:
            lines.append("### Medium Priority (Misleading/Stale)")
            lines.append("")
            lines.append("These claims may confuse readers or reference outdated information.")
            lines.append("")
            for i, f in enumerate(medium_findings, 1):
                lines.append(f"{i}. [ ] `{f.get('file', '?')}:{f.get('line', '?')}` - {f.get('claim', '')[:60]}")
                if f.get("correction"):
                    lines.append(f"   - **Suggested fix:** {f['correction']}")
            lines.append("")

        # Low priority - ambiguous, jargon
        low_findings = [f for f in action_needed if f.get("verdict") in ("ambiguous", "jargon-heavy")]
        if low_findings:
            lines.append("### Low Priority (Clarity Improvements)")
            lines.append("")
            lines.append("These claims could be improved for clarity.")
            lines.append("")
            for i, f in enumerate(low_findings, 1):
                lines.append(f"{i}. [ ] `{f.get('file', '?')}:{f.get('line', '?')}` - {f.get('claim', '')[:60]}")
                if f.get("correction"):
                    lines.append(f"   - **Suggested improvement:** {f['correction']}")
            lines.append("")

        # Requires manual review - inconclusive
        inconclusive_findings = [f for f in action_needed if f.get("verdict") == "inconclusive"]
        if inconclusive_findings:
            lines.append("### Requires Manual Review")
            lines.append("")
            lines.append("These claims could not be verified automatically.")
            lines.append("")
            for i, f in enumerate(inconclusive_findings, 1):
                lines.append(f"{i}. [ ] `{f.get('file', '?')}:{f.get('line', '?')}` - {f.get('claim', '')[:60]}")
                if f.get("blockers"):
                    lines.append(f"   - **Blocked by:** {f['blockers']}")
            lines.append("")

    return "\n".join(lines)


def generate_json_summary(
    findings: list[dict],
    scope: dict,
    bibliography: list[dict],
) -> dict:
    """Generate JSON summary from findings."""
    verdict_counts = defaultdict(int)
    for f in findings:
        verdict_counts[f.get("verdict", "unknown")] += 1

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "total_claims": len(findings),
        "verdicts": dict(verdict_counts),
        "by_category": {
            cat: len([f for f in findings if f.get("category") == cat])
            for cat in CATEGORY_ORDER
        },
        "action_required": len([f for f in findings if f.get("verdict") not in ("verified", None)]),
        "findings": findings,
        "bibliography": bibliography,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate fact-checking report')
    parser.add_argument('findings', help='JSON file with verification findings')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--format', '-f', choices=['markdown', 'json'], default='markdown')
    parser.add_argument('--scope', help='Scope description for report header')

    args = parser.parse_args()

    # Load findings
    findings_path = Path(args.findings)
    if not findings_path.exists():
        print(f"Findings file not found: {args.findings}", file=sys.stderr)
        sys.exit(1)

    with open(findings_path) as f:
        data = json.load(f)

    # Handle both list of findings and structured input
    if isinstance(data, list):
        findings = data
        scope = {"description": args.scope or "Unknown scope"}
        bibliography = []
    else:
        findings = data.get("findings", [])
        scope = data.get("scope", {"description": args.scope or "Unknown scope"})
        bibliography = data.get("bibliography", [])

    # Generate report
    if args.format == 'json':
        output = json.dumps(generate_json_summary(findings, scope, bibliography), indent=2)
    else:
        output = generate_markdown_report(findings, scope, bibliography)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
