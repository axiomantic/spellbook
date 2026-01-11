# tests/test_handoff_command.py
"""Tests for the handoff command structure and content."""
import pytest
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDOFF_PATH = os.path.join(REPO_ROOT, 'commands', 'handoff.md')


@pytest.fixture
def handoff_content():
    """Load handoff command content."""
    with open(HANDOFF_PATH, 'r') as f:
        return f.read()


class TestHandoffStructure:
    """Test that handoff command has required structure."""

    def test_file_exists(self):
        """Handoff command file must exist."""
        assert os.path.exists(HANDOFF_PATH), f"Handoff command not found at {HANDOFF_PATH}"

    def test_has_frontmatter(self, handoff_content):
        """Must have YAML frontmatter with description."""
        assert handoff_content.startswith('---'), "Missing YAML frontmatter"
        assert 'description:' in handoff_content[:500], "Missing description in frontmatter"

    def test_has_role_section(self, handoff_content):
        """Must have ROLE section for instruction engineering."""
        assert '<ROLE>' in handoff_content, "Missing <ROLE> section"
        assert '</ROLE>' in handoff_content, "Missing </ROLE> closing tag"

    def test_has_section_0(self, handoff_content):
        """Must have Section 0: Mandatory First Actions."""
        assert 'SECTION 0' in handoff_content, "Missing Section 0"
        assert 'MANDATORY FIRST ACTIONS' in handoff_content.upper() or 'Execute Before Reading' in handoff_content, \
            "Section 0 should be about mandatory first actions"

    def test_has_section_1(self, handoff_content):
        """Must have Section 1: Session Context."""
        assert 'SECTION 1' in handoff_content, "Missing Section 1"

    def test_has_section_2(self, handoff_content):
        """Must have Section 2: Continuation Protocol."""
        assert 'SECTION 2' in handoff_content, "Missing Section 2"

    def test_workflow_restoration_in_section_0(self, handoff_content):
        """Workflow restoration must be in Section 0, not Section 1."""
        # Find Section 0 position
        section_0_match = re.search(r'SECTION 0', handoff_content)
        section_1_match = re.search(r'SECTION 1', handoff_content)

        assert section_0_match is not None, "Section 0 not found"
        assert section_1_match is not None, "Section 1 not found"

        # Find workflow restoration
        workflow_match = re.search(r'Workflow Restoration', handoff_content)
        assert workflow_match is not None, "Workflow Restoration section not found"

        # Workflow restoration should be between Section 0 and Section 1
        assert section_0_match.start() < workflow_match.start() < section_1_match.start(), \
            "Workflow Restoration must be in Section 0 (before Section 1)"


class TestHandoffAntiPatterns:
    """Test that handoff command addresses key anti-patterns."""

    def test_documents_absolute_paths(self, handoff_content):
        """Must emphasize absolute paths over relative paths."""
        content_lower = handoff_content.lower()
        assert 'absolute' in content_lower, "Should mention absolute paths"
        # Check for anti-pattern about relative paths
        assert 'relative' in content_lower or '/absolute/path' in handoff_content, \
            "Should warn about relative paths"

    def test_documents_plan_search(self, handoff_content):
        """Must document searching for planning documents."""
        assert 'plans/' in handoff_content, "Should reference plans directory"
        assert 'search' in handoff_content.lower() or 'find' in handoff_content.lower(), \
            "Should mention searching for plans"

    def test_documents_skill_invocation(self, handoff_content):
        """Must document skill invocation pattern."""
        assert 'Skill(' in handoff_content or 'skill' in handoff_content.lower(), \
            "Should document skill invocation"

    def test_documents_todowrite(self, handoff_content):
        """Must document TodoWrite for state restoration."""
        assert 'TodoWrite' in handoff_content, "Should document TodoWrite for state restoration"


class TestHandoffSubsections:
    """Test required subsections in handoff command."""

    def test_has_document_reads_section(self, handoff_content):
        """Must have document reads section."""
        assert 'Document Read' in handoff_content or 'Required Document' in handoff_content, \
            "Should have document reads section"

    def test_has_todo_restoration(self, handoff_content):
        """Must have todo state restoration."""
        assert 'Todo' in handoff_content, "Should have todo restoration section"

    def test_has_organizational_structure(self, handoff_content):
        """Must document organizational structure."""
        assert 'Organizational' in handoff_content or 'Organization' in handoff_content or \
               'Main Chat Agent' in handoff_content, \
            "Should document organizational structure"

    def test_has_verification_commands(self, handoff_content):
        """Must include verification commands."""
        assert 'verif' in handoff_content.lower(), "Should mention verification"


class TestHandoffQuality:
    """Test quality indicators for handoff command."""

    def test_not_too_short(self, handoff_content):
        """Handoff command must have substantial content."""
        lines = handoff_content.strip().split('\n')
        assert len(lines) >= 100, f"Handoff seems too short ({len(lines)} lines), may be missing content"

    def test_has_examples(self, handoff_content):
        """Should have examples for clarity."""
        # Look for code blocks which typically contain examples
        code_blocks = re.findall(r'```', handoff_content)
        assert len(code_blocks) >= 4, "Should have at least 2 code block examples (4 backtick pairs)"

    def test_has_emotional_stakes(self, handoff_content):
        """Should have emotional stakes for instruction engineering."""
        assert 'EMOTIONAL_STAKES' in handoff_content or 'Failure consequences' in handoff_content or \
               'anxiety' in handoff_content.lower(), \
            "Should have emotional stakes section"
