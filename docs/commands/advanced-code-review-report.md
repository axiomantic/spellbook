# /advanced-code-review-report

## Command Content

``````````markdown
# Phase 5: Report Generation

## Invariant Principles

1. **Signal over noise**: Only verified findings appear in the final report. REFUTED findings are excluded. Quality of findings matters more than quantity.
2. **Actionable output**: Every finding must have clear next steps. Findings without suggestions or context are not actionable.
3. **Machine-readable artifacts for automation**: JSON summary enables CI/CD integration, automated triage, and tooling. Human-readable Markdown is not sufficient alone.

**Purpose:** Produce final deliverables including Markdown report and machine-readable JSON summary.

## 5.1 Finding Filtering

Filter to verified and inconclusive findings only:

```python
def filter_findings_for_report(findings: list[dict]) -> list[dict]:
    """Filter out REFUTED findings for final report."""
    return [
        f for f in findings
        if f.get("verification_status") != "REFUTED"
    ]
```

## 5.2 Severity Sorting

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

## 5.3 Verdict Determination

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

## 5.4 Template Rendering

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

## 5.5 Action Items Generation

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

## 5.6 Previous Context Section

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

## 5.7 Output: review-report.md

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

## 5.8 Output: review-summary.json

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

## 5.9 File Output

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

## Phase 5 Self-Check

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
``````````
