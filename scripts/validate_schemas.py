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

# Per-file SIZE-limit exemptions (byte + line checks ONLY).
# Keyed by repo-relative POSIX path. Exempt files still undergo every other
# check (frontmatter, Invariant Principles, reasoning tags, etc.); only the
# truncation byte/line gate is waived.
#
# commands/crystallize.md: crystallize's PURPOSE is to shrink/consolidate other
# docs, so it legitimately carries extensive instructional content and is allowed
# to exceed the truncation size gate. This is a narrow, operator-directed
# exemption — do not add files here without a documented rationale.
#
# skills/develop/SKILL.md: develop/SKILL.md is the governance-dense central
# orchestrator; its untouchable + mandatory-preserve governance content exceeds
# the byte limit and crystallize's 80% preservation floor cannot reach it without
# dropping protected rules. Operator-approved exemption (2026-05-24).
# DEFERRED: split reference material into a sibling file so this exemption
# can be removed.
SIZE_LIMIT_EXEMPT = {
    "commands/crystallize.md",
    "skills/develop/SKILL.md",
}


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


def repo_relative_key(path: Path) -> str:
    """Return the repo-relative POSIX path used for per-file exemption lookups."""
    repo_root = Path(__file__).parent.parent.absolute()
    try:
        return path.absolute().relative_to(repo_root).as_posix()
    except ValueError:
        # Path is outside the repo root; fall back to its own posix form.
        return path.as_posix()


def check_truncation_limits(content: str, errors: list[str], path: Path | None = None) -> None:
    """Check if content exceeds opencode tool output truncation limits.

    Files listed in SIZE_LIMIT_EXEMPT are exempt from the byte/line size gate
    ONLY; all other checks still apply.
    """
    if path is not None and repo_relative_key(path) in SIZE_LIMIT_EXEMPT:
        return

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
    content = path.read_text(encoding="utf-8")
    errors = []
    warnings = []

    # Check truncation limits first (hard error)
    check_truncation_limits(content, errors, path)

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
    content = path.read_text(encoding="utf-8")
    errors = []
    warnings = []

    # Check truncation limits first (hard error)
    check_truncation_limits(content, errors, path)

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
    content = path.read_text(encoding="utf-8")
    errors = []
    warnings = []

    # Check truncation limits first (hard error)
    check_truncation_limits(content, errors, path)

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


# --- Rule module validation -------------------------------------------------
#
# Rule modules (rules/*.md) are standalone instruction files. They deliberately
# do NOT carry the skill/agent apparatus (Invariant Principles, <analysis> and
# <reflection> tags), so validate_skill() would hard-error on every one of them.
# validate_rule_module() therefore uses a relaxed required set and adds the
# checks that matter for a module that must read coherently on its own.

# Instruction tags that must open and close within a single module.
_RULE_MODULE_TAGS = ("CRITICAL", "FORBIDDEN", "RULE", "ROLE", "analysis", "reflection")

# Antigravity enforces a per-rule-file character cap.
_ANTIGRAVITY_FILE_CAP = 12000

# Positional language: a module must not refer to its position in a larger
# document, because any subset of modules may be installed.
_POSITIONAL_TOKENS = (
    "above", "below", "here", "earlier", "later", "following section",
    "preceding", "this section", "as noted", "see above", "see below",
)

# Non-referential uses of a positional token, enumerated by (module id, token).
# These are sequential or temporal, not cross-references. Enumerating them
# rather than pattern-matching keeps a NEW positional use of the same token red.
_POSITIONAL_ALLOWED: dict[tuple[str, str], str] = {
    ("develop-discipline", "preceding"): "'preceded by a Phase Declaration' is sequential",
    ("core-philosophy", "later"): "'an unspecified later' is a temporal noun",
    ("pr-conventions", "above"): "'above all user instructions' describes the harness prompt",
}

# Wording that makes a cross-module reference degrade gracefully.
_CONDITIONAL_MARKERS = (
    "if the", "where the", "when the", "is installed", "are installed",
    "if present", "if installed", "if a ", "where a ",
)

