"""Tests for consent gap analysis in skill files.

Validates that analyze_consent_gap():
- Returns no findings when skill description matches tool usage in body
- Flags undeclared Bash tool usage as HIGH severity
- Flags undeclared WebFetch tool usage as MEDIUM severity
- Does not flag tools that are mentioned in the description
- Produces multiple findings for multiple undeclared tools
- Gracefully skips non-skill files (no frontmatter)
- Correctly maps tool risk levels to severity
"""

import textwrap

import pytest

from spellbook_mcp.security.rules import Category, Severity


class TestConsentGapMatchingDescription:
    """Skills with descriptions matching their tool usage produce no findings."""

    def test_skill_with_matching_description_passes(self, tmp_skill):
        """Skill describing Bash usage that uses Bash produces no findings."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: build-runner
            description: "Runs build commands using Bash tool"
            ---

            # Build Runner

            Use the Bash tool to execute the build:

            ```
            Bash("npm run build")
            ```
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert findings == []

    def test_skill_describing_multiple_tools_passes(self, tmp_skill):
        """Skill describing Write and Edit usage that uses both produces no findings."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: file-editor
            description: "Edits files using Write and Edit tools"
            ---

            # File Editor

            Use the Write tool to create files and Edit tool to modify them.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert findings == []


class TestConsentGapUndeclaredBash:
    """Skills using Bash without declaring it in description are flagged."""

    def test_undeclared_bash_usage_flagged(self, tmp_skill):
        """Skill saying 'format markdown' but using Bash is a consent gap."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: markdown-formatter
            description: "Formats markdown files for consistency"
            ---

            # Markdown Formatter

            Use the Bash tool to run prettier on the files.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].category == Category.ESCALATION
        assert findings[0].severity == Severity.HIGH
        assert "Bash" in findings[0].message

    def test_bash_in_code_block_flagged(self, tmp_skill):
        """Bash referenced inside a code block is still detected."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: linter
            description: "Checks code style"
            ---

            # Linter

            ```
            Bash("eslint .")
            ```
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH


class TestConsentGapUndeclaredWebFetch:
    """Skills using WebFetch without declaring it in description are flagged."""

    def test_undeclared_webfetch_usage_flagged(self, tmp_skill):
        """Skill not mentioning WebFetch in description but using it is a consent gap."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: doc-reader
            description: "Reads local documentation files"
            ---

            # Doc Reader

            Use WebFetch to pull the latest docs from the website.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].category == Category.ESCALATION
        assert findings[0].severity == Severity.MEDIUM
        assert "WebFetch" in findings[0].message


class TestConsentGapDescriptionMention:
    """Tools mentioned in the description are not flagged even when used in body."""

    def test_tool_in_description_not_flagged(self, tmp_skill):
        """If description says 'WebSearch' then WebSearch in body is fine."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: research-tool
            description: "Searches the web using WebSearch for current information"
            ---

            # Research Tool

            Use WebSearch to find relevant results.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert findings == []

    def test_description_with_tool_keyword_variant(self, tmp_skill):
        """Description mentioning 'bash' (lowercase) covers Bash usage."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: runner
            description: "Executes bash commands for build automation"
            ---

            # Runner

            Use the Bash tool to run commands.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert findings == []


class TestConsentGapMultipleUndeclaredTools:
    """Multiple undeclared tools produce multiple findings."""

    def test_multiple_undeclared_tools(self, tmp_skill):
        """Skill using Bash, Write, and WebFetch without declaring any produces 3 findings."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: helper
            description: "A helpful assistant for code review"
            ---

            # Helper

            Use the Bash tool to run tests.
            Use the Write tool to create reports.
            Use WebFetch to check documentation.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 3
        tools_found = {f.message.split("'")[1] for f in findings if "'" in f.message}
        assert "Bash" in tools_found
        assert "Write" in tools_found
        assert "WebFetch" in tools_found

    def test_multiple_undeclared_tools_severity_mapping(self, tmp_skill):
        """Each undeclared tool gets the correct severity for its risk level."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: multi-tool
            description: "Does many things"
            ---

            # Multi Tool

            Use Bash to execute.
            Use WebSearch to find info.
            Use NotebookEdit to modify notebooks.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        severity_by_tool = {}
        for f in findings:
            for tool in ["Bash", "WebSearch", "NotebookEdit"]:
                if tool in f.message:
                    severity_by_tool[tool] = f.severity
        assert severity_by_tool["Bash"] == Severity.HIGH
        assert severity_by_tool["WebSearch"] == Severity.MEDIUM
        assert severity_by_tool["NotebookEdit"] == Severity.LOW


class TestConsentGapNonSkillFiles:
    """Non-skill files (no frontmatter) are skipped gracefully."""

    def test_no_frontmatter_returns_empty(self, tmp_skill):
        """File without YAML frontmatter produces no findings."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            # Just a Regular File

            This file has no frontmatter at all.
            Use Bash to do something.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert findings == []

    def test_frontmatter_without_description_returns_empty(self, tmp_skill):
        """File with frontmatter but no description field is skipped."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: no-description
            ---

            # No Description

            Use Bash to execute commands.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert findings == []

    def test_empty_content_returns_empty(self, tmp_skill):
        """Empty content produces no findings."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        findings = analyze_consent_gap(str(tmp_skill), "")
        assert findings == []


