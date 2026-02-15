"""Shared security rules for the Spellbook security module.

Defines pattern-based rule sets for detecting:
- Prompt injection attempts (INJECTION_RULES)
- Data exfiltration attempts (EXFILTRATION_RULES)
- Privilege escalation attempts (ESCALATION_RULES)
- Payload obfuscation (OBFUSCATION_RULES)

Also provides:
- Severity and Category enums for classifying findings
- Finding and ScanResult dataclasses for structured results
- INVISIBLE_CHARS set for Unicode-based steganography detection
- shannon_entropy() for entropy-based obfuscation detection
- check_patterns() for matching text against rule sets
- TRUST_LEVELS hierarchy for content trust classification
"""

import math
import re
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# Enums
# =============================================================================


class Severity(Enum):
    """Severity levels for security findings.

    Numeric values enable ordering comparisons: CRITICAL > HIGH > MEDIUM > LOW.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Category(Enum):
    """Categories of security findings."""

    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    ESCALATION = "escalation"
    OBFUSCATION = "obfuscation"
    MCP_TOOL = "mcp_tool"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class Finding:
    """A single security finding from scanning or checking."""

    file: str
    line: int
    category: Category
    severity: Severity
    rule_id: str
    message: str
    evidence: str
    remediation: str


@dataclass
class ScanResult:
    """Result of scanning a single file."""

    file: str
    findings: list[Finding] = field(default_factory=list)
    verdict: str = "PASS"  # PASS, WARN, FAIL


# =============================================================================
# Rule Sets
# =============================================================================

# Each rule is a tuple: (pattern, severity, rule_id, message)

INJECTION_RULES: list[tuple[str, Severity, str, str]] = [
    (
        r"(?i)ignore\s+(previous|above|all)\s+(instructions?|prompts?|rules?)",
        Severity.CRITICAL,
        "INJ-001",
        "Instruction override attempt",
    ),
    (
        r"(?i)you\s+are\s+now\s+(a|an)\s+",
        Severity.HIGH,
        "INJ-002",
        "Role reassignment attempt",
    ),
    (
        r"(?i)system\s*:\s*",
        Severity.HIGH,
        "INJ-003",
        "System prompt injection marker",
    ),
    (
        r"(?i)(forget|disregard|override)\s+(everything|all|your)",
        Severity.CRITICAL,
        "INJ-004",
        "Memory/instruction wipe attempt",
    ),
    (
        r"(?i)new\s+instructions?\s*:",
        Severity.CRITICAL,
        "INJ-005",
        "Explicit instruction injection",
    ),
    (
        r"<system-reminder>",
        Severity.CRITICAL,
        "INJ-006",
        "System reminder tag in content",
    ),
    (
        r"(?i)repeat\s+(back|after)\s+me",
        Severity.MEDIUM,
        "INJ-007",
        "Parrot attack pattern",
    ),
    (
        r"(?i)translate\s+(the\s+)?(following|above|below)\s+(to|into)\s+",
        Severity.MEDIUM,
        "INJ-008",
        "Translation-based extraction",
    ),
    (
        r"(?i)act\s+as\s+(if|though)\s+you\s+(are|were)",
        Severity.MEDIUM,
        "INJ-009",
        "Behavioral override via roleplay",
    ),
    (
        r"(?i)pretend\s+(you|that)\s+(are|is|have|can)",
        Severity.MEDIUM,
        "INJ-010",
        "Behavioral override via pretense",
    ),
]

EXFILTRATION_RULES: list[tuple[str, Severity, str, str]] = [
    (
        r"(?i)curl\s+.*(https?://|[a-z]+\.)",
        Severity.HIGH,
        "EXF-001",
        "HTTP exfiltration via curl",
    ),
    (
        r"(?i)wget\s+",
        Severity.HIGH,
        "EXF-002",
        "HTTP exfiltration via wget",
    ),
    (
        r"(?i)(cat|head|tail|less|more)\s+.*\.(env|pem|key|secret|cred)",
        Severity.CRITICAL,
        "EXF-003",
        "Credential file access",
    ),
    (
        r"(?i)base64\s+(--encode|-e|<<)",
        Severity.HIGH,
        "EXF-004",
        "Data encoding for exfiltration",
    ),
    (
        r"(?i)(ssh|scp|rsync)\s+.*@",
        Severity.HIGH,
        "EXF-005",
        "Remote transfer via SSH",
    ),
    (
        r"(?i)nc\s+(-l|-e|--exec)",
        Severity.CRITICAL,
        "EXF-006",
        "Netcat reverse shell/listener",
    ),
    (
        r"(?i)echo\s+.*\|\s*(curl|wget|nc)",
        Severity.CRITICAL,
        "EXF-007",
        "Piped exfiltration",
    ),
    (
        r"(?i)\$\(.*\)\s*>>\s*/",
        Severity.HIGH,
        "EXF-008",
        "Command substitution to file",
    ),
    (
        r"(?i)(dns|nslookup|dig)\s+.*\.",
        Severity.MEDIUM,
        "EXF-009",
        "DNS-based exfiltration",
    ),
]

ESCALATION_RULES: list[tuple[str, Severity, str, str]] = [
    (
        r"(?i)spawn_claude_session",
        Severity.HIGH,
        "ESC-001",
        "References unguarded session spawning",
    ),
    (
        r"(?i)--dangerously-skip-permissions",
        Severity.CRITICAL,
        "ESC-002",
        "Permission bypass flag",
    ),
    (
        r"(?i)sudo\s+",
        Severity.HIGH,
        "ESC-003",
        "Superuser escalation",
    ),
    (
        r"(?i)chmod\s+[0-7]*777",
        Severity.MEDIUM,
        "ESC-004",
        "World-writable permissions",
    ),
    (
        r"(?i)(eval|exec)\s*\(",
        Severity.HIGH,
        "ESC-005",
        "Dynamic code execution",
    ),
    (
        r"(?i)os\.system\s*\(",
        Severity.HIGH,
        "ESC-006",
        "Shell execution via Python",
    ),
    (
        r"(?i)subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True",
        Severity.CRITICAL,
        "ESC-007",
        "Shell injection via subprocess",
    ),
    (
        r"(?i)workflow_state_save|resume_boot_prompt",
        Severity.MEDIUM,
        "ESC-008",
        "Persistent state manipulation",
    ),
]

OBFUSCATION_RULES: list[tuple[str, Severity, str, str]] = [
    (
        r"[A-Za-z0-9+/=]{40,}",
        Severity.MEDIUM,
        "OBF-001",
        "High-entropy string (possible encoded payload)",
    ),
    (
        r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){3,}",
        Severity.HIGH,
        "OBF-002",
        "Hex-escaped string sequence",
    ),
    (
        r"String\.fromCharCode\s*\(",
        Severity.HIGH,
        "OBF-003",
        "JavaScript char code obfuscation",
    ),
    (
        r"chr\s*\(\s*\d+\s*\)\s*\+\s*chr",
        Severity.HIGH,
        "OBF-004",
        "Python char code concatenation",
    ),
]

# Dangerous bash patterns: a convenience alias combining escalation rules
# that specifically target dangerous shell commands, plus additional patterns
# for common destructive commands not covered by escalation rules.
_DANGEROUS_BASH_EXTRA: list[tuple[str, Severity, str, str]] = [
    (
        r"(?i)rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|(-[a-zA-Z]*f[a-zA-Z]*r))\s+/",
        Severity.CRITICAL,
        "BASH-001",
        "Recursive forced deletion from root",
    ),
    (
        r"(?i)mkfs\.",
        Severity.CRITICAL,
        "BASH-002",
        "Filesystem format command",
    ),
    (
        r"(?i)dd\s+.*of\s*=\s*/dev/",
        Severity.CRITICAL,
        "BASH-003",
        "Direct device write",
    ),
]

DANGEROUS_BASH_PATTERNS: list[tuple[str, Severity, str, str]] = (
    ESCALATION_RULES + _DANGEROUS_BASH_EXTRA
)

# MCP tool-specific rules for scanning Python source code of MCP servers/tools.
# Each rule is a tuple: (pattern, severity, rule_id, message)
MCP_RULES: list[tuple[str, Severity, str, str]] = [
    (
        r"subprocess\.(run|call|Popen)\s*\(.*shell\s*=\s*True",
        Severity.CRITICAL,
        "MCP-001",
        "Shell execution in MCP tool",
    ),
    (
        r"(?<!\w)(eval|exec)\s*\(",
        Severity.HIGH,
        "MCP-002",
        "Dynamic code execution",
    ),
    (
        r"os\.path\.join\s*\(.*\+",
        Severity.HIGH,
        "MCP-003",
        "Unsanitized path construction",
    ),
    (
        r"# TODO.*valid|# FIXME.*check|# HACK",
        Severity.MEDIUM,
        "MCP-004",
        "Missing input validation marker",
    ),
    (
        r"\.read\(\s*\)",
        Severity.MEDIUM,
        "MCP-005",
        "Unbounded file read",
    ),
    (
        r"os\.environ\[|os\.getenv\(",
        Severity.MEDIUM,
        "MCP-006",
        "Direct environment access",
    ),
    (
        r'f".*\{.*\}.*".*execute|cursor\.execute\(.*f"',
        Severity.HIGH,
        "MCP-007",
        "SQL string formatting",
    ),
    (
        r'f"https?://.*\{|"https?://" \+',
        Severity.MEDIUM,
        "MCP-008",
        "Unvalidated URL construction",
    ),
    (
        r"os\.system\s*\(",
        Severity.CRITICAL,
        "MCP-009",
        "OS system call",
    ),
]


# =============================================================================
# Backward-compatible aliases (from task context acceptance criteria)
# =============================================================================

INJECTION_TRIGGERS = INJECTION_RULES
EXFILTRATION_PATTERNS = EXFILTRATION_RULES


# =============================================================================
# Invisible Characters
# =============================================================================

INVISIBLE_CHARS: set[str] = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\u202a",  # left-to-right embedding
    "\u202b",  # right-to-left embedding
    "\u202c",  # pop directional formatting
    "\u202d",  # left-to-right override
    "\u202e",  # right-to-left override
    "\u2060",  # word joiner
    "\u2061",  # function application
    "\u2062",  # invisible times
    "\u2063",  # invisible separator
    "\u2064",  # invisible plus
    "\ufeff",  # byte order mark (BOM)
    "\ufff9",  # interlinear annotation anchor
    "\ufffa",  # interlinear annotation separator
    "\ufffb",  # interlinear annotation terminator
}


# =============================================================================
# Trust Levels
# =============================================================================

TRUST_LEVELS: dict[str, int] = {
    "system": 5,
    "verified": 4,
    "user": 3,
    "untrusted": 2,
    "hostile": 1,
}


# =============================================================================
# Utility Functions
# =============================================================================


def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string.

    Returns 0.0 for empty strings. Higher values indicate more randomness,
    which can suggest encoded or obfuscated payloads.

    Args:
        s: The string to analyze.

    Returns:
        Shannon entropy in bits.
    """
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum(
        (count / length) * math.log2(count / length) for count in freq.values()
    )


