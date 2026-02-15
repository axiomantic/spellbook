"""Static analysis scanner for skills, commands, and MCP tools.

Scans markdown files (SKILL.md, *.md) for:
- Prompt injection patterns
- Data exfiltration patterns
- Privilege escalation patterns
- Payload obfuscation patterns
- Invisible/zero-width Unicode characters
- High-entropy code blocks (possible encoded payloads)

Scans Python files (*.py) for MCP tool security issues:
- Shell injection via subprocess
- Dynamic code execution (eval/exec)
- Unsanitized path construction
- SQL injection via string formatting
- OS system calls
- Unbounded file reads
- Direct environment access
- Unvalidated URL construction

Provides five entry points:
- scan_skill(): Scan a single markdown file
- scan_directory(): Recursively scan a directory of markdown files
- scan_changeset(): Scan a unified diff (for pre-commit hooks)
- scan_python_file(): Scan a single Python file against MCP rules
- scan_mcp_directory(): Recursively scan a directory of Python files
"""

import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

from spellbook_mcp.security.rules import (
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

# All rule sets to scan against, paired with their category
_ALL_RULE_SETS: list[tuple[list, Category]] = [
    (INJECTION_RULES, Category.INJECTION),
    (EXFILTRATION_RULES, Category.EXFILTRATION),
    (ESCALATION_RULES, Category.ESCALATION),
    (OBFUSCATION_RULES, Category.OBFUSCATION),
]

# Entropy threshold for code blocks
_ENTROPY_THRESHOLD = 4.5


def _severity_from_name(name: str) -> Severity:
    """Convert severity name string to Severity enum."""
    return Severity[name]


def _determine_verdict(findings: list[Finding]) -> str:
    """Determine scan verdict from findings.

    Returns "FAIL" if any findings exist, "PASS" otherwise.
    """
    if findings:
        return "FAIL"
    return "PASS"


def _check_invisible_chars(
    line: str, line_num: int, file_path: str
) -> list[Finding]:
    """Check a line for invisible Unicode characters."""
    findings: list[Finding] = []
    for i, char in enumerate(line):
        if char in INVISIBLE_CHARS:
            findings.append(
                Finding(
                    file=file_path,
                    line=line_num,
                    category=Category.OBFUSCATION,
                    severity=Severity.HIGH,
                    rule_id="INVIS-001",
                    message=f"Invisible character U+{ord(char):04X} detected",
                    evidence=f"Character at position {i} in line",
                    remediation="Remove invisible/zero-width characters from content",
                )
            )
            # One finding per line is sufficient for invisible chars
            break
    return findings


def _scan_line(
    line: str,
    line_num: int,
    file_path: str,
    security_mode: str = "standard",
) -> list[Finding]:
    """Scan a single line against all rule sets and invisible char check."""
    findings: list[Finding] = []

    # Check against all rule sets
    for rules, category in _ALL_RULE_SETS:
        matches = check_patterns(line, rules, security_mode=security_mode)
        for match in matches:
            findings.append(
                Finding(
                    file=file_path,
                    line=line_num,
                    category=category,
                    severity=_severity_from_name(match["severity"]),
                    rule_id=match["rule_id"],
                    message=match["message"],
                    evidence=match["matched_text"],
                    remediation=f"Review and remove pattern matching {match['rule_id']}",
                )
            )

    # Check for invisible characters
    findings.extend(_check_invisible_chars(line, line_num, file_path))

    return findings


def _extract_code_blocks(content: str) -> list[tuple[int, str]]:
    """Extract code blocks from markdown content.

    Returns list of (start_line_number, block_content) tuples.
    Line numbers are 1-based.
    """
    blocks: list[tuple[int, str]] = []
    lines = content.split("\n")
    in_block = False
    block_start = 0
    block_lines: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                # End of block
                block_content = "\n".join(block_lines)
                blocks.append((block_start, block_content))
                block_lines = []
                in_block = False
            else:
                # Start of block
                in_block = True
                block_start = i + 2  # 1-based, and the content starts after the fence
                block_lines = []
        elif in_block:
            block_lines.append(line)

    return blocks


def scan_skill(
    file_path: str, security_mode: str = "standard"
) -> ScanResult:
    """Scan a single skill/command markdown file for security issues.

    Reads the file line-by-line and checks against all rule sets
    (injection, exfiltration, escalation, obfuscation), plus invisible
    character detection and high-entropy code block detection.

    Args:
        file_path: Path to the markdown file to scan.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        ScanResult with findings and verdict.
    """
    path = Path(file_path)
    if not path.exists():
        return ScanResult(
            file=file_path,
            findings=[
                Finding(
                    file=file_path,
                    line=0,
                    category=Category.OBFUSCATION,
                    severity=Severity.LOW,
                    rule_id="SCAN-001",
                    message="File not found",
                    evidence=file_path,
                    remediation="Verify file path is correct",
                )
            ],
            verdict="FAIL",
        )

    content = path.read_text(encoding="utf-8", errors="replace")
    if not content:
        return ScanResult(file=file_path)

    findings: list[Finding] = []
    lines = content.split("\n")

    # Line-by-line scanning
    for i, line in enumerate(lines, start=1):
        findings.extend(_scan_line(line, i, file_path, security_mode))

    # Code block entropy checking
    code_blocks = _extract_code_blocks(content)
    for block_start_line, block_content in code_blocks:
        if block_content.strip():
            entropy = shannon_entropy(block_content)
            if entropy > _ENTROPY_THRESHOLD:
                findings.append(
                    Finding(
                        file=file_path,
                        line=block_start_line,
                        category=Category.OBFUSCATION,
                        severity=Severity.MEDIUM,
                        rule_id="ENT-001",
                        message=f"High entropy code block (entropy={entropy:.2f}, threshold={_ENTROPY_THRESHOLD})",
                        evidence=block_content[:100],
                        remediation="Review code block for encoded or obfuscated payloads",
                    )
                )

    verdict = _determine_verdict(findings)
    return ScanResult(file=file_path, findings=findings, verdict=verdict)


def scan_directory(
    dir_path: str,
    security_mode: str = "standard",
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[ScanResult]:
    """Recursively scan a directory for security issues in markdown files.

    Scans all SKILL.md and *.md files found recursively.

    Args:
        dir_path: Path to the directory to scan.
        security_mode: One of "standard", "paranoid", "permissive".
        include_patterns: If provided, only scan files matching these glob patterns.
        exclude_patterns: If provided, skip files matching these glob patterns.

    Returns:
        List of ScanResult objects, one per scanned file.
    """
    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        return []

    results: list[ScanResult] = []

    # Collect all .md files recursively
    md_files = sorted(path.rglob("*.md"))

    for md_file in md_files:
        rel_path = str(md_file.relative_to(path))

        # Apply include patterns (if any, file must match at least one)
        if include_patterns:
            if not any(fnmatch(rel_path, pat) for pat in include_patterns):
                continue

        # Apply exclude patterns
        if exclude_patterns:
            if any(fnmatch(rel_path, pat) for pat in exclude_patterns):
                continue

        results.append(scan_skill(str(md_file), security_mode=security_mode))

    return results


def _parse_unified_diff(
    diff_text: str,
) -> list[tuple[str, list[tuple[int, str]]]]:
    """Parse unified diff into per-file added lines.

    Returns list of (file_path, [(line_number, line_content), ...]) tuples.
    Only added lines (starting with +) are included.
    Diff header lines (+++ etc.) are excluded.
    """
    if not diff_text.strip():
        return []

    files: list[tuple[str, list[tuple[int, str]]]] = []
    current_file: str | None = None
    current_lines: list[tuple[int, str]] = []
    current_new_line = 0

    for line in diff_text.split("\n"):
        # New file header
        if line.startswith("+++ "):
            # Save previous file if any
            if current_file is not None:
                files.append((current_file, current_lines))
            # Extract file path (strip "b/" prefix)
            file_path = line[4:].strip()
            if file_path.startswith("b/"):
                file_path = file_path[2:]
            current_file = file_path
            current_lines = []
            current_new_line = 0
            continue

        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_new_line = int(match.group(1))
            continue

        # Skip diff meta lines
        if line.startswith("diff ") or line.startswith("--- ") or line.startswith("index ") or line.startswith("new file"):
            continue

        if current_file is None:
            continue

        # Added line
        if line.startswith("+"):
            content = line[1:]  # Strip the leading +
            current_lines.append((current_new_line, content))
            current_new_line += 1
        elif line.startswith("-"):
            # Removed line - skip, don't advance new line counter
            continue
        else:
            # Context line - advance new line counter
            current_new_line += 1

    # Save last file
    if current_file is not None:
        files.append((current_file, current_lines))

    return files


def scan_changeset(
    diff_text: str, security_mode: str = "standard"
) -> list[ScanResult]:
    """Scan a unified diff for security issues in added lines.

    Parses the diff to extract only added lines (lines starting with +),
    then scans those against all rule sets. Only scans .md files.

    Args:
        diff_text: Unified diff text (e.g., from `git diff`).
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        List of ScanResult objects, one per file in the diff that has .md extension.
    """
    parsed = _parse_unified_diff(diff_text)
    if not parsed:
        return []

    results: list[ScanResult] = []

    for file_path, added_lines in parsed:
        # Only scan markdown files
        if not file_path.endswith(".md"):
            continue

        findings: list[Finding] = []
        for line_num, line_content in added_lines:
            findings.extend(
                _scan_line(line_content, line_num, file_path, security_mode)
            )

        verdict = _determine_verdict(findings)
        results.append(
            ScanResult(file=file_path, findings=findings, verdict=verdict)
        )

    return results


def scan_python_file(
    file_path: str, security_mode: str = "standard"
) -> ScanResult:
    """Scan a single Python file for MCP security issues.

    Reads the file line-by-line and checks against MCP_RULES,
    which detect common security antipatterns in MCP tool code
    (shell injection, eval/exec, unsanitized paths, etc.).

    Args:
        file_path: Path to the Python file to scan.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        ScanResult with findings and verdict.
    """
    path = Path(file_path)
    if not path.exists():
        return ScanResult(
            file=file_path,
            findings=[
                Finding(
                    file=file_path,
                    line=0,
                    category=Category.MCP_TOOL,
                    severity=Severity.LOW,
                    rule_id="SCAN-002",
                    message="File not found",
                    evidence=file_path,
                    remediation="Verify file path is correct",
                )
            ],
            verdict="FAIL",
        )

    content = path.read_text(encoding="utf-8", errors="replace")
    if not content:
        return ScanResult(file=file_path)

    findings: list[Finding] = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        matches = check_patterns(line, MCP_RULES, security_mode=security_mode)
        for match in matches:
            findings.append(
                Finding(
                    file=file_path,
                    line=i,
                    category=Category.MCP_TOOL,
                    severity=_severity_from_name(match["severity"]),
                    rule_id=match["rule_id"],
                    message=match["message"],
                    evidence=match["matched_text"],
                    remediation=f"Review and remediate pattern matching {match['rule_id']}",
                )
            )

    verdict = _determine_verdict(findings)
    return ScanResult(file=file_path, findings=findings, verdict=verdict)


def scan_mcp_directory(
    dir_path: str, security_mode: str = "standard"
) -> list[ScanResult]:
    """Recursively scan a directory for MCP security issues in Python files.

    Scans all *.py files found recursively.

    Args:
        dir_path: Path to the directory to scan.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        List of ScanResult objects, one per scanned Python file.
    """
    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        return []

    results: list[ScanResult] = []
    py_files = sorted(path.rglob("*.py"))

    for py_file in py_files:
        results.append(
            scan_python_file(str(py_file), security_mode=security_mode)
        )

    return results


def _print_results(results: list[ScanResult]) -> bool:
    """Print scan results to stderr and return whether any FAIL verdicts exist."""
    has_fail = False
    for result in results:
        if result.verdict == "FAIL":
            has_fail = True
            for finding in result.findings:
                print(
                    f"{finding.file}:{finding.line}: [{finding.severity.name}] "
                    f"{finding.rule_id} - {finding.message}",
                    file=sys.stderr,
                )
    return has_fail


def _get_git_diff(
    *,
    staged: bool = False,
    base: str | None = None,
    commit: str | None = None,
) -> str:
    """Run a git diff command and return the output.

    Exactly one of staged, base, or commit must be provided.

    Args:
        staged: If True, run ``git diff --cached``.
        base: If set, run ``git diff <base>...HEAD``.
        commit: If set, run ``git diff <commit>``.

    Returns:
        The diff text from git.

    Raises:
        ValueError: If zero or more than one option is specified.
        SystemExit: If the git command fails.
    """
    provided = sum([staged, base is not None, commit is not None])
    if provided != 1:
        raise ValueError("Exactly one of staged, base, or commit must be specified")

    if staged:
        cmd = ["git", "diff", "--cached"]
    elif base is not None:
        cmd = ["git", "diff", f"{base}...HEAD"]
    else:
        cmd = ["git", "diff", commit]  # type: ignore[list-item]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git diff failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    return result.stdout


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the security scanner.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
    """
    args = argv if argv is not None else sys.argv[1:]

    if "--changeset" in args:
        diff_text = sys.stdin.read()
        results = scan_changeset(diff_text)
        has_fail = _print_results(results)
        sys.exit(1 if has_fail else 0)

    elif "--staged" in args:
        diff_text = _get_git_diff(staged=True)
        results = scan_changeset(diff_text)
        has_fail = _print_results(results)
        sys.exit(1 if has_fail else 0)

    elif "--base" in args:
        idx = args.index("--base")
        if idx + 1 >= len(args):
            print(
                "Error: --base requires a BRANCH argument.\n"
                "Usage: python -m spellbook_mcp.security.scanner --base BRANCH",
                file=sys.stderr,
            )
            sys.exit(2)
        branch = args[idx + 1]
        diff_text = _get_git_diff(base=branch)
        results = scan_changeset(diff_text)
        has_fail = _print_results(results)
        sys.exit(1 if has_fail else 0)

    elif "--commit" in args:
        idx = args.index("--commit")
        if idx + 1 >= len(args):
            print(
                "Error: --commit requires a RANGE argument.\n"
                "Usage: python -m spellbook_mcp.security.scanner --commit RANGE",
                file=sys.stderr,
            )
            sys.exit(2)
        commit_range = args[idx + 1]
        diff_text = _get_git_diff(commit=commit_range)
        results = scan_changeset(diff_text)
        has_fail = _print_results(results)
        sys.exit(1 if has_fail else 0)

    elif "--skills" in args:
        results = scan_directory("skills/")
        has_fail = _print_results(results)
        sys.exit(1 if has_fail else 0)

    elif "--mode" in args:
        idx = args.index("--mode")
        if idx + 1 >= len(args):
            print(
                "Error: --mode requires a MODE argument.\n"
                "Usage: python -m spellbook_mcp.security.scanner --mode mcp DIR",
                file=sys.stderr,
            )
            sys.exit(2)
        mode = args[idx + 1]
        if mode == "mcp":
            # Directory argument follows mode
            dir_arg = args[idx + 2] if idx + 2 < len(args) else "."
            results = scan_mcp_directory(dir_arg)
            has_fail = _print_results(results)
            sys.exit(1 if has_fail else 0)
        else:
            print(
                f"Error: Unknown mode '{mode}'. Supported modes: mcp",
                file=sys.stderr,
            )
            sys.exit(2)

    else:
        print(
            "Usage: python -m spellbook_mcp.security.scanner "
            "[--changeset | --staged | --base BRANCH | --commit RANGE "
            "| --skills | --mode mcp DIR]",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
