"""Spellbook security module.

Provides shared security rules, runtime checks, static scanning,
and MCP tools for defense-in-depth against prompt injection,
privilege escalation, and exfiltration attacks.
"""

from spellbook_mcp.security.rules import (
    DANGEROUS_BASH_PATTERNS,
    ESCALATION_RULES,
    EXFILTRATION_PATTERNS,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    INJECTION_TRIGGERS,
    INVISIBLE_CHARS,
    MCP_RULES,
    OBFUSCATION_RULES,
    TRUST_LEVELS,
    Category,
    Finding,
    ScanResult,
    Severity,
    check_patterns,
    shannon_entropy,
)

__all__ = [
    "Category",
    "DANGEROUS_BASH_PATTERNS",
    "ESCALATION_RULES",
    "EXFILTRATION_PATTERNS",
    "EXFILTRATION_RULES",
    "Finding",
    "INJECTION_RULES",
    "INJECTION_TRIGGERS",
    "INVISIBLE_CHARS",
    "MCP_RULES",
    "OBFUSCATION_RULES",
    "ScanResult",
    "Severity",
    "TRUST_LEVELS",
    "check_patterns",
    "shannon_entropy",
]
