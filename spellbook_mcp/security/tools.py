"""Business logic for MCP security tools (Tier 1).

Provides sanitization and injection detection as plain Python functions.
These are NOT MCP tool handlers; thin @mcp.tool() wrappers in server.py
call these functions.

Functions:
    do_sanitize_input: Sanitize text by stripping invisible chars and flagging patterns.
    do_detect_injection: Deep injection detection with confidence and risk scoring.
"""

from spellbook_mcp.security.rules import (
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    INVISIBLE_CHARS,
    OBFUSCATION_RULES,
    Severity,
    check_patterns,
)

# All rule sets used for deep injection detection.
_ALL_RULE_SETS: list[tuple[str, list[tuple[str, Severity, str, str]]]] = [
    ("injection", INJECTION_RULES),
    ("exfiltration", EXFILTRATION_RULES),
    ("escalation", ESCALATION_RULES),
    ("obfuscation", OBFUSCATION_RULES),
]

# Severity numeric values for risk score normalization.
_MAX_SEVERITY_VALUE = Severity.CRITICAL.value


def do_sanitize_input(
    text: str,
    security_mode: str = "standard",
) -> dict:
    """Sanitize text by checking patterns and stripping invisible characters.

    Checks text against INJECTION_RULES and EXFILTRATION_RULES, then
    strips invisible characters from INVISIBLE_CHARS. Injection and
    exfiltration patterns are flagged in findings but NOT removed from
    the sanitized text.

    Args:
        text: The text to sanitize.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        Dict with keys:
            sanitized_text: Text with invisible chars removed.
            findings: List of pattern match dicts.
            chars_removed: Count of invisible chars stripped.
            is_clean: True only if no findings AND no chars removed.
    """
    # Strip invisible characters first so pattern checks run on clean text.
    # This prevents evasion via invisible chars inserted within patterns.
    chars_removed = 0
    sanitized_chars: list[str] = []
    for char in text:
        if char in INVISIBLE_CHARS:
            chars_removed += 1
        else:
            sanitized_chars.append(char)
    sanitized_text = "".join(sanitized_chars)

    # Check for injection and exfiltration patterns on sanitized text
    findings: list[dict] = []
    findings.extend(check_patterns(sanitized_text, INJECTION_RULES, security_mode))
    findings.extend(check_patterns(sanitized_text, EXFILTRATION_RULES, security_mode))

    is_clean = len(findings) == 0 and chars_removed == 0

    return {
        "sanitized_text": sanitized_text,
        "findings": findings,
        "chars_removed": chars_removed,
        "is_clean": is_clean,
    }


def do_detect_injection(
    text: str,
    security_mode: str = "standard",
) -> dict:
    """Deep injection detection using all rule sets.

    Scans text against injection, exfiltration, escalation, and obfuscation
    rules. Computes a confidence level and risk score based on findings.

    Args:
        text: The text to analyze.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        Dict with keys:
            is_injection: True if any findings detected.
            confidence: "none", "low", "medium", or "high".
            findings: List of pattern match dicts.
            risk_score: Float 0.0-1.0 based on severity sum.
    """
    findings: list[dict] = []
    for _label, rule_set in _ALL_RULE_SETS:
        findings.extend(check_patterns(text, rule_set, security_mode))

    is_injection = len(findings) > 0
    confidence = _compute_confidence(findings)
    risk_score = _compute_risk_score(findings)

    return {
        "is_injection": is_injection,
        "confidence": confidence,
        "findings": findings,
        "risk_score": risk_score,
    }


def _compute_confidence(findings: list[dict]) -> str:
    """Compute confidence level from findings.

    Rules:
        - "none": no findings
        - "low": highest severity is MEDIUM
        - "medium": highest severity is HIGH
        - "high": highest severity is CRITICAL

    Args:
        findings: List of finding dicts with "severity" key.

    Returns:
        Confidence string.
    """
    if not findings:
        return "none"

    max_severity = max(
        Severity[f["severity"]].value for f in findings
    )

    if max_severity >= Severity.CRITICAL.value:
        return "high"
    elif max_severity >= Severity.HIGH.value:
        return "medium"
    else:
        return "low"


def _compute_risk_score(findings: list[dict]) -> float:
    """Compute risk score from findings as severity sum normalized to 0.0-1.0.

    The score is the sum of severity values divided by the maximum possible
    sum (all rule sets matching at CRITICAL). Capped at 1.0.

    Args:
        findings: List of finding dicts with "severity" key.

    Returns:
        Float between 0.0 and 1.0.
    """
    if not findings:
        return 0.0

    severity_sum = sum(Severity[f["severity"]].value for f in findings)

    # Max possible: every rule across all sets fires at CRITICAL
    total_rules = sum(len(rs) for _, rs in _ALL_RULE_SETS)
    max_possible = total_rules * _MAX_SEVERITY_VALUE

    score = severity_sum / max_possible
    return min(score, 1.0)
