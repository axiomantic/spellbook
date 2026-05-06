"""Spellbook security gates module.

Provides the shared pattern rule sets and runtime checks used by
the surviving security gates (Bash, spawn, workflow state) plus
the pre-commit scanner. Also exposes the YOLO transcript analyzer
library used by ``scripts/analyze_yolo_transcripts.py`` and the
``permissions-from-transcripts`` skill.
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
from spellbook.gates.transcript_analyzer import (
    BashRecord,
    BucketEntry,
    Categorized,
    bucket_and_classify,
    bucket_key,
    classify,
    extract_bash_commands,
    render_proposed_list,
    write_proposed_list,
)

__all__ = [
    "BashRecord",
    "BucketEntry",
    "Category",
    "Categorized",
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
    "bucket_and_classify",
    "bucket_key",
    "check_patterns",
    "classify",
    "extract_bash_commands",
    "render_proposed_list",
    "shannon_entropy",
    "write_proposed_list",
]
