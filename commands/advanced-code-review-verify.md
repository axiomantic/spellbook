---
description: "Advanced Code Review Phase 4: Verification - fact-check findings against codebase, remove false positives"
---

# Phase 4: Verification

## Invariant Principles

1. **Every finding must be verifiable against actual code**: If a finding cannot be verified by reading the file at the specified line, it is not a valid finding.
2. **REFUTED findings must be removed, not just flagged**: False positives erode trust. They are removed from the final output entirely (logged in audit for transparency).
3. **INCONCLUSIVE findings must be clearly marked**: Uncertainty is acceptable; hidden uncertainty is not. Mark findings that could not be verified so humans can assess.

**Purpose:** Fact-check every finding against the actual codebase. Remove false positives. Flag uncertain claims for human review.

## 4.1 Verification Overview

This is a simplified verification protocol, not a full invocation of the `fact-checking` skill. It focuses on:
- Line content verification
- Function behavior checks
- Call pattern analysis
- Pattern violation confirmation

## 4.2 Claim Types

| Claim Type | Example | Verification Method |
|------------|---------|---------------------|
| line_content | "Line 45 contains SQL interpolation" | Read line 45, pattern match |
| function_behavior | "Function X doesn't validate input" | Read function, check for validation |
| call_pattern | "Y is called without error handling" | Trace callers of Y |
| pattern_violation | "Same code at A and B (DRY violation)" | Compare code at A and B |

## 4.3 Claim Extraction Algorithm

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

## 4.4 Verification Functions

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

## 4.5 Finding Verification

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

## 4.6 Duplicate Detection

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

## 4.7 Line Number Validation

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

## 4.8 Signal-to-Noise Calculation

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

## 4.9 REFUTED Finding Handling

- REFUTED findings are **removed** from final output
- They are logged in verification-audit.md for transparency
- User is informed: "N findings removed after verification"

## 4.10 INCONCLUSIVE Finding Handling

- INCONCLUSIVE findings are **kept** with a flag
- Report marks them: `[NEEDS VERIFICATION]`
- User should manually verify these

## 4.11 Output: verification-audit.md

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

## Phase 4 Self-Check

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
