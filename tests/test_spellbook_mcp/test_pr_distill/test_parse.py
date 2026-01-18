"""Tests for pr_distill unified diff parsing."""

import pytest
from spellbook_mcp.pr_distill.parse import parse_diff, parse_file_chunk
from spellbook_mcp.pr_distill.errors import PRDistillError, ErrorCode


class TestParseFileChunkAddedFile:
    """Test parsing newly added files."""

    def test_simple_added_file(self):
        """Parse a simple newly added file."""
        chunk = """diff --git a/newfile.py b/newfile.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/newfile.py
@@ -0,0 +1,3 @@
+def hello():
+    return "hello"
+"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "newfile.py"
        assert result["old_path"] is None
        assert result["status"] == "added"
        assert result["additions"] == 3
        assert result["deletions"] == 0
        assert len(result["hunks"]) == 1

    def test_added_file_line_numbers(self):
        """Verify line numbers are tracked correctly for additions."""
        chunk = """diff --git a/newfile.py b/newfile.py
new file mode 100644
--- /dev/null
+++ b/newfile.py
@@ -0,0 +1,2 @@
+line one
+line two
"""
        result = parse_file_chunk(chunk)
        hunk = result["hunks"][0]

        assert hunk["new_start"] == 1
        assert hunk["new_count"] == 2
        assert len(hunk["lines"]) == 2

        # First added line should be at new line 1
        assert hunk["lines"][0]["type"] == "add"
        assert hunk["lines"][0]["content"] == "line one"
        assert hunk["lines"][0]["new_line_num"] == 1
        assert hunk["lines"][0]["old_line_num"] is None

        # Second added line should be at new line 2
        assert hunk["lines"][1]["new_line_num"] == 2


class TestParseFileChunkModifiedFile:
    """Test parsing modified files."""

    def test_simple_modified_file(self):
        """Parse a simple file modification."""
        chunk = """diff --git a/existing.py b/existing.py
index abc1234..def5678 100644
--- a/existing.py
+++ b/existing.py
@@ -1,3 +1,4 @@
 def hello():
-    return "hello"
+    return "hello world"
+    # new comment
"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "existing.py"
        assert result["old_path"] is None
        assert result["status"] == "modified"
        assert result["additions"] == 2
        assert result["deletions"] == 1

    def test_modified_file_line_numbers(self):
        """Verify line numbers for context, additions, and deletions."""
        chunk = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -10,4 +10,4 @@
 context line
-removed line
+added line
 more context
"""
        result = parse_file_chunk(chunk)
        hunk = result["hunks"][0]

        # Context line at old=10, new=10
        assert hunk["lines"][0]["type"] == "context"
        assert hunk["lines"][0]["old_line_num"] == 10
        assert hunk["lines"][0]["new_line_num"] == 10

        # Removed line at old=11
        assert hunk["lines"][1]["type"] == "remove"
        assert hunk["lines"][1]["old_line_num"] == 11
        assert hunk["lines"][1]["new_line_num"] is None

        # Added line at new=11
        assert hunk["lines"][2]["type"] == "add"
        assert hunk["lines"][2]["old_line_num"] is None
        assert hunk["lines"][2]["new_line_num"] == 11


class TestParseFileChunkDeletedFile:
    """Test parsing deleted files."""

    def test_deleted_file(self):
        """Parse a deleted file."""
        chunk = """diff --git a/removed.py b/removed.py
deleted file mode 100644
index abc1234..0000000
--- a/removed.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def old():
-    pass
"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "removed.py"
        assert result["old_path"] is None
        assert result["status"] == "deleted"
        assert result["additions"] == 0
        assert result["deletions"] == 2


class TestParseFileChunkRenamedFile:
    """Test parsing renamed files."""

    def test_renamed_file_no_changes(self):
        """Parse a file rename with no content changes."""
        chunk = """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "new_name.py"
        assert result["old_path"] == "old_name.py"
        assert result["status"] == "renamed"
        assert result["additions"] == 0
        assert result["deletions"] == 0

    def test_renamed_file_with_changes(self):
        """Parse a file rename with content modifications."""
        chunk = """diff --git a/old.py b/new.py
similarity index 80%
rename from old.py
rename to new.py
--- a/old.py
+++ b/new.py
@@ -1,2 +1,3 @@
 def func():
-    pass
+    return True
+# comment
"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "new.py"
        assert result["old_path"] == "old.py"
        assert result["status"] == "renamed"
        assert result["additions"] == 2
        assert result["deletions"] == 1


class TestParseFileChunkBinaryFile:
    """Test parsing binary files."""

    def test_binary_file(self):
        """Parse a binary file change."""
        chunk = """diff --git a/image.png b/image.png
index abc1234..def5678 100644
Binary files a/image.png and b/image.png differ
"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "image.png"
        assert result["status"] == "modified"
        assert result["additions"] == 0
        assert result["deletions"] == 0
        assert len(result["hunks"]) == 0

    def test_binary_file_added(self):
        """Parse a newly added binary file."""
        chunk = """diff --git a/icon.ico b/icon.ico
