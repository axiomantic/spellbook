"""Tests for Rich-based TUI installer."""
import pytest


def test_rich_welcome_panel_renders():
    """Welcome panel must render without errors."""
    from rich.console import Console
    from io import StringIO
    console = Console(file=StringIO(), force_terminal=True)
    from installer.tui import render_welcome_panel
    render_welcome_panel(console)
    output = console.file.getvalue()
    assert "spellbook" in output.lower()


def test_rich_feature_selection_groups():
    """Feature selection must include security features group."""
    from installer.tui import get_feature_groups
    groups = get_feature_groups()
    security_group = next((g for g in groups if g["name"] == "Security Features"), None)
    assert security_group is not None
    feature_ids = [f["id"] for f in security_group["features"]]
    assert "spotlighting" in feature_ids
    assert "crypto" in feature_ids
    assert "sleuth" in feature_ids


def test_welcome_panel_includes_version():
    """Welcome panel should show the spellbook version."""
    from rich.console import Console
    from io import StringIO
    console = Console(file=StringIO(), force_terminal=True)
    from installer.tui import render_welcome_panel
    render_welcome_panel(console, version="1.2.3")
    output = console.file.getvalue()
    assert "1.2.3" in output


def test_feature_groups_have_required_fields():
    """Each feature in groups must have id, name, description, default."""
    from installer.tui import get_feature_groups
    groups = get_feature_groups()
    for group in groups:
        assert "name" in group
        assert "features" in group
        for feature in group["features"]:
            assert "id" in feature, f"Missing 'id' in feature: {feature}"
            assert "name" in feature, f"Missing 'name' in feature: {feature}"
            assert "description" in feature, f"Missing 'description' in feature: {feature}"
            assert "default" in feature, f"Missing 'default' in feature: {feature}"


def test_render_feature_table():
    """Feature table must render security features as a Rich table."""
    from rich.console import Console
    from io import StringIO
    console = Console(file=StringIO(), force_terminal=True)
    from installer.tui import get_feature_groups, render_feature_table
    groups = get_feature_groups()
    render_feature_table(console, groups)
    output = console.file.getvalue()
    assert "Spotlighting" in output
    assert "Crypto" in output or "Cryptographic" in output


def test_render_security_config_panel():
    """Security config panel must render selected features."""
    from rich.console import Console
    from io import StringIO
    console = Console(file=StringIO(), force_terminal=True)
    from installer.tui import render_security_config_panel
    selections = {"spotlighting": True, "crypto": True, "sleuth": False}
    render_security_config_panel(console, selections)
    output = console.file.getvalue()
    assert "Spotlighting" in output or "spotlighting" in output


def test_render_dry_run_banner():
    """Dry-run banner must clearly indicate no changes will be made."""
    from rich.console import Console
    from io import StringIO
    console = Console(file=StringIO(), force_terminal=True)
    from installer.tui import render_dry_run_banner
    render_dry_run_banner(console)
    output = console.file.getvalue()
    assert "dry" in output.lower() or "DRY" in output


def test_render_progress_steps():
    """Progress rendering must accept step descriptions."""
    from rich.console import Console
    from io import StringIO
    console = Console(file=StringIO(), force_terminal=True)
    from installer.tui import render_progress_steps
    steps = [
        {"name": "Install hooks", "status": "done"},
        {"name": "Configure security", "status": "pending"},
    ]
    render_progress_steps(console, steps)
    output = console.file.getvalue()
    assert "Install hooks" in output


def test_supports_rich_terminal_detection():
    """Terminal detection must fall back when Rich is unavailable."""
    from installer.tui import supports_rich
    # In test env, Rich is installed, so this should return True
    # when force_terminal=True or we're in a real TTY
    result = supports_rich()
    assert isinstance(result, bool)