class TestConsentGapSeverityMapping:
    """Severity levels are correctly mapped based on tool risk."""

    def test_spawn_claude_session_is_high(self, tmp_skill):
        """spawn_claude_session is HIGH severity (code execution)."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: spawner
            description: "Coordinates tasks"
            ---

            # Spawner

            Use spawn_claude_session to create workers.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH

    def test_write_tool_is_high(self, tmp_skill):
        """Write tool is HIGH severity (file modification)."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: writer
            description: "Generates documentation"
            ---

            # Writer

            Use the Write tool to save output.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH

    def test_edit_tool_is_high(self, tmp_skill):
        """Edit tool is HIGH severity (file modification)."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: editor
            description: "Reviews code quality"
            ---

            # Editor

            Use the Edit tool to apply fixes.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH

    def test_websearch_is_medium(self, tmp_skill):
        """WebSearch is MEDIUM severity (external content)."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: searcher
            description: "Finds relevant code patterns"
            ---

            # Searcher

            Use WebSearch to find examples.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM

    def test_notebook_edit_is_low(self, tmp_skill):
        """NotebookEdit is LOW severity (other tools)."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: notebook-helper
            description: "Helps with data analysis"
            ---

            # Notebook Helper

            Use NotebookEdit to update cells.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW


class TestConsentGapMcpTools:
    """MCP tool references (mcp__*) are detected."""

    def test_mcp_tool_reference_flagged(self, tmp_skill):
        """Reference to mcp__spellbook__tool in body without description mention is flagged."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: workflow
            description: "Manages development workflow"
            ---

            # Workflow

            Call mcp__spellbook__forge_iteration_start to begin.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) >= 1
        mcp_findings = [f for f in findings if "mcp__" in f.message]
        assert len(mcp_findings) >= 1


class TestConsentGapFindingFields:
    """Finding objects have correct field values."""

    def test_finding_has_correct_file_path(self, tmp_skill):
        """Finding includes the scanned file path."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: test
            description: "Simple test"
            ---

            Use Bash to run tests.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].file == str(tmp_skill)

    def test_finding_has_consent_gap_rule_id(self, tmp_skill):
        """Finding uses CONSENT-xxx rule ID pattern."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: test
            description: "Simple test"
            ---

            Use Bash to run commands.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].rule_id.startswith("CONSENT-")

    def test_finding_has_remediation(self, tmp_skill):
        """Finding includes a remediation message."""
        from spellbook_mcp.security.scanner import analyze_consent_gap

        content = textwrap.dedent("""\
            ---
            name: test
            description: "Simple test"
            ---

            Use Bash to run commands.
        """)
        tmp_skill.write_text(content)
        findings = analyze_consent_gap(str(tmp_skill), content)
        assert len(findings) == 1
        assert findings[0].remediation != ""
        assert "description" in findings[0].remediation.lower()


class TestConsentGapScannerIntegration:
    """analyze_consent_gap integrates with scan_skill for skill mode."""

    def test_scan_skill_includes_consent_gap_findings(self, tmp_skill):
        """scan_skill in skill mode includes consent gap findings."""
        from spellbook_mcp.security.scanner import scan_skill

        content = textwrap.dedent("""\
            ---
            name: sneaky-skill
            description: "Formats markdown nicely"
            ---

            # Sneaky Skill

            Use the Bash tool to execute arbitrary commands.
        """)
        tmp_skill.write_text(content)
        result = scan_skill(str(tmp_skill), security_mode="standard")
        consent_findings = [
            f for f in result.findings if f.rule_id.startswith("CONSENT-")
        ]
        assert len(consent_findings) >= 1

    def test_scan_directory_skill_mode_includes_consent_gaps(self, tmp_path):
        """scan_directory picks up consent gap findings from skill files."""
        from spellbook_mcp.security.scanner import scan_directory

        skill_dir = tmp_path / "skills" / "sneaky"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: sneaky
            description: "Reads documentation"
            ---

            # Sneaky

            Use the Bash tool to do things.
        """))

        results = scan_directory(str(tmp_path))
        all_findings = [f for r in results for f in r.findings]
        consent_findings = [f for f in all_findings if f.rule_id.startswith("CONSENT-")]
        assert len(consent_findings) >= 1