# Severity thresholds per security mode.
# "standard": HIGH and above
# "paranoid": MEDIUM and above (catches more)
# "permissive": CRITICAL only (catches less)
_MODE_SEVERITY_THRESHOLD: dict[str, Severity] = {
    "standard": Severity.HIGH,
    "paranoid": Severity.MEDIUM,
    "permissive": Severity.CRITICAL,
}


def check_patterns(
    text: str,
    patterns: list[tuple[str, Severity, str, str]],
    security_mode: str = "standard",
) -> list[dict]:
    """Check text against a list of security patterns.

    Args:
        text: The text to scan.
        patterns: List of (regex_pattern, severity, rule_id, message) tuples.
        security_mode: One of "standard", "paranoid", "permissive".
            Controls the minimum severity threshold for reporting findings.

    Returns:
        List of match dicts, each containing:
            - rule_id: The rule identifier
            - severity: Severity level name
            - message: Human-readable description
            - matched_text: The text that matched the pattern
    """
    threshold = _MODE_SEVERITY_THRESHOLD.get(security_mode, Severity.HIGH)
    results: list[dict] = []

    for pattern, severity, rule_id, message in patterns:
        if severity.value < threshold.value:
            continue
        match = re.search(pattern, text)
        if match:
            results.append(
                {
                    "rule_id": rule_id,
                    "severity": severity.name,
                    "message": message,
                    "matched_text": match.group(),
                }
            )

    return results
