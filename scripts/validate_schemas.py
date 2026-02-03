#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "tiktoken"]
# ///
"""
Validate skills, commands, and agents against canonical schemas.

Checks:
1. YAML frontmatter presence and required fields
2. Required sections (Invariant Principles, etc.)
3. Research-backed elements (EmotionPrompt, NegativePrompt, Self-Check)
4. Reasoning schema tags (<analysis>, <reflection>)
5. Interoperability sections (Inputs, Outputs)
6. Token counts

Exit codes:
- 0: All validations pass
- 1: Validation failures found
"""

import re
import sys
import json
from pathlib import Path
from typing import NamedTuple

try:
    import yaml
except ImportError:
    print("Warning: pyyaml not installed, using basic YAML parsing")
    yaml = None

try:
    import tiktoken
    ENCODER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    print("Warning: tiktoken not installed, using word-based token estimation")
    ENCODER = None

# Opencode tool output truncation limits (with safety buffer)
# Source: opencode/src/tool/truncation.ts:10-11
# Hard limits: 2000 lines OR 51,200 bytes (50KB)
# We use conservative limits to ensure content is never truncated
MAX_LINES = 1900  # Buffer of 100 lines
MAX_BYTES = 49152  # Buffer of 2KB (48KB)


class ValidationResult(NamedTuple):
    path: str
    item_type: str  # skill, command, agent
    name: str
    passed: bool
    errors: list[str]
    warnings: list[str]
    token_count: int
    line_count: int
    byte_count: int


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken or estimate from words."""
    if ENCODER:
        return len(ENCODER.encode(text))
    # Rough estimation: ~0.75 tokens per word
    return int(len(text.split()) * 1.3)


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Extract YAML frontmatter and body from markdown."""
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    if yaml:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError:
            return None, content
    else:
        # Basic parsing fallback
        frontmatter = {}
        for line in frontmatter_text.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip()

    return frontmatter, body


def has_section(content: str, section_name: str) -> bool:
    """Check if content has a markdown section."""
    patterns = [
        rf"^##\s+{re.escape(section_name)}\s*$",
        rf"^##\s+{re.escape(section_name)}[:\s]",
        rf"^#\s+{re.escape(section_name)}\s*$",
    ]
    for pattern in patterns:
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            return True
    return False


def has_tag(content: str, tag_name: str) -> bool:
    """Check if content has an XML-style tag."""
    return f"<{tag_name}>" in content.lower() or f"<{tag_name.upper()}>" in content


