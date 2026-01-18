"""Tests for PR distill MCP tools registered in server.py.

Uses .fn to access the underlying function from the FunctionTool wrapper
created by the @mcp.tool() decorator.
"""

import pytest
from unittest.mock import patch, MagicMock

# Import the MCP server module to access the tools
from spellbook_mcp import server


class TestPrDiff:
    """Tests for pr_diff MCP tool."""

    def test_parses_diff_correctly(self):
        """pr_diff parses unified diff into FileDiff objects."""
        raw_diff = """diff --git a/foo.py b/foo.py
index abc123..def456 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line1
+added_line
 line2
 line3
"""
        result = server.pr_diff.fn(raw_diff)

        assert "files" in result
        assert "warnings" in result
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "foo.py"
        assert result["files"][0]["status"] == "modified"
        assert result["files"][0]["additions"] == 1
        assert result["files"][0]["deletions"] == 0
        # Verify hunk structure exists
        assert len(result["files"][0].get("hunks", [])) > 0
        assert result["warnings"] == []  # Explicitly verify no warnings

    def test_parses_empty_diff(self):
        """pr_diff handles empty diff string."""
        result = server.pr_diff.fn("")

        assert result["files"] == []
        assert result["warnings"] == []

    def test_parses_multiple_files(self):
        """pr_diff parses diff with multiple files."""
        raw_diff = """diff --git a/foo.py b/foo.py
index abc123..def456 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
-old_line
+new_line
 context
diff --git a/bar.py b/bar.py
new file mode 100644
--- /dev/null
+++ b/bar.py
@@ -0,0 +1,2 @@
+line1
+line2
"""
        result = server.pr_diff.fn(raw_diff)

        assert len(result["files"]) == 2
        assert result["files"][0]["path"] == "foo.py"
        assert result["files"][1]["path"] == "bar.py"
        assert result["files"][1]["status"] == "added"


class TestPrFiles:
    """Tests for pr_files MCP tool."""

    def test_extracts_file_list(self):
        """pr_files extracts file list from pr_fetch result."""
        pr_result = {
            "meta": {
                "files": [
                    {"path": "foo.py", "additions": 5, "deletions": 2},
                    {"path": "bar.py", "additions": 10, "deletions": 0},
                    {"path": "baz.py", "additions": 0, "deletions": 8},
                ]
            }
        }

        result = server.pr_files.fn(pr_result)

        assert len(result) == 3
        assert result[0]["path"] == "foo.py"
        assert result[0]["status"] == "modified"  # has both additions and deletions
        assert result[1]["path"] == "bar.py"
        assert result[1]["status"] == "added"  # only additions
        assert result[2]["path"] == "baz.py"
        assert result[2]["status"] == "deleted"  # only deletions

    def test_handles_empty_files_list(self):
        """pr_files handles empty files list."""
        pr_result = {"meta": {"files": []}}

        result = server.pr_files.fn(pr_result)

        assert result == []

    def test_handles_missing_files_key(self):
        """pr_files handles missing files key gracefully."""
        pr_result = {"meta": {}}

        result = server.pr_files.fn(pr_result)

        assert result == []


class TestPrMatchPatterns:
    """Tests for pr_match_patterns MCP tool."""

    def test_matches_patterns(self, tmp_path):
        """pr_match_patterns matches patterns against files."""
        files = [
            {
                # Pattern expects /migrations/ in path (note the leading slash)
                "path": "app/migrations/0001_initial.py",
                "old_path": None,
                "status": "added",
                "hunks": [],
                "additions": 10,
                "deletions": 0,
            }
        ]

        result = server.pr_match_patterns.fn(
            files=files,
            project_root=str(tmp_path),
            custom_patterns=None,
        )

        assert "matched" in result
        assert "unmatched" in result
        assert "patterns_checked" in result
        # migration-file pattern should match (regex: /migrations/.*\.py$)
        assert "migration-file" in result["matched"]
        # Verify match has content (not just key existence)
        assert len(result["matched"]["migration-file"]) > 0
        # Verify patterns were actually checked
        assert result["patterns_checked"] > 0

    def test_returns_unmatched_files(self, tmp_path):
        """pr_match_patterns returns unmatched files."""
        files = [
            {
                "path": "random_file.xyz",
                "old_path": None,
                "status": "modified",
                "hunks": [],
                "additions": 1,
                "deletions": 1,
            }
        ]

        result = server.pr_match_patterns.fn(
            files=files,
            project_root=str(tmp_path),
            custom_patterns=None,
        )

        assert len(result["unmatched"]) == 1
        assert result["unmatched"][0]["path"] == "random_file.xyz"
        # Verify matched is truly empty (no spurious matches)
        assert len(result["matched"]) == 0 or all(
            len(v) == 0 for v in result["matched"].values()
        )


