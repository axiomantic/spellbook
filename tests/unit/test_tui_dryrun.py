"""Tests for TUI dry-run mode and terminal fallback."""
import sys
from io import StringIO


def test_dry_run_banner_visible():
    """Dry-run banner must be clearly visible."""
    from rich.console import Console
    from installer.tui import render_dry_run_banner
    console = Console(file=StringIO(), force_terminal=True)
    render_dry_run_banner(console)
    output = console.file.getvalue()
    assert "DRY RUN" in output.upper()
    assert "no changes" in output.lower()


def test_progress_steps_show_all_states():
    """Progress rendering must handle done, pending, failed, running states."""
    from rich.console import Console
    from installer.tui import render_progress_steps
    console = Console(file=StringIO(), force_terminal=True)
    steps = [
        {"name": "Step A", "status": "done"},
        {"name": "Step B", "status": "running"},
        {"name": "Step C", "status": "pending"},
        {"name": "Step D", "status": "failed"},
    ]
    render_progress_steps(console, steps)
    output = console.file.getvalue()
    assert "Step A" in output
    assert "Step B" in output
    assert "Step C" in output
    assert "Step D" in output


def test_supports_rich_false_when_dumb_terminal(monkeypatch):
    """supports_rich must return False for TERM=dumb."""
    from installer.tui import supports_rich
    monkeypatch.setenv("TERM", "dumb")
    assert supports_rich() is False


def test_supports_rich_false_when_rich_missing(monkeypatch):
    """supports_rich must return False if Rich is not importable."""
    import importlib
    import installer.tui

    # Remove rich from sys.modules so the import inside supports_rich retries
    saved = sys.modules.pop("rich", None)
    # Block re-import of rich by inserting None (triggers ImportError)
    monkeypatch.setitem(sys.modules, "rich", None)

    # Reload the module so the top-level state is fresh
    importlib.reload(installer.tui)
    try:
        result = installer.tui.supports_rich()
        assert result is False
    finally:
        # Restore rich so other tests are unaffected
        if saved is not None:
            sys.modules["rich"] = saved
        else:
            sys.modules.pop("rich", None)
        importlib.reload(installer.tui)


def test_plain_text_fallback_header():
    """When Rich is unavailable, plain text header from ui.py should work."""
    from installer.ui import print_header
    # Just ensure it doesn't crash (it writes to stdout)
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        print_header(version="1.0.0")
        output = sys.stdout.getvalue()
        assert "Spellbook" in output
        assert "1.0.0" in output
    finally:
        sys.stdout = old_stdout


def test_render_feature_table_plain_fallback():
    """Feature table should still render when force_terminal=False."""
    from rich.console import Console
    from installer.tui import get_feature_groups, render_feature_table
    console = Console(file=StringIO(), force_terminal=False, no_color=True)
    groups = get_feature_groups()
    render_feature_table(console, groups)
    output = console.file.getvalue()
    # Even without colors, feature names should appear
    assert "Spotlighting" in output