def count_invariant_principles(content: str) -> int:
    """Count numbered invariant principles."""
    # Look for patterns like "1. **Name**" or "1. Name"
    pattern = r"^\d+\.\s+\*?\*?[A-Z]"

    # Find the Invariant Principles section
    inv_match = re.search(r"##\s+Invariant\s+Principles.*?(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not inv_match:
        return 0

    section = inv_match.group(0)
    matches = re.findall(pattern, section, re.MULTILINE)
    return len(matches)


def check_truncation_limits(content: str, errors: list[str]) -> None:
    """Check if content exceeds opencode tool output truncation limits."""
    line_count = len(content.splitlines())
    byte_count = len(content.encode("utf-8"))

    if line_count > MAX_LINES:
        errors.append(
            f"Exceeds line limit: {line_count} lines > {MAX_LINES} max "
            f"(opencode truncates at 2000 lines)"
        )

    if byte_count > MAX_BYTES:
        errors.append(
            f"Exceeds size limit: {byte_count:,} bytes > {MAX_BYTES:,} max "
            f"(opencode truncates at 51,200 bytes)"
        )


def validate_skill(path: Path) -> ValidationResult:
    """Validate a skill against the skill schema."""
    content = path.read_text()
    errors = []
    warnings = []

    # Check truncation limits first (hard error)
    check_truncation_limits(content, errors)

    frontmatter, body = parse_frontmatter(content)

    # Required: YAML frontmatter with name and description
    if not frontmatter:
        errors.append("Missing YAML frontmatter")
    else:
        if "name" not in frontmatter:
            errors.append("Frontmatter missing 'name' field")
        if "description" not in frontmatter:
            errors.append("Frontmatter missing 'description' field")

    # Required: Invariant Principles (3-5)
    principle_count = count_invariant_principles(content)
    if principle_count == 0:
        errors.append("Missing 'Invariant Principles' section")
    elif principle_count < 3:
        warnings.append(f"Only {principle_count} invariant principles (recommend 3-5)")
    elif principle_count > 5:
        warnings.append(f"{principle_count} invariant principles (recommend 3-5)")

    # Required: <analysis> tag
    if not has_tag(content, "analysis"):
        errors.append("Missing <analysis> reasoning tag")

    # Required: <reflection> tag
    if not has_tag(content, "reflection"):
        errors.append("Missing <reflection> reasoning tag")

    # Recommended: Role (EmotionPrompt)
    if not has_tag(content, "role"):
        warnings.append("Missing <ROLE> tag (EmotionPrompt)")

    # Recommended: Anti-patterns (NegativePrompt)
    if not has_tag(content, "forbidden") and not has_section(content, "Anti-Patterns"):
        warnings.append("Missing <FORBIDDEN> or Anti-Patterns section (NegativePrompt)")

    # Recommended: Inputs section (interoperability)
    if not has_section(content, "Inputs"):
        warnings.append("Missing 'Inputs' section (interoperability)")

    # Recommended: Outputs section (interoperability)
    if not has_section(content, "Outputs"):
        warnings.append("Missing 'Outputs' section (interoperability)")

    # Recommended: Self-Check
    if not has_section(content, "Self-Check") and "self-check" not in content.lower():
        warnings.append("Missing 'Self-Check' section")

    # Token budget
    token_count = count_tokens(content)
    if token_count > 1500:
        warnings.append(f"Token count {token_count} exceeds recommended 1000")

    name = frontmatter.get("name", path.parent.name) if frontmatter else path.parent.name

    return ValidationResult(
        path=str(path),
        item_type="skill",
        name=name,
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        token_count=token_count,
        line_count=len(content.splitlines()),
        byte_count=len(content.encode("utf-8")),
    )


def validate_command(path: Path) -> ValidationResult:
    """Validate a command against the command schema."""
    content = path.read_text()
    errors = []
    warnings = []

    # Check truncation limits first (hard error)
    check_truncation_limits(content, errors)

    frontmatter, body = parse_frontmatter(content)

    # Required: YAML frontmatter with description
    if not frontmatter:
        errors.append("Missing YAML frontmatter")
    elif "description" not in frontmatter:
        errors.append("Frontmatter missing 'description' field")

    # Required: Mission/purpose statement (header or MISSION section)
    has_mission = "# MISSION" in content or has_section(content, "MISSION")
    has_header = re.search(r"^#\s+[A-Z]", content, re.MULTILINE)
    if not has_mission and not has_header:
        errors.append("Missing mission statement or main header")

    # Required: Invariant Principles (3-5)
    principle_count = count_invariant_principles(content)
    if principle_count == 0:
        # Check for alternative formats
        if not has_section(content, "Constitution") and not has_tag(content, "invariants"):
            errors.append("Missing 'Invariant Principles' section")
    elif principle_count < 3:
        warnings.append(f"Only {principle_count} invariant principles (recommend 3-5)")

    # Recommended: <analysis> tag
    if not has_tag(content, "analysis"):
        warnings.append("Missing <analysis> reasoning tag")

    # Recommended: <reflection> tag
    if not has_tag(content, "reflection"):
        warnings.append("Missing <reflection> reasoning tag")

    # Recommended: Role (EmotionPrompt)
    if not has_tag(content, "role"):
        warnings.append("Missing <ROLE> tag (EmotionPrompt)")

    # Recommended: Anti-patterns (NegativePrompt)
    if not has_tag(content, "forbidden"):
        warnings.append("Missing <FORBIDDEN> tag (NegativePrompt)")

    # Token budget (commands should be leaner)
    token_count = count_tokens(content)
    if token_count > 1200:
        warnings.append(f"Token count {token_count} exceeds recommended 800")

    name = path.stem

    return ValidationResult(
        path=str(path),
        item_type="command",
        name=name,
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        token_count=token_count,
        line_count=len(content.splitlines()),
        byte_count=len(content.encode("utf-8")),
    )


def validate_agent(path: Path) -> ValidationResult:
    """Validate an agent against the agent schema."""
    content = path.read_text()
    errors = []
    warnings = []

    # Check truncation limits first (hard error)
    check_truncation_limits(content, errors)

    frontmatter, body = parse_frontmatter(content)

    # Required: YAML frontmatter with name, description, model
    if not frontmatter:
        errors.append("Missing YAML frontmatter")
    else:
        if "name" not in frontmatter:
            errors.append("Frontmatter missing 'name' field")
        if "description" not in frontmatter:
            errors.append("Frontmatter missing 'description' field")
        if "model" not in frontmatter:
            warnings.append("Frontmatter missing 'model' field (defaults to inherit)")

    # Required: Invariant Principles (3-5)
    principle_count = count_invariant_principles(content)
    if principle_count == 0:
        errors.append("Missing 'Invariant Principles' section")
    elif principle_count < 3:
        warnings.append(f"Only {principle_count} invariant principles (recommend 3-5)")

    # Required: <analysis> tag
    if not has_tag(content, "analysis"):
        errors.append("Missing <analysis> reasoning tag")

    # Required: <reflection> tag
    if not has_tag(content, "reflection"):
        errors.append("Missing <reflection> reasoning tag")

    # Recommended: Role (EmotionPrompt)
    if not has_tag(content, "role"):
        warnings.append("Missing <ROLE> tag (EmotionPrompt)")

    # Recommended: Inputs section
    if not has_section(content, "Inputs"):
        warnings.append("Missing 'Inputs' section")

    # Recommended: Outputs section
    if not has_section(content, "Outputs"):
        warnings.append("Missing 'Outputs' section")

    # Recommended: Output Structure
    if not has_section(content, "Output Structure"):
        warnings.append("Missing 'Output Structure' section")

    # Recommended: Anti-patterns (NegativePrompt)
    if not has_tag(content, "forbidden") and not has_section(content, "Anti-Patterns"):
        warnings.append("Missing <FORBIDDEN> or Anti-Patterns section (NegativePrompt)")

    # Token budget (agents should be compact)
    token_count = count_tokens(content)
    if token_count > 1000:
        warnings.append(f"Token count {token_count} exceeds recommended 600")

    name = frontmatter.get("name", path.stem) if frontmatter else path.stem

    return ValidationResult(
        path=str(path),
        item_type="agent",
        name=name,
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        token_count=token_count,
        line_count=len(content.splitlines()),
        byte_count=len(content.encode("utf-8")),
    )


def main():
    repo_root = Path(__file__).parent.parent.absolute()
    skills_dir = repo_root / "skills"
    commands_dir = repo_root / "commands"
    agents_dir = repo_root / "agents"

    results: list[ValidationResult] = []

    # Validate skills
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                results.append(validate_skill(skill_file))

    # Validate commands
    for cmd_file in sorted(commands_dir.glob("*.md")):
        if not cmd_file.name.startswith("_"):
            results.append(validate_command(cmd_file))

    # Validate agents
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            if not agent_file.name.startswith("_"):
                results.append(validate_agent(agent_file))

    # Print results
    passed = 0
    failed = 0
    total_errors = 0
    total_warnings = 0

    print("=" * 70)
    print("SCHEMA VALIDATION REPORT")
    print("=" * 70)

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        icon = "✓" if result.passed else "✗"

        print(f"\n{icon} [{result.item_type.upper()}] {result.name} ({status})")
        print(f"  Path: {result.path}")
        print(f"  Lines: {result.line_count}, Bytes: {result.byte_count:,}, Tokens: {result.token_count}")

        if result.errors:
            print("  Errors:")
            for error in result.errors:
                print(f"    - {error}")

        if result.warnings:
            print("  Warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")

        if result.passed:
            passed += 1
        else:
            failed += 1
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {len(results)} items")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")

    # Token statistics
    total_tokens = sum(r.token_count for r in results)
    total_lines = sum(r.line_count for r in results)
    total_bytes = sum(r.byte_count for r in results)
    print(f"\nTotal tokens: {total_tokens}")
    print(f"Total lines: {total_lines}")
    print(f"Total bytes: {total_bytes:,}")
    print(f"\nTruncation limits: {MAX_LINES} lines / {MAX_BYTES:,} bytes per file")

    # Generate JSON report if requested
    if "--json" in sys.argv:
        report = {
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": failed,
                "errors": total_errors,
                "warnings": total_warnings,
                "total_tokens": total_tokens,
                "total_lines": total_lines,
                "total_bytes": total_bytes,
                "truncation_limits": {
                    "max_lines": MAX_LINES,
                    "max_bytes": MAX_BYTES,
                },
            },
            "results": [
                {
                    "path": r.path,
                    "type": r.item_type,
                    "name": r.name,
                    "passed": r.passed,
                    "errors": r.errors,
                    "warnings": r.warnings,
                    "token_count": r.token_count,
                    "line_count": r.line_count,
                    "byte_count": r.byte_count,
                }
                for r in results
            ],
        }
        print("\n" + json.dumps(report, indent=2))

    # Exit with error if any failures
    if failed > 0:
        print(f"\n{failed} item(s) failed validation. See errors above.")
        sys.exit(1)
    else:
        print("\nAll items passed validation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