class TestPrBlessPattern:
    """Tests for pr_bless_pattern MCP tool."""

    def test_blesses_valid_pattern(self, tmp_path):
        """pr_bless_pattern blesses a valid pattern."""
        result = server.pr_bless_pattern.fn(
            project_root=str(tmp_path),
            pattern_id="my-custom-pattern",
        )

        assert result["success"] is True
        assert result["pattern_id"] == "my-custom-pattern"
        assert result.get("error") is None
        # Verify already_blessed is False for first blessing
        assert result.get("already_blessed") is False or "already_blessed" not in result

    def test_rejects_invalid_pattern(self, tmp_path):
        """pr_bless_pattern rejects invalid pattern ID."""
        result = server.pr_bless_pattern.fn(
            project_root=str(tmp_path),
            pattern_id="INVALID_PATTERN",  # uppercase not allowed
        )

        assert result["success"] is False
        assert "error" in result
        # Verify error message is meaningful
        assert len(result["error"]) > 0
        assert result["pattern_id"] == "INVALID_PATTERN"

    def test_reports_already_blessed(self, tmp_path):
        """pr_bless_pattern reports when pattern already blessed."""
        # Bless once
        server.pr_bless_pattern.fn(
            project_root=str(tmp_path),
            pattern_id="my-pattern",
        )

        # Bless again
        result = server.pr_bless_pattern.fn(
            project_root=str(tmp_path),
            pattern_id="my-pattern",
        )

        assert result["success"] is True
        assert result["already_blessed"] is True


class TestPrListPatterns:
    """Tests for pr_list_patterns MCP tool."""

    def test_returns_all_patterns(self, tmp_path):
        """pr_list_patterns returns builtin and blessed patterns."""
        # First bless a pattern
        server.pr_bless_pattern.fn(
            project_root=str(tmp_path),
            pattern_id="my-blessed-pattern",
        )

        result = server.pr_list_patterns.fn(project_root=str(tmp_path))

        assert "builtin" in result
        assert "blessed" in result
        assert "total" in result
        assert len(result["builtin"]) > 0
        assert "my-blessed-pattern" in result["blessed"]
        assert result["total"] == len(result["builtin"]) + len(result["blessed"])

    def test_returns_only_builtin_without_project_root(self):
        """pr_list_patterns returns only builtin patterns without project_root."""
        result = server.pr_list_patterns.fn(project_root=None)

        assert "builtin" in result
        assert len(result["builtin"]) > 0
        assert result["blessed"] == []

    def test_builtin_patterns_have_required_fields(self):
        """pr_list_patterns builtin patterns have required fields."""
        result = server.pr_list_patterns.fn(project_root=None)

        for pattern in result["builtin"]:
            assert "id" in pattern
            assert "confidence" in pattern
            assert "priority" in pattern
            assert "description" in pattern


class TestPrFetch:
    """Tests for pr_fetch MCP tool."""

    @patch("spellbook_mcp.pr_distill.fetch.check_gh_version")
    @patch("spellbook_mcp.pr_distill.fetch.run_command")
    def test_fetches_pr_by_number(self, mock_run_command, mock_check_version):
        """pr_fetch fetches PR by number (mocked)."""
        mock_check_version.return_value = True
        mock_run_command.side_effect = [
            "origin\thttps://github.com/owner/repo.git (fetch)",  # git remote get-url
            '{"number": 123, "title": "Test PR", "files": []}',  # gh pr view
            "diff content here",  # gh pr diff
        ]

        result = server.pr_fetch.fn("123")

        assert "meta" in result
        assert "diff" in result
        assert result["meta"]["number"] == 123
        # Verify mocks were actually called
        mock_check_version.assert_called_once()
        assert mock_run_command.call_count == 3  # remote, pr view, pr diff

    @patch("spellbook_mcp.pr_distill.fetch.check_gh_version")
    @patch("spellbook_mcp.pr_distill.fetch.run_command")
    def test_fetches_pr_by_url(self, mock_run_command, mock_check_version):
        """pr_fetch fetches PR by URL (mocked)."""
        mock_check_version.return_value = True
        mock_run_command.side_effect = [
            '{"number": 456, "title": "Another PR", "files": []}',  # gh pr view
            "diff content",  # gh pr diff
        ]

        result = server.pr_fetch.fn("https://github.com/owner/repo/pull/456")

        assert result["meta"]["number"] == 456
        assert result["repo"] == "owner/repo"
        # Verify mocks were actually called
        mock_check_version.assert_called_once()
        assert mock_run_command.call_count == 2  # pr view, pr diff (no remote needed for URL)
