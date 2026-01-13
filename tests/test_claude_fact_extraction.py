"""
Claude-based fact extraction tests for prompt files.

This module uses Claude CLI in non-interactive mode to extract structured facts
from skill/command/agent files, enabling tests that verify prompt quality
against our documented standards.

Usage:
    pytest tests/test_claude_fact_extraction.py -v

Requires:
    - Claude CLI (`claude`) available in PATH
    - ANTHROPIC_API_KEY environment variable set
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest


# Path to skills directory
REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"


@dataclass
class SkillFacts:
    """Structured facts extracted from a skill file."""

    # Structural properties (deterministic)
    has_yaml_frontmatter: bool
    has_role_tag: bool
    has_forbidden_section: bool
    invariant_principles_count: int

    # Semantic properties (requires judgment)
    description_follows_use_when_pattern: bool

    # Metadata
    file_path: str
    extraction_model: str = "unknown"


# The extraction prompt - designed for reproducibility
EXTRACTION_PROMPT = '''You are a structured data extractor. Your task is to analyze a skill file and extract specific facts.

CRITICAL: Output ONLY valid JSON. No explanations, no markdown, just the JSON object.

Read the following skill file content and extract these properties:

1. has_yaml_frontmatter: Does the file start with a YAML frontmatter block (--- ... ---)?
2. has_role_tag: Is there a <ROLE> tag in the content?
3. has_forbidden_section: Is there a <FORBIDDEN> tag OR a section header containing "FORBIDDEN" or "Anti-Patterns"?
4. invariant_principles_count: Count the numbered items under "## Invariant Principles" (0 if section doesn't exist)
5. description_follows_use_when_pattern: Does the description field in frontmatter start with "Use when" or similar trigger phrase?

Output format (strict JSON, no extra text):
{
  "has_yaml_frontmatter": true,
  "has_role_tag": true,
  "has_forbidden_section": true,
  "invariant_principles_count": 5,
  "description_follows_use_when_pattern": true
}

SKILL FILE CONTENT:
---BEGIN---
%s
---END---

Remember: Output ONLY the JSON object, nothing else.'''


def extract_facts_from_skill(skill_path: Path, timeout: int = 90) -> Optional[SkillFacts]:
    """
    Use Claude CLI to extract structured facts from a skill file.

    Args:
        skill_path: Path to the SKILL.md file
        timeout: Timeout in seconds for Claude CLI call

    Returns:
        SkillFacts dataclass with extracted properties, or None if extraction failed
    """
    if not skill_path.exists():
        return None

    content = skill_path.read_text()
    prompt = EXTRACTION_PROMPT % content

    try:
        result = subprocess.run(
            [
                "claude",
                "-p", prompt,
                "--output-format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "CLAUDE_MODEL": "claude-sonnet-4-20250514"},  # Use faster model for extraction
        )

        if result.returncode != 0:
            print(f"Claude CLI error: {result.stderr}")
            return None

        # Parse the JSON output
        # The --output-format json wraps the response in a JSON object:
        # {"result": "```json\n{...}\n```", "is_error": false, ...}
        # We need to:
        # 1. Parse the outer JSON wrapper
        # 2. Extract the "result" field (the LLM's string response)
        # 3. Strip any markdown code fences (```json ... ```)
        # 4. Parse the inner JSON
        output = json.loads(result.stdout)

        # The actual response is in the 'result' field
        response_text = output.get("result", result.stdout)

        if isinstance(response_text, str):
            # Strip markdown code fences if present
            # Handle both ```json and ``` variants
            # Remove leading ```json or ``` and trailing ```
            response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text.strip())
            response_text = re.sub(r'\n?```\s*$', '', response_text.strip())

            # Find and extract the JSON object
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end > start:
                response_text = response_text[start:end]
            facts_dict = json.loads(response_text)
        else:
            facts_dict = response_text

        return SkillFacts(
            has_yaml_frontmatter=facts_dict.get("has_yaml_frontmatter", False),
            has_role_tag=facts_dict.get("has_role_tag", False),
            has_forbidden_section=facts_dict.get("has_forbidden_section", False),
            invariant_principles_count=facts_dict.get("invariant_principles_count", 0),
            description_follows_use_when_pattern=facts_dict.get("description_follows_use_when_pattern", False),
            file_path=str(skill_path),
            extraction_model="claude-sonnet-4-20250514",
        )

    except subprocess.TimeoutExpired:
        print(f"Claude CLI timed out for {skill_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse Claude response: {e}")
        print(f"Raw output: {result.stdout[:500]}")
        return None
    except Exception as e:
        print(f"Extraction failed: {e}")
        return None


def get_all_skill_files() -> list[Path]:
    """Get all SKILL.md files in the skills directory."""
    return list(SKILLS_DIR.glob("*/SKILL.md"))


# Skip if Claude CLI not available
def claude_cli_available() -> bool:
    """Check if Claude CLI is available and configured."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


