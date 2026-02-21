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

    # Additional structural properties
    has_analysis_tag: bool  # <analysis> tag present
    has_reflection_tag: bool  # <reflection> tag present
    has_self_check_section: bool  # Self-Check or Self Check section
    has_inputs_section: bool  # Inputs table/section
    has_outputs_section: bool  # Outputs table/section

    # Emotional stimuli and quality properties
    has_positive_emotional_stimulus: bool  # Contains phrases like "important to my career", "ensure impeccable reasoning"
    has_negative_emotional_stimulus: bool  # Contains consequence framing like "errors will cause", "negative impact"
    has_example_section: bool  # Has example or <EXAMPLE> section
    token_count_estimate: int  # Rough token estimate (count words * 1.3)
    meets_token_budget: bool  # Under 1500 tokens for skills

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
6. has_analysis_tag: Is there an <analysis> tag in the content?
7. has_reflection_tag: Is there a <reflection> tag in the content?
8. has_self_check_section: Is there a section header containing "Self-Check" or "Self Check" (case insensitive)?
9. has_inputs_section: Is there an "## Inputs" section or a table with input parameters?
10. has_outputs_section: Is there an "## Outputs" section or a table with output/deliverable information?
11. has_positive_emotional_stimulus: Contains positive emotional framing phrases like "important to my career", "ensure impeccable reasoning", "this matters deeply", "your expertise is crucial", "take pride in", "demonstrate excellence"?
12. has_negative_emotional_stimulus: Contains negative consequence framing like "errors will cause", "negative impact", "failure will result in", "mistakes lead to", "will harm", "critical failure"?
13. has_example_section: Is there an <example> or <EXAMPLE> tag, OR a section header containing "Example" or "Examples"?
14. token_count_estimate: Count all words in the file and multiply by 1.3 (round to nearest integer). Words are whitespace-separated tokens.
15. meets_token_budget: Is the token_count_estimate under 1500?

