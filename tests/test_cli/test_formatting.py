"""Tests for spellbook.cli.formatting - output formatting."""

import io
import json

import pytest

from spellbook.cli.formatting import output


class TestJsonMode:
    """Tests for JSON output mode."""

    def test_json_mode_dict(self):
        buf = io.StringIO()
        output({"key": "value", "count": 42}, json_mode=True, file=buf)
        result = json.loads(buf.getvalue())
        assert result == {"key": "value", "count": 42}

    def test_json_mode_list(self):
        buf = io.StringIO()
        output([{"a": 1}, {"a": 2}], json_mode=True, file=buf)
        result = json.loads(buf.getvalue())
        assert result == [{"a": 1}, {"a": 2}]

    def test_json_mode_string(self):
        buf = io.StringIO()
        output("hello", json_mode=True, file=buf)
        result = json.loads(buf.getvalue())
        assert result == "hello"

    def test_json_mode_uses_default_str(self):
        """Non-serializable objects should use str() as fallback."""
        from pathlib import Path

        buf = io.StringIO()
        test_path = Path("/tmp/test")
        output({"path": test_path}, json_mode=True, file=buf)
        result = json.loads(buf.getvalue())
        assert result["path"] == str(test_path)

    def test_json_mode_indented(self):
        buf = io.StringIO()
        output({"a": 1}, json_mode=True, file=buf)
        text = buf.getvalue()
        # Should be indented (pretty-printed)
        assert "\n" in text


class TestDictMode:
    """Tests for key-value pair output (dict, non-JSON)."""

    def test_dict_output_aligned(self):
        buf = io.StringIO()
        output({"name": "spellbook", "version": "1.0"}, file=buf)
        text = buf.getvalue()
        # Should contain key-value pairs
        assert "name" in text
        assert "spellbook" in text
        assert "version" in text
        assert "1.0" in text

    def test_dict_output_keys_right_aligned(self):
        buf = io.StringIO()
        output({"a": "1", "long_key": "2"}, file=buf)
        lines = buf.getvalue().rstrip("\n").split("\n")
        # Keys should be right-aligned (longer key sets the width)
        assert len(lines) == 2
        # The colon positions should be aligned
        colon_positions = [line.index(":") for line in lines if ":" in line]
        assert len(set(colon_positions)) == 1  # All colons at same position


class TestListMode:
    """Tests for tabular output (list of dicts, non-JSON)."""

    def test_list_of_dicts_tabular(self):
        buf = io.StringIO()
        data = [
            {"name": "alice", "age": 30},
            {"name": "bob", "age": 25},
        ]
        output(data, file=buf)
        text = buf.getvalue()
        assert "alice" in text
        assert "bob" in text

    def test_list_with_headers(self):
        buf = io.StringIO()
        data = [
            {"name": "alice", "age": 30},
        ]
        output(data, headers=["name", "age"], file=buf)
        text = buf.getvalue()
        assert "NAME" in text or "name" in text.split("\n")[0].lower()

    def test_list_column_width_calculation(self):
        buf = io.StringIO()
        data = [
            {"x": "short", "y": "a"},
            {"x": "very long value here", "y": "b"},
        ]
        output(data, file=buf)
        lines = buf.getvalue().strip().split("\n")
        # Header + 2 data rows
        assert len(lines) >= 2


class TestStringMode:
    """Tests for plain string output."""

    def test_string_printed_as_is(self):
        buf = io.StringIO()
        output("hello world", file=buf)
        assert buf.getvalue().strip() == "hello world"

    def test_integer_printed_as_string(self):
        buf = io.StringIO()
        output(42, file=buf)
        assert "42" in buf.getvalue()


class TestDefaultFile:
    """Test that default file is stdout."""

    def test_default_to_stdout(self, capsys):
        output("test output")
        captured = capsys.readouterr()
        assert "test output" in captured.out
