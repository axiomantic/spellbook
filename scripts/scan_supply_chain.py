#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Scan skills and commands for external supply chain references.

Detects:
- SC-001: Non-allowlisted URLs (http/https links not in allowlist)
- SC-002: External skill repos (references to install/clone external repos)
- SC-003: Fetch/download directives (curl, wget, fetch, download instructions)
- SC-004: External MCP servers (references to MCP server URIs not in spellbook)
- SC-005: Package install directives (pip install, npm install, cargo install, etc.)

URL allowlist is configurable via .spellbook-security.json in the project root.

Exit codes:
- 0: Clean (no findings)
- 1: Findings detected
- 2: Error (bad path, etc.)
"""

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from fnmatch import fnmatch
from pathlib import Path


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class Finding:
    """A single supply chain finding."""

    file: str
    line: int
    rule_id: str
    message: str
    evidence: str


@dataclass
class ScanResult:
    """Result of scanning files for supply chain references."""

    files_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)


# =============================================================================
# Default URL allowlist
# =============================================================================

DEFAULT_URL_ALLOWLIST: list[str] = [
    "github.com/anthropics/*",
    "docs.anthropic.com/*",
    "docs.python.org/*",
    "developer.mozilla.org/*",
]


# =============================================================================
# Rules
# =============================================================================

# URL pattern to extract http/https URLs from text
URL_PATTERN = re.compile(r"https?://[^\s\)\]\}>\"'`]+")

# SC-002: External skill repo patterns
REPO_CLONE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"git\s+clone\s+"),
        "git clone directive",
    ),
    (
        re.compile(r"git\s+submodule\s+add\s+"),
        "git submodule add directive",
    ),
    (
        re.compile(r"gh\s+repo\s+clone\s+"),
        "gh repo clone directive",
    ),
]

# SC-003: Fetch/download directive patterns
FETCH_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"(?<!\w)curl\s+"),
        "curl download directive",
    ),
    (
        re.compile(r"(?<!\w)wget\s+"),
        "wget download directive",
    ),
    (
        re.compile(r'(?<!\w)fetch\s*\(\s*["\']https?://'),
        "fetch() API call",
    ),
    (
        re.compile(r"Invoke-WebRequest\s+", re.IGNORECASE),
        "PowerShell Invoke-WebRequest directive",
    ),
]

# SC-004: External MCP server patterns
MCP_SERVER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"npx\s+(-y\s+)?@(?!spellbook/)[a-zA-Z0-9_-]+/"),
        "npx MCP server package",
    ),
    (
        re.compile(r"mcp[_-]?server\s*:\s*https?://", re.IGNORECASE),
        "MCP server URL reference",
    ),
    (
        re.compile(r'"mcpServers"', re.IGNORECASE),
        "mcpServers configuration block",
    ),
]

# SC-005: Package install directive patterns
PACKAGE_INSTALL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"(?<!\w)pip\s+install\s+"),
        "pip install directive",
    ),
    (
        re.compile(r"(?<!\w)pip3\s+install\s+"),
        "pip3 install directive",
    ),
    (
        re.compile(r"(?<!\w)pipx\s+install\s+"),
        "pipx install directive",
    ),
    (
        re.compile(r"(?<!\w)npm\s+install\s+"),
        "npm install directive",
    ),
    (
        re.compile(r"(?<!\w)yarn\s+add\s+"),
        "yarn add directive",
    ),
    (
        re.compile(r"(?<!\w)pnpm\s+add\s+"),
        "pnpm add directive",
    ),
    (
        re.compile(r"(?<!\w)cargo\s+install\s+"),
        "cargo install directive",
    ),
    (
        re.compile(r"(?<!\w)go\s+install\s+"),
        "go install directive",
    ),
    (
        re.compile(r"(?<!\w)gem\s+install\s+"),
        "gem install directive",
    ),
    (
        re.compile(r"(?<!\w)brew\s+install\s+"),
        "brew install directive",
    ),
]


# =============================================================================
# Allowlist logic
# =============================================================================


def load_allowlist(project_root: Path) -> list[str]:
    """Load URL allowlist from .spellbook-security.json or use defaults."""
    config_path = project_root / ".spellbook-security.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            supply_chain = config.get("supply_chain", {})
            allowlist = supply_chain.get("url_allowlist")
            if allowlist is not None:
                return allowlist
        except (json.JSONDecodeError, KeyError):
            pass
    return DEFAULT_URL_ALLOWLIST


def is_url_allowed(url: str, allowlist: list[str]) -> bool:
    """Check if a URL matches any entry in the allowlist.

    Allowlist entries are domain/path glob patterns like 'github.com/anthropics/*'.
    The URL's scheme (http:// or https://) is stripped before matching.
    """
    # Strip scheme
    stripped = re.sub(r"^https?://", "", url)
    # Remove trailing punctuation that got captured
    stripped = stripped.rstrip(".,;:!?)")

    for pattern in allowlist:
        if fnmatch(stripped, pattern):
            return True
    return False


# =============================================================================
# Scanning logic
# =============================================================================


def scan_file(file_path: Path, allowlist: list[str]) -> list[Finding]:
    """Scan a single file for supply chain references."""
    findings: list[Finding] = []
    content = file_path.read_text(errors="replace")
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        # SC-001: Non-allowlisted URLs
        for match in URL_PATTERN.finditer(line):
            url = match.group()
            if not is_url_allowed(url, allowlist):
                findings.append(
                    Finding(
                        file=str(file_path),
                        line=line_num,
                        rule_id="SC-001",
                        message="Non-allowlisted URL",
                        evidence=url,
                    )
                )

        # SC-002: External skill repos
        for pattern, message in REPO_CLONE_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file=str(file_path),
                        line=line_num,
                        rule_id="SC-002",
                        message=message,
                        evidence=line.strip(),
                    )
                )

        # SC-003: Fetch/download directives
        for pattern, message in FETCH_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file=str(file_path),
                        line=line_num,
                        rule_id="SC-003",
                        message=message,
                        evidence=line.strip(),
                    )
                )

        # SC-004: External MCP servers
        for pattern, message in MCP_SERVER_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file=str(file_path),
                        line=line_num,
                        rule_id="SC-004",
                        message=message,
                        evidence=line.strip(),
                    )
                )

        # SC-005: Package install directives
        for pattern, message in PACKAGE_INSTALL_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file=str(file_path),
                        line=line_num,
                        rule_id="SC-005",
                        message=message,
                        evidence=line.strip(),
                    )
                )

    return findings


def collect_md_files(paths: list[Path]) -> list[Path]:
    """Collect all .md files from the given paths (files or directories)."""
    md_files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".md":
            md_files.append(path)
        elif path.is_dir():
            md_files.extend(sorted(path.rglob("*.md")))
    return md_files


def scan_paths(
    paths: list[Path], project_root: Path
) -> ScanResult:
    """Scan the given paths for supply chain references."""
    allowlist = load_allowlist(project_root)
    md_files = collect_md_files(paths)

    result = ScanResult(files_scanned=len(md_files))
    for md_file in md_files:
        file_findings = scan_file(md_file, allowlist)
        result.findings.extend(file_findings)

    return result


# =============================================================================
# Output formatting
# =============================================================================


def print_human_readable(result: ScanResult) -> None:
    """Print findings in human-readable format."""
    if not result.findings:
        print(f"Supply chain scan: {result.files_scanned} files scanned, no findings.")
        return

    print(f"Supply chain scan: {result.files_scanned} files scanned, "
          f"{len(result.findings)} finding(s)\n")

    for finding in result.findings:
        print(f"  [{finding.rule_id}] {finding.file}:{finding.line}")
        print(f"    {finding.message}")
        print(f"    Evidence: {finding.evidence}")
        print()


def print_json(result: ScanResult) -> None:
    """Print findings in JSON format."""
    output = {
        "summary": {
            "files_scanned": result.files_scanned,
            "total_findings": len(result.findings),
        },
        "findings": [asdict(f) for f in result.findings],
    }
    print(json.dumps(output, indent=2))


# =============================================================================
# CLI
# =============================================================================


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    if argv is None:
        argv = sys.argv[1:]

    # Parse --json flag
    json_output = "--json" in argv
    args = [a for a in argv if a != "--json"]

    # Determine project root (cwd)
    project_root = Path.cwd()

    # Determine paths to scan
    if args:
        paths = [Path(a) for a in args]
        # Validate paths exist
        for p in paths:
            if not p.exists():
                print(f"Error: path does not exist: {p}", file=sys.stderr)
                return 2
    else:
        # Default: scan skills/ and commands/ in project root
        paths = []
        skills_dir = project_root / "skills"
        commands_dir = project_root / "commands"
        if skills_dir.is_dir():
            paths.append(skills_dir)
        if commands_dir.is_dir():
            paths.append(commands_dir)
        if not paths:
            if json_output:
                print_json(ScanResult())
            else:
                print("No skills/ or commands/ directory found. Nothing to scan.")
            return 0

    result = scan_paths(paths, project_root)

    if json_output:
        print_json(result)
    else:
        print_human_readable(result)

    if result.findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
