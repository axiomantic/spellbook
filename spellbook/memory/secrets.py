"""Secret detection for memory content.

Scans text for common secret patterns (API keys, tokens, private keys).
Returns findings with pattern name and matched text. Flags but never blocks.
"""

import re
from typing import Dict, List

# Each pattern: (name, compiled_regex)
_SECRET_PATTERNS: List[tuple] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key", re.compile(
        r"(?i)(aws_secret_access_key|aws_secret)\s*[=:]\s*[A-Za-z0-9/+=]{40}"
    )),
    ("GitHub Token (classic)", re.compile(r"ghp_[A-Za-z0-9]{30,}")),
    ("GitHub Token (fine-grained)", re.compile(r"github_pat_[A-Za-z0-9_]{82}")),
    ("GitLab Token", re.compile(r"glpat-[A-Za-z0-9\-]{20,}")),
    ("Slack Token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("Private Key Header", re.compile(r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE KEY-----")),
    ("Anthropic API Key", re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}")),
    ("OpenAI API Key", re.compile(r"sk-proj-[A-Za-z0-9]{20,}")),
    ("OpenAI Legacy Key", re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("Google API Key", re.compile(r"AIza[A-Za-z0-9\-_]{35}")),
    ("Stripe Key", re.compile(r"(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{24,}")),
    ("NPM Token", re.compile(r"npm_[A-Za-z0-9]{36}")),
    ("PyPI Token", re.compile(r"pypi-[A-Za-z0-9\-_]{50,}")),
    ("Generic High-Entropy Key Assignment", re.compile(
        r"""(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\s*[=:]\s*["']?[A-Za-z0-9/+=\-_]{32,}["']?"""
    )),
    ("Hex Secret (64+ chars)", re.compile(r"(?i)(?:secret|token|key)\s*[=:]\s*[0-9a-f]{64,}")),
]


def _redact_match(matched_text: str) -> str:
    """Create a redacted preview of a secret match.

    For matches >= 8 chars: first 4 chars + "..." + last 2 chars.
    For matches < 8 chars: "[REDACTED]".
    """
    if len(matched_text) < 8:
        return "[REDACTED]"
    return matched_text[:4] + "..." + matched_text[-2:]


def scan_for_secrets(text: str) -> List[Dict[str, str]]:
    """Scan text for common secret patterns.

    Args:
        text: Content to scan.

    Returns:
        List of dicts with 'pattern_name', 'start', 'end', and
        'redacted_preview' keys. The full matched text is never stored.
        Empty list if no secrets detected.
    """
    findings: List[Dict[str, str]] = []
    for pattern_name, regex in _SECRET_PATTERNS:
        for match in regex.finditer(text):
            findings.append({
                "pattern_name": pattern_name,
                "start": match.start(),
                "end": match.end(),
                "redacted_preview": _redact_match(match.group(0)),
            })
    return findings