Output format (strict JSON, no extra text):
{
  "has_yaml_frontmatter": true,
  "has_role_tag": true,
  "has_forbidden_section": true,
  "invariant_principles_count": 5,
  "description_follows_use_when_pattern": true,
  "has_analysis_tag": false,
  "has_reflection_tag": false,
  "has_self_check_section": true,
  "has_inputs_section": true,
  "has_outputs_section": true,
  "has_positive_emotional_stimulus": true,
  "has_negative_emotional_stimulus": false,
  "has_example_section": true,
  "token_count_estimate": 1200,
  "meets_token_budget": true
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
                "--tools", "",
                "--disable-slash-commands",
                "--setting-sources", "",
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
            has_analysis_tag=facts_dict.get("has_analysis_tag", False),
            has_reflection_tag=facts_dict.get("has_reflection_tag", False),
            has_self_check_section=facts_dict.get("has_self_check_section", False),
            has_inputs_section=facts_dict.get("has_inputs_section", False),
            has_outputs_section=facts_dict.get("has_outputs_section", False),
            has_positive_emotional_stimulus=facts_dict.get("has_positive_emotional_stimulus", False),
            has_negative_emotional_stimulus=facts_dict.get("has_negative_emotional_stimulus", False),
            has_example_section=facts_dict.get("has_example_section", False),
            token_count_estimate=facts_dict.get("token_count_estimate", 0),
            meets_token_budget=facts_dict.get("meets_token_budget", False),
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
    """Check if Claude CLI is available and configured.

    Returns False if running inside a Claude Code session (nested sessions
    are not supported and will fail), or if the CLI is not installed.
    """
    # Claude Code sets CLAUDECODE env var; nested sessions are not supported
    if os.environ.get("CLAUDECODE"):
        return False
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
        assert facts.invariant_principles_count == 6, "Should have exactly 6 principles"
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
        assert facts.invariant_principles_count == 9, "Should have exactly 9 principles"
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
    """Test all skills meet minimum quality standards.

    Quality standards for skills:
    - has_yaml_frontmatter: Required for all skills (discovery, metadata)
    - has_role_tag: Required for all skills (agent persona clarity)
    - has_forbidden_section: Required for quality skills (guardrails)
    - invariant_principles_count >= 3: Required for quality skills (core tenets)
    - description_follows_use_when_pattern: Required (trigger clarity)
    """

    # Token budget target and tolerance for LLM-based estimation.
    # The LLM's word-count-based token estimates vary by ~5-10% between runs,
    # so we apply a 10% tolerance margin to avoid flaky failures on borderline
    # skills. Skills genuinely over budget (e.g., 2340 tokens) still fail.
    TOKEN_BUDGET = 1500
    TOKEN_BUDGET_TOLERANCE = 1.1  # 10% margin
    TOKEN_BUDGET_HARD_LIMIT = int(TOKEN_BUDGET * TOKEN_BUDGET_TOLERANCE)  # 1650

    # Skills with known token budget issues - xfail until condensed
    # TODO: Run /optimizing-instructions on each to bring under 1500 tokens
    KNOWN_OVER_BUDGET_SKILLS = {
        "debugging",
        "reviewing-design-docs",
        "dispatching-parallel-agents",
        "executing-plans",
        "fact-checking",
        "finding-dead-code",
        "fixing-tests",
        "auditing-green-mirage",
        "reviewing-impl-plans",
        "implementing-features",
        "instruction-engineering",
        "project-encyclopedia",
        "receiving-code-review",
        "smart-reading",
        "test-driven-development",
        "using-git-worktrees",
        "merging-worktrees",
        "writing-skills",
    }

    @requires_claude
    @pytest.mark.parametrize("skill_path", get_all_skill_files(), ids=lambda p: p.parent.name)
    def test_skill_has_required_structure(self, skill_path: Path):
        """Every skill should meet all quality standards.

        Failing tests indicate either:
        1. Skill needs improvement to meet standards
        2. Standards need adjustment for edge cases
        3. Extraction prompt needs refinement for accuracy
        """
        skill_name = skill_path.parent.name

        # Mark known over-budget skills as expected failures
        if skill_name in self.KNOWN_OVER_BUDGET_SKILLS:
            pytest.xfail(f"{skill_name} exceeds token budget - pending condensation")

        facts = extract_facts_from_skill(skill_path)

        assert facts is not None, f"Extraction failed for {skill_name}"

        # Collect all failures for comprehensive reporting
        failures = []
        warnings = []

        # Property 1: YAML frontmatter (required for all skills)
        if not facts.has_yaml_frontmatter:
            failures.append(
                f"has_yaml_frontmatter=False: Missing YAML frontmatter block (--- ... ---)"
            )

        # Property 2: ROLE tag (required for all skills)
        if not facts.has_role_tag:
            failures.append(
                f"has_role_tag=False: Missing <ROLE> tag for agent persona"
            )

        # Property 3: FORBIDDEN section (required for quality skills)
        if not facts.has_forbidden_section:
            failures.append(
                f"has_forbidden_section=False: Missing <FORBIDDEN> tag or Anti-Patterns section"
            )

        # Property 4: Invariant principles count (>= 3 for quality skills)
        if facts.invariant_principles_count < 3:
            failures.append(
                f"invariant_principles_count={facts.invariant_principles_count}: "
                f"Expected >= 3 numbered principles under '## Invariant Principles'"
            )

        # Property 5: Description follows "Use when" pattern
        if not facts.description_follows_use_when_pattern:
            failures.append(
                f"description_follows_use_when_pattern=False: "
                f"Description should start with 'Use when' or similar trigger phrase"
            )

        # Property 6: Analysis tag (recommended for structured thinking)
        if not facts.has_analysis_tag:
            warnings.append(
                f"has_analysis_tag=False: Consider adding <analysis> tag for structured reasoning"
            )

        # Property 7: Reflection tag (recommended for self-correction)
        if not facts.has_reflection_tag:
            warnings.append(
                f"has_reflection_tag=False: Consider adding <reflection> tag for self-correction"
            )

        # Property 8: Self-Check section (recommended for quality verification)
        if not facts.has_self_check_section:
            warnings.append(
                f"has_self_check_section=False: Consider adding Self-Check section for verification"
            )

        # Property 9: Inputs section (optional but recommended for complex skills)
        if not facts.has_inputs_section:
            warnings.append(
                f"has_inputs_section=False: Consider adding Inputs section for clarity"
            )

        # Property 10: Outputs section (optional but recommended for complex skills)
        if not facts.has_outputs_section:
            warnings.append(
                f"has_outputs_section=False: Consider adding Outputs section for clarity"
            )

        # Property 11: Positive emotional stimulus (recommended per EmotionPrompt research)
        if not facts.has_positive_emotional_stimulus:
            warnings.append(
                f"has_positive_emotional_stimulus=False: Consider adding positive emotional framing "
                f"(e.g., 'important to my career', 'ensure impeccable reasoning') per EmotionPrompt research"
            )

        # Property 12: Negative emotional stimulus (recommended per EmotionPrompt research)
        if not facts.has_negative_emotional_stimulus:
            warnings.append(
                f"has_negative_emotional_stimulus=False: Consider adding consequence framing "
                f"(e.g., 'errors will cause', 'negative impact') per EmotionPrompt research"
            )

        # Property 13: Example section (recommended for clarity)
        if not facts.has_example_section:
            warnings.append(
                f"has_example_section=False: Consider adding <example> section for concrete guidance"
            )

        # Property 14-15: Token budget with tolerance for LLM estimation variance.
        # The LLM reports meets_token_budget against a hard 1500 cutoff, but its
        # word-count estimates vary ~5-10% between runs. To avoid flaky failures on
        # borderline skills, we apply a 10% tolerance: skills estimated between
        # 1500-1650 get a warning, skills over 1650 fail.
        if not facts.meets_token_budget:
            if facts.token_count_estimate > self.TOKEN_BUDGET_HARD_LIMIT:
                failures.append(
                    f"meets_token_budget=False: Skill exceeds token budget hard limit "
                    f"(estimated {facts.token_count_estimate} tokens > {self.TOKEN_BUDGET_HARD_LIMIT} "
                    f"tolerance threshold). Consider condensing."
                )
            else:
                warnings.append(
                    f"meets_token_budget=False: Skill is borderline on token budget "
                    f"(estimated {facts.token_count_estimate} tokens, budget={self.TOKEN_BUDGET}, "
                    f"tolerance={self.TOKEN_BUDGET_HARD_LIMIT}). LLM estimation variance may "
                    f"cause this to fluctuate between runs. Consider condensing."
                )

        # Print soft warnings (do not fail test)
        if warnings:
            warning_report = "\n  - ".join(warnings)
            print(f"\n[WARNINGS] {skill_name} missing optional properties:\n  - {warning_report}")

        # Report all failures at once for comprehensive feedback
        if failures:
            failure_report = "\n  - ".join(failures)
            pytest.fail(
                f"\n{skill_name} failed quality checks:\n  - {failure_report}\n\n"
                f"Extracted facts: {facts}"
            )


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
            has_analysis_tag=True,
            has_reflection_tag=False,
            has_self_check_section=True,
            has_inputs_section=True,
            has_outputs_section=False,
            has_positive_emotional_stimulus=True,
            has_negative_emotional_stimulus=False,
            has_example_section=True,
            token_count_estimate=1200,
            meets_token_budget=True,
            file_path="/path/to/skill.md",
        )

        assert facts.has_yaml_frontmatter is True
        assert facts.invariant_principles_count == 5
        assert facts.has_analysis_tag is True
        assert facts.has_reflection_tag is False
        assert facts.has_self_check_section is True
        assert facts.has_inputs_section is True
        assert facts.has_outputs_section is False
        assert facts.has_positive_emotional_stimulus is True
        assert facts.has_negative_emotional_stimulus is False
        assert facts.has_example_section is True
        assert facts.token_count_estimate == 1200
        assert facts.meets_token_budget is True

    def test_extraction_prompt_contains_all_properties(self):
        """Verify extraction prompt asks for all SkillFacts properties."""
        assert "has_yaml_frontmatter" in EXTRACTION_PROMPT
        assert "has_role_tag" in EXTRACTION_PROMPT
        assert "has_forbidden_section" in EXTRACTION_PROMPT
        assert "invariant_principles_count" in EXTRACTION_PROMPT
        assert "description_follows_use_when_pattern" in EXTRACTION_PROMPT
        assert "has_analysis_tag" in EXTRACTION_PROMPT
        assert "has_reflection_tag" in EXTRACTION_PROMPT
        assert "has_self_check_section" in EXTRACTION_PROMPT
        assert "has_inputs_section" in EXTRACTION_PROMPT
        assert "has_outputs_section" in EXTRACTION_PROMPT
        assert "has_positive_emotional_stimulus" in EXTRACTION_PROMPT
        assert "has_negative_emotional_stimulus" in EXTRACTION_PROMPT
        assert "has_example_section" in EXTRACTION_PROMPT
        assert "token_count_estimate" in EXTRACTION_PROMPT
        assert "meets_token_budget" in EXTRACTION_PROMPT


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
