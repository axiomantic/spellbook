"""Helper functions for the surviving security gates.

Only one function remains: do_detect_injection, used by
spellbook.sessions.injection to sanitize soul recovery context
fields before they are injected into tool responses.
"""

from spellbook.gates.rules import (
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
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

_MAX_SEVERITY_VALUE = Severity.CRITICAL.value


def do_detect_injection(
    text: str,
    security_mode: str = "standard",
) -> dict:
    """Deep injection detection using all rule sets.

    Scans text against injection, exfiltration, escalation, and obfuscation
    rules. Returns a simple is_injection flag plus findings and a
    normalized risk score.

    Args:
        text: The text to analyze.
        security_mode: One of "standard" or "paranoid".

    Returns:
        Dict with keys:
            is_injection: True if any findings detected.
            findings: List of pattern match dicts.
            risk_score: Float 0.0-1.0 based on severity sum.
    """
    findings: list[dict] = []
    for _label, rule_set in _ALL_RULE_SETS:
        findings.extend(check_patterns(text, rule_set, security_mode))

    is_injection = len(findings) > 0

    if not findings:
        risk_score = 0.0
    else:
        severity_sum = sum(Severity[f["severity"]].value for f in findings)
        total_rules = sum(len(rs) for _, rs in _ALL_RULE_SETS)
        max_possible = total_rules * _MAX_SEVERITY_VALUE
        risk_score = min(severity_sum / max_possible, 1.0)

    return {
        "is_injection": is_injection,
        "findings": findings,
        "risk_score": risk_score,
    }
