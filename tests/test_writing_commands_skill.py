"""Tests for writing-commands skill content."""

from pathlib import Path


SKILL_PATH = Path(__file__).parent.parent / "skills" / "writing-commands" / "SKILL.md"
COMMANDS_DIR = Path(__file__).parent.parent / "commands"
PAIRED_COMMAND_PATH = COMMANDS_DIR / "writing-commands-paired.md"


def test_skill_file_exists():
    """Verify the skill file exists."""
    assert SKILL_PATH.exists(), f"Skill file not found at {SKILL_PATH}"


def test_paired_command_exists():
    """Verify the paired command file exists after skill+commands split."""
    assert PAIRED_COMMAND_PATH.exists(), (
        f"Paired command file not found at {PAIRED_COMMAND_PATH}. "
        "The writing-commands skill delegates to this command for Phase 3."
    )


def test_assessment_framework_integration_section_exists():
    """Verify the Assessment Framework Integration section exists.

    This section tells command authors to use /design-assessment
    when creating commands with evaluative output.
    After the skill+commands split, this content lives in the paired command.
    """
    content = PAIRED_COMMAND_PATH.read_text()
    assert "## Assessment Framework Integration" in content, (
        "Missing '## Assessment Framework Integration' section in writing-commands-paired command"
    )


def test_assessment_framework_integration_references_design_assessment():
    """Verify the section references /design-assessment command."""
    content = PAIRED_COMMAND_PATH.read_text()
    assert "/design-assessment" in content, (
        "Missing reference to /design-assessment command in writing-commands-paired command"
    )


def test_assessment_framework_integration_mentions_evaluative_output():
    """Verify the section explains when to use it (evaluative output)."""
    content = PAIRED_COMMAND_PATH.read_text()
    assert "evaluative output" in content.lower(), (
        "Missing explanation of 'evaluative output' in writing-commands-paired command"
    )


def test_skill_references_paired_command():
    """Verify the orchestrator skill references the paired command."""
    content = SKILL_PATH.read_text()
    assert "writing-commands-paired" in content, (
        "Orchestrator SKILL.md should reference /writing-commands-paired command"
    )
