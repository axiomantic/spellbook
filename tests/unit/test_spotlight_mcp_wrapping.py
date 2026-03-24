"""Test MCP tool self-wrapping with spotlight delimiters."""
from pathlib import Path


def test_pr_fetch_has_spotlight_wrapping():
    """pr_fetch must include spotlight wrapping logic."""
    pr_file = Path(__file__).resolve().parent.parent.parent / "spellbook" / "mcp" / "tools" / "pr.py"
    source = pr_file.read_text()
    assert "spotlight_wrap" in source, (
        "pr_fetch tool does not reference spotlight_wrap"
    )
    assert "pr_fetch" in source and "spotlight" in source.lower(), (
        "pr_fetch must spotlight-wrap external diff content"
    )


def test_spotlight_wrap_is_fail_open_in_pr():
    """Spotlight wrapping in pr.py must be fail-open (ImportError caught)."""
    pr_file = Path(__file__).resolve().parent.parent.parent / "spellbook" / "mcp" / "tools" / "pr.py"
    source = pr_file.read_text()
    assert "ImportError" in source, (
        "pr.py must catch ImportError for fail-open spotlight wrapping"
    )
