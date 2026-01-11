# tests/test_verify_command.py
"""Tests for the verify command structure and content."""
import pytest
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY_PATH = os.path.join(REPO_ROOT, 'commands', 'verify.md')


@pytest.fixture
def verify_content():
    """Load verify command content."""
    with open(VERIFY_PATH, 'r') as f:
        return f.read()


class TestVerifyStructure:
    """Test that verify command has required structure."""

    def test_file_exists(self):
        """Verify command file must exist."""
        assert os.path.exists(VERIFY_PATH), f"Verify command not found at {VERIFY_PATH}"

    def test_has_frontmatter(self, verify_content):
        """Must have YAML frontmatter with description."""
        assert verify_content.startswith('---'), "Missing YAML frontmatter"
        assert 'description:' in verify_content[:500], "Missing description in frontmatter"

    def test_has_iron_law(self, verify_content):
        """Must have the iron law about verification."""
        assert 'Iron Law' in verify_content or 'IRON LAW' in verify_content, \
            "Missing Iron Law section"

    def test_has_gate_function(self, verify_content):
        """Must have the gate function process."""
        assert 'Gate Function' in verify_content or 'gate function' in verify_content.lower(), \
            "Missing Gate Function section"


class TestVerifyAntiPatterns:
    """Test that verify command documents anti-patterns."""

    def test_documents_common_failures(self, verify_content):
        """Must document common verification failures."""
        assert 'Common Failure' in verify_content or 'Not Sufficient' in verify_content, \
            "Should document common failures"

    def test_documents_red_flags(self, verify_content):
        """Must document red flags to watch for."""
        assert 'Red Flag' in verify_content or 'STOP' in verify_content, \
            "Should document red flags"

    def test_warns_about_should(self, verify_content):
        """Must warn about using 'should' without verification."""
        assert 'should' in verify_content.lower(), \
            "Should warn about 'should' without verification"

    def test_warns_about_probably(self, verify_content):
        """Must warn about 'probably' without verification."""
        assert 'probably' in verify_content.lower(), \
            "Should warn about 'probably' without verification"

    def test_warns_about_trusting_agents(self, verify_content):
        """Must warn about trusting agent success reports."""
        content_lower = verify_content.lower()
        assert 'agent' in content_lower and ('trust' in content_lower or 'verify' in content_lower), \
            "Should warn about trusting agent reports"


class TestVerifyPatterns:
    """Test that verify command includes key patterns."""

    def test_documents_test_verification(self, verify_content):
        """Must document test verification pattern."""
        assert 'test' in verify_content.lower() and 'pass' in verify_content.lower(), \
            "Should document test verification pattern"

    def test_documents_build_verification(self, verify_content):
        """Must document build verification pattern."""
        content_lower = verify_content.lower()
        assert 'build' in content_lower, "Should document build verification"

    def test_documents_regression_testing(self, verify_content):
        """Must document regression test verification (red-green)."""
        assert 'regression' in verify_content.lower() or 'red-green' in verify_content.lower(), \
            "Should document regression test verification"

    def test_documents_when_to_apply(self, verify_content):
        """Must document when to apply verification."""
        assert 'When To Apply' in verify_content or 'ALWAYS' in verify_content, \
            "Should document when to apply verification"


class TestVerifyRationalizations:
    """Test that verify command addresses rationalizations."""

    def test_documents_rationalizations(self, verify_content):
        """Must document common rationalizations."""
        assert 'Rationalization' in verify_content or 'Excuse' in verify_content, \
            "Should document common rationalizations"

    def test_addresses_confidence_excuse(self, verify_content):
        """Must address 'I'm confident' as insufficient."""
        content_lower = verify_content.lower()
        assert 'confident' in content_lower, "Should address confidence excuse"

    def test_addresses_tiredness_excuse(self, verify_content):
        """Must address tiredness as insufficient excuse."""
        content_lower = verify_content.lower()
        assert 'tired' in content_lower or 'exhaustion' in content_lower, \
            "Should address tiredness excuse"


class TestVerifyQuality:
    """Test quality indicators for verify command."""

    def test_not_too_short(self, verify_content):
        """Verify command must have substantial content."""
        lines = verify_content.strip().split('\n')
        assert len(lines) >= 50, f"Verify seems too short ({len(lines)} lines)"

    def test_has_examples(self, verify_content):
        """Should have examples for clarity."""
        code_blocks = re.findall(r'```', verify_content)
        assert len(code_blocks) >= 4, "Should have at least 2 code block examples"

    def test_has_bottom_line(self, verify_content):
        """Should have clear bottom line statement."""
        assert 'Bottom Line' in verify_content or 'non-negotiable' in verify_content.lower(), \
            "Should have clear bottom line statement"

    def test_evidence_before_claims(self, verify_content):
        """Core principle: evidence before claims."""
        content_lower = verify_content.lower()
        assert 'evidence' in content_lower and 'claim' in content_lower, \
            "Should emphasize evidence before claims"