new file mode 100644
index 0000000..abc1234
Binary files /dev/null and b/icon.ico differ
"""
        result = parse_file_chunk(chunk)

        assert result["path"] == "icon.ico"
        assert result["status"] == "added"
        assert len(result["hunks"]) == 0


class TestParseFileChunkMultipleHunks:
    """Test parsing files with multiple hunks."""

    def test_multiple_hunks(self):
        """Parse a file with multiple change regions."""
        chunk = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def first():
-    pass
+    return 1
@@ -10,3 +10,4 @@
 def second():
     pass
+    # added
"""
        result = parse_file_chunk(chunk)

        assert len(result["hunks"]) == 2
        assert result["hunks"][0]["old_start"] == 1
        assert result["hunks"][0]["new_start"] == 1
        assert result["hunks"][1]["old_start"] == 10
        assert result["hunks"][1]["new_start"] == 10


class TestParseFileChunkEdgeCases:
    """Test edge cases in file chunk parsing."""

    def test_file_with_spaces_in_name(self):
        """Parse a file with spaces in its path."""
        chunk = """diff --git a/path with spaces/my file.py b/path with spaces/my file.py
new file mode 100644
--- /dev/null
+++ b/path with spaces/my file.py
@@ -0,0 +1 @@
+content
"""
        result = parse_file_chunk(chunk)
        assert result["path"] == "path with spaces/my file.py"

    def test_hunk_with_count_omitted(self):
        """Hunk header with count=1 omitted (just line number)."""
        chunk = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -5 +5 @@
-old
+new
"""
        result = parse_file_chunk(chunk)
        hunk = result["hunks"][0]

        # When count is omitted, it defaults to 1
        assert hunk["old_start"] == 5
        assert hunk["old_count"] == 1
        assert hunk["new_start"] == 5
        assert hunk["new_count"] == 1

    def test_no_newline_at_end_of_file(self):
        """Handle 'No newline at end of file' markers."""
        chunk = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1 +1 @@
-old
\\ No newline at end of file
+new
\\ No newline at end of file
"""
        result = parse_file_chunk(chunk)

        # Should parse without error, ignoring backslash lines
        assert result["deletions"] == 1
        assert result["additions"] == 1

    def test_invalid_header_raises_error(self):
        """Invalid diff header raises PRDistillError."""
        chunk = "not a valid diff header\n+some content\n"

        with pytest.raises(PRDistillError) as exc_info:
            parse_file_chunk(chunk)

        assert exc_info.value.code == ErrorCode.DIFF_PARSE_ERROR
        assert "Could not parse diff header" in str(exc_info.value)


class TestParseDiff:
    """Test parsing complete unified diffs."""

    def test_empty_diff(self):
        """Empty diff returns empty files list."""
        result = parse_diff("")
        assert result["files"] == []
        assert result["warnings"] == []

    def test_whitespace_only_diff(self):
        """Whitespace-only diff returns empty files list."""
        result = parse_diff("   \n  \n")
        assert result["files"] == []
        assert result["warnings"] == []

    def test_single_file_diff(self):
        """Parse diff with one file."""
        diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1 +1 @@
-old
+new
"""
        result = parse_diff(diff)

        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "file.py"

    def test_multiple_files_diff(self):
        """Parse diff with multiple files."""
        diff = """diff --git a/first.py b/first.py
--- a/first.py
+++ b/first.py
@@ -1 +1 @@
-one
+two
diff --git a/second.py b/second.py
new file mode 100644
--- /dev/null
+++ b/second.py
@@ -0,0 +1 @@
+new file
diff --git a/third.py b/third.py
deleted file mode 100644
--- a/third.py
+++ /dev/null
@@ -1 +0,0 @@
-deleted
"""
        result = parse_diff(diff)

        assert len(result["files"]) == 3
        assert result["files"][0]["path"] == "first.py"
        assert result["files"][0]["status"] == "modified"
        assert result["files"][1]["path"] == "second.py"
        assert result["files"][1]["status"] == "added"
        assert result["files"][2]["path"] == "third.py"
        assert result["files"][2]["status"] == "deleted"

    def test_parse_error_collected_as_warning(self):
        """Parse errors for individual files become warnings."""
        diff = """not a valid chunk
diff --git a/valid.py b/valid.py
--- a/valid.py
+++ b/valid.py
@@ -1 +1 @@
-old
+new
"""
        result = parse_diff(diff)

        # Valid file should still be parsed
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "valid.py"
        # No warnings because the invalid part doesn't start with "diff --git"
        assert result["warnings"] == []

    def test_content_before_first_diff(self):
        """Content before first 'diff --git' is ignored."""
        diff = """Some git metadata
commit abc123
Author: Test

diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1 +1 @@
-old
+new
"""
        result = parse_diff(diff)

        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "file.py"