requires_claude = pytest.mark.skipif(
    not claude_cli_available(),
    reason="Claude CLI not available"
)


# =============================================================================
# PROOF OF CONCEPT TESTS
# =============================================================================

class TestClaudeFactExtraction:
    """Tests that use Claude CLI to extract and verify facts about skill files."""

    @requires_claude
    def test_extract_facts_instruction_engineering(self):
        """Test fact extraction on instruction-engineering skill."""
        skill_path = SKILLS_DIR / "instruction-engineering" / "SKILL.md"

        facts = extract_facts_from_skill(skill_path)

        assert facts is not None, "Extraction should succeed"
        assert facts.has_yaml_frontmatter is True, "Should have YAML frontmatter"
        assert facts.has_role_tag is True, "Should have <ROLE> tag"
        assert facts.has_forbidden_section is True, "Should have FORBIDDEN section"
        assert facts.invariant_principles_count == 5, "Should have exactly 5 principles"
        assert facts.description_follows_use_when_pattern is True, "Description should start with 'Use when'"

    @requires_claude
    def test_extract_facts_debugging(self):
        """Test fact extraction on debugging skill."""
        skill_path = SKILLS_DIR / "debugging" / "SKILL.md"

        facts = extract_facts_from_skill(skill_path)

        assert facts is not None, "Extraction should succeed"
        assert facts.has_yaml_frontmatter is True, "Should have YAML frontmatter"
        assert facts.has_role_tag is True, "Should have <ROLE> tag"
        assert facts.has_forbidden_section is True, "Should have FORBIDDEN section"
        assert facts.invariant_principles_count == 5, "Should have exactly 5 principles"
        assert facts.description_follows_use_when_pattern is True, "Description should start with 'Use when'"


class TestReproducibility:
    """Tests to verify extraction reproducibility."""

    @requires_claude
    @pytest.mark.parametrize("run", range(3))
    def test_extraction_reproducibility(self, run: int):
        """Run extraction multiple times to check consistency."""
        skill_path = SKILLS_DIR / "instruction-engineering" / "SKILL.md"

        facts = extract_facts_from_skill(skill_path)

        # These should be the same every time
        assert facts is not None
        assert facts.has_yaml_frontmatter is True
        assert facts.has_role_tag is True
        # Note: This test will reveal if extraction is reproducible


class TestAllSkillsMinimumCompliance:
    """Test all skills meet minimum quality standards."""

    @requires_claude
    @pytest.mark.parametrize("skill_path", get_all_skill_files(), ids=lambda p: p.parent.name)
    def test_skill_has_required_structure(self, skill_path: Path):
        """Every skill should have basic required structure."""
        facts = extract_facts_from_skill(skill_path)

        assert facts is not None, f"Extraction failed for {skill_path.parent.name}"
        assert facts.has_yaml_frontmatter, f"{skill_path.parent.name}: Missing YAML frontmatter"
        # Note: Not all skills have ROLE tags yet - this test will reveal which ones


# =============================================================================
# UNIT TESTS (no Claude CLI required)
# =============================================================================

class TestSkillFactsDataclass:
    """Unit tests for the SkillFacts dataclass."""

    def test_skill_facts_creation(self):
        """Test SkillFacts can be created with all fields."""
        facts = SkillFacts(
            has_yaml_frontmatter=True,
            has_role_tag=True,
            has_forbidden_section=True,
            invariant_principles_count=5,
            description_follows_use_when_pattern=True,
            file_path="/path/to/skill.md",
        )

        assert facts.has_yaml_frontmatter is True
        assert facts.invariant_principles_count == 5

    def test_extraction_prompt_contains_all_properties(self):
        """Verify extraction prompt asks for all SkillFacts properties."""
        assert "has_yaml_frontmatter" in EXTRACTION_PROMPT
        assert "has_role_tag" in EXTRACTION_PROMPT
        assert "has_forbidden_section" in EXTRACTION_PROMPT
        assert "invariant_principles_count" in EXTRACTION_PROMPT
        assert "description_follows_use_when_pattern" in EXTRACTION_PROMPT


class TestSkillFileDiscovery:
    """Tests for skill file discovery."""

    def test_skills_directory_exists(self):
        """Skills directory should exist."""
        assert SKILLS_DIR.exists(), f"Skills directory not found at {SKILLS_DIR}"

    def test_finds_skill_files(self):
        """Should find at least some skill files."""
        skills = get_all_skill_files()
        assert len(skills) > 0, "Should find at least one skill file"

    def test_instruction_engineering_exists(self):
        """The instruction-engineering skill should exist (used as test fixture)."""
        skill_path = SKILLS_DIR / "instruction-engineering" / "SKILL.md"
        assert skill_path.exists(), f"instruction-engineering skill not found at {skill_path}"