_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_FENCE_RE = re.compile(r"^\s*```")
_LOAD_SKILL_RE = re.compile(r"Load\s+`?[\w-]+`?\s+skill", re.IGNORECASE)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _prose_lines(body: str):
    """Yield (lineno, original, scrubbed) for lines outside code, code spans removed."""
    in_fence = False
    for lineno, line in enumerate(body.splitlines(), 1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        scrubbed = _LOAD_SKILL_RE.sub("", _INLINE_CODE_RE.sub("", line))
        yield lineno, line, scrubbed


def load_rule_modules(rules_dir: Path) -> list[tuple[Path, dict, str]]:
    """Read every rule module as (path, frontmatter, body). Unparseable files get {}."""
    modules = []
    for path in sorted(rules_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(content)
        modules.append((path, frontmatter or {}, body))
    return modules


def _check_frontmatter(fm: dict, path: Path, all_ids: list[str], errors: list[str]) -> None:
    """Section 7.2 field rules, including the quoted-`default` requirement."""
    mid = fm.get("id")
    if not mid:
        errors.append("Frontmatter missing 'id' field")
    elif not isinstance(mid, str) or not _ID_RE.match(mid):
        errors.append(f"'id' must match ^[a-z][a-z0-9-]*$, got {mid!r}")
    elif all_ids.count(mid) > 1:
        errors.append(f"'id' {mid!r} is not unique across rules/")

    if not fm.get("name"):
        errors.append("Frontmatter missing 'name' field")
    if not fm.get("description"):
        errors.append("Frontmatter missing 'description' field")

    cls = fm.get("class")
    if cls not in ("mandatory", "preference"):
        errors.append(f"'class' must be 'mandatory' or 'preference', got {cls!r}")

    default = fm.get("default")
    if cls == "preference":
        # PyYAML is YAML 1.1: bare `on`/`off` parse to bool, which would make
        # every `default == "on"` comparison silently False. Require the quoted
        # form rather than coercing it.
        if isinstance(default, bool):
            errors.append(
                f"'default' parsed as bool {default!r}; write it quoted "
                f'(default: "on" / default: "off")'
            )
        elif default not in ("on", "off"):
            errors.append(f"'default' must be \"on\" or \"off\", got {default!r}")
        if not fm.get("benefit"):
            errors.append("Preference module missing 'benefit' (needed for the selector row)")
        if not fm.get("declining_means"):
            errors.append("Preference module missing 'declining_means'")
    elif cls == "mandatory" and default is not None:
        errors.append("Mandatory module must not carry a 'default' field")

    for field in ("related", "renamed_from", "paths"):
        if field not in fm:
            errors.append(f"Frontmatter missing '{field}' field (may be an empty list)")
        elif not isinstance(fm[field], list):
            errors.append(f"'{field}' must be a list")

    if "superseded_by" not in fm:
        errors.append("Frontmatter missing 'superseded_by' field (may be null)")
    elif fm["superseded_by"] is not None and fm["superseded_by"] not in all_ids:
        errors.append(f"'superseded_by' names unknown id {fm['superseded_by']!r}")

    for prior in fm.get("renamed_from") or []:
        if prior in all_ids:
            errors.append(f"'renamed_from' entry {prior!r} collides with a live module id")


def _check_related(fm: dict, repo_root: Path, errors: list[str]) -> None:
    """Every related: entry resolves to a real skill, command, or agent."""
    for entry in fm.get("related") or []:
        if not isinstance(entry, str):
            errors.append(f"'related' entry {entry!r} is not a string")
            continue
        candidates = [
            repo_root / entry / "SKILL.md",
            repo_root / f"{entry}.md",
        ]
        if not any(c.exists() for c in candidates):
            errors.append(f"'related' entry {entry!r} does not resolve to a repo artifact")


def validate_rule_module(
    path: Path,
    all_modules: list[tuple[Path, dict, str]] | None = None,
) -> ValidationResult:
    """Validate a rule module against the rule-module schema (design section 17)."""
    content = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    check_truncation_limits(content, errors, path)

    frontmatter, body = parse_frontmatter(content)
    repo_root = Path(__file__).parent.parent.absolute()
    if all_modules is None:
        all_modules = load_rule_modules(repo_root / "rules")

    all_ids = [fm.get("id") for _, fm, _ in all_modules if fm.get("id")]

    if not frontmatter:
        errors.append("Missing YAML frontmatter")
        frontmatter = {}
    else:
        _check_frontmatter(frontmatter, path, all_ids, errors)
        _check_related(frontmatter, repo_root, errors)

    this_id = frontmatter.get("id")
    this_class = frontmatter.get("class")

    # Check 1: tag balance. Code spans are excluded so a module may name a tag
    # in prose (e.g. `<ROLE>`) without tripping the scan.
    scrubbed_body = "\n".join(s for _, _, s in _prose_lines(body))
    for tag in _RULE_MODULE_TAGS:
        opened = len(re.findall(rf"<{tag}>", scrubbed_body))
        closed = len(re.findall(rf"</{tag}>", scrubbed_body))
        if opened != closed:
            errors.append(f"Unbalanced <{tag}> tag: {opened} open, {closed} close")

    # Check 2: no positional language.
    positional_re = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in _POSITIONAL_TOKENS) + r")\b", re.IGNORECASE
    )
    for lineno, original, scrubbed in _prose_lines(body):
        for match in positional_re.finditer(scrubbed):
            token = match.group(0).lower()
            if (this_id, token) in _POSITIONAL_ALLOWED:
                continue
            errors.append(
                f"Positional language {token!r} at body line {lineno}: {original.strip()[:70]}"
            )

    # Check 3: no bare reference to another module's heading/name.
    for _, other_fm, _ in all_modules:
        other_id, other_name = other_fm.get("id"), other_fm.get("name")
        if not other_id or not other_name or other_id == this_id:
            continue
        bare_re = re.compile(
            rf"(`{re.escape(other_name)}`|\*\*{re.escape(other_name)}\*\*)", re.IGNORECASE
        )
        for lineno, original, _ in _prose_lines(body):
            if bare_re.search(original) and f"the `{other_id}` module" not in original:
                errors.append(
                    f"Bare reference to module {other_name!r} at body line {lineno}; "
                    f"qualify it as 'the `{other_id}` module'"
                )

    # Check 4: no unconditional mandatory -> preference edge.
    if this_class == "mandatory":
        pref_ids = {
            fm.get("id") for _, fm, _ in all_modules if fm.get("class") == "preference"
        }
        for lineno, original, _ in _prose_lines(body):
            lowered = original.lower()
            for pref_id in pref_ids:
                if (
                    pref_id
                    and f"`{pref_id}`" in original
                    and not any(marker in lowered for marker in _CONDITIONAL_MARKERS)
                ):
                    errors.append(
                        f"Unconditional mandatory->preference reference to "
                        f"{pref_id!r} at body line {lineno}; phrase it conditionally"
                    )

    # Check 7: per-platform size cap.
    byte_count = len(content.encode("utf-8"))
    if byte_count > _ANTIGRAVITY_FILE_CAP:
        errors.append(
            f"Exceeds Antigravity per-file cap: {byte_count:,} > {_ANTIGRAVITY_FILE_CAP:,} chars"
        )

    return ValidationResult(
        path=str(path),
        item_type="rule",
        name=frontmatter.get("name", path.stem),
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        token_count=count_tokens(content),
        line_count=len(content.splitlines()),
        byte_count=byte_count,
    )


def main():
    repo_root = Path(__file__).parent.parent.absolute()
    skills_dir = repo_root / "skills"
    commands_dir = repo_root / "commands"
    agents_dir = repo_root / "agents"
    rules_dir = repo_root / "rules"

    results: list[ValidationResult] = []

    # Validate skills
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                results.append(validate_skill(skill_file))

    # Validate commands
    for cmd_file in sorted(commands_dir.glob("*.md")):
        if not cmd_file.name.startswith("_") and "crystallized2" not in cmd_file.name:
            results.append(validate_command(cmd_file))

    # Validate agents
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            if not agent_file.name.startswith("_") and "crystallized2" not in agent_file.name:
                results.append(validate_agent(agent_file))

    # Validate rule modules
    if rules_dir.exists():
        rule_modules = load_rule_modules(rules_dir)
        for rule_file, _, _ in rule_modules:
            if not rule_file.name.startswith("_"):
                results.append(validate_rule_module(rule_file, rule_modules))

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
