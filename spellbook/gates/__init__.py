"""Spellbook security gates module.

Provides the shared pattern rule sets and runtime checks used by
the surviving security gates (Bash, spawn, workflow state) plus
the pre-commit scanner.
"""

from spellbook.gates.rules import (
    DANGEROUS_BASH_PATTERNS,
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    INVISIBLE_CHARS,
    MCP_RULES,
    OBFUSCATION_RULES,
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
    "EXFILTRATION_RULES",
    "Finding",
    "INJECTION_RULES",
    "INVISIBLE_CHARS",
    "MCP_RULES",
    "OBFUSCATION_RULES",
    "ScanResult",
    "Severity",
    "check_patterns",
    "shannon_entropy",
]
