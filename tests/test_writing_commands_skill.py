"""Tests for writing-commands skill content."""

from pathlib import Path


SKILL_PATH = Path(__file__).parent.parent / "skills" / "writing-commands" / "SKILL.md"


def test_skill_file_exists():
    """Verify the skill file exists."""
    assert SKILL_PATH.exists(), f"Skill file not found at {SKILL_PATH}"


def test_assessment_framework_integration_section_exists():
    """Verify the Assessment Framework Integration section exists.
    
    This section tells command authors to use /design-assessment
    when creating commands with evaluative output.
    """
    content = SKILL_PATH.read_text()
    assert "## Assessment Framework Integration" in content, (
        "Missing '## Assessment Framework Integration' section in writing-commands skill"
    )


def test_assessment_framework_integration_references_design_assessment():
    """Verify the section references /design-assessment command."""
    content = SKILL_PATH.read_text()
    assert "/design-assessment" in content, (
        "Missing reference to /design-assessment command in writing-commands skill"
    )


def test_assessment_framework_integration_mentions_evaluative_output():
    """Verify the section explains when to use it (evaluative output)."""
    content = SKILL_PATH.read_text()
    assert "evaluative output" in content.lower(), (
        "Missing explanation of 'evaluative output' in writing-commands skill"
    )


def test_assessment_framework_integration_section_location():
    """Verify the section appears after Command Testing Protocol and before Example."""
    content = SKILL_PATH.read_text()
    
    testing_protocol_pos = content.find("## Command Testing Protocol")
    assessment_section_pos = content.find("## Assessment Framework Integration")
    example_pos = content.find("## Example: Complete Command")
    
    assert testing_protocol_pos != -1, "Missing '## Command Testing Protocol' section"
    assert example_pos != -1, "Missing '## Example: Complete Command' section"
    
    if assessment_section_pos != -1:
        assert testing_protocol_pos < assessment_section_pos < example_pos, (
            "Assessment Framework Integration section should be between "
            "Command Testing Protocol and Example: Complete Command"
        )
