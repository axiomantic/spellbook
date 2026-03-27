"""Integration test: full TUI in dry-run mode.

Exercises the complete TUI workflow: welcome panel, feature groups,
security config panel, progress steps, and dry-run banner, all
rendering to a captured StringIO console.
"""
import sys

import pytest

if sys.platform == "win32":
    pytest.skip("TUI depends on termios (Unix-only)", allow_module_level=True)

from io import StringIO

from rich.console import Console

from installer.tui import (
    LiveProgressDisplay,
    get_feature_groups,
    render_completion_summary,
    render_dry_run_banner,
    render_feature_table,
    render_progress_steps,
    render_security_config_panel,
    render_welcome_panel,
    supports_rich,
)
from installer.components.security import (
    apply_security_config,
    get_default_security_config,
    get_security_config_keys,
    get_security_summary,
)


def test_full_tui_dry_run_workflow():
    """Complete dry-run TUI workflow must render without errors."""
    console = Console(file=StringIO(), force_terminal=True, width=100)

    # Step 1: Welcome panel
    render_welcome_panel(console, version="0.35.0")

    # Step 2: Dry-run banner
    render_dry_run_banner(console)

    # Step 3: Feature groups
    groups = get_feature_groups()
    render_feature_table(console, groups)

    # Step 4: User selects features (simulated)
    selections = {"spotlighting": True, "crypto": True, "sleuth": False, "lodo": True}

    # Step 5: Security config panel
    render_security_config_panel(console, selections)

    # Step 6: Progress steps
    steps = [
        {"name": "Install MCP daemon", "status": "done"},
        {"name": "Configure security features", "status": "done"},
        {"name": "Install Claude Code hooks", "status": "done"},
        {"name": "Generate signing keys", "status": "done"},
    ]
    render_progress_steps(console, steps)

    output = console.file.getvalue()

    # Verify key content is present
    assert "Spellbook" in output
    assert "0.35.0" in output
    assert "DRY RUN" in output.upper()
    assert "Spotlighting" in output
    assert "Install MCP daemon" in output


def test_security_config_keys_complete():
    """All security config keys must have defaults and be enumerable."""
    keys = get_security_config_keys()
    defaults = get_default_security_config()

    # All keys must have a default
    for key in keys:
        assert key in defaults, f"Key {key} missing from defaults"

    # Verify minimum key count (4 features x at least 2 keys each)
    assert len(keys) >= 8

    # Verify all feature prefixes are present
    prefixes = {k.rsplit(".", 1)[0] for k in keys}
    assert "security.spotlighting" in {p.rsplit(".", 1)[0] for p in prefixes} or \
           any(k.startswith("security.spotlighting.") for k in keys)
    assert any(k.startswith("security.crypto.") for k in keys)
    assert any(k.startswith("security.sleuth.") for k in keys)
    assert any(k.startswith("security.lodo.") for k in keys)


def test_dry_run_apply_returns_all_selected_keys():
    """Dry-run apply must return the keys it would write."""
    import bigfoot

    selections = {"spotlighting": True, "crypto": True, "sleuth": False, "lodo": True}

    def mock_config_set(key, value):
        raise AssertionError("Should not write in dry-run mode")

    proxy = bigfoot.mock("installer.components.security:_config_set")
    proxy.__call__.required(False).calls(mock_config_set)

    with bigfoot:
        keys = apply_security_config(selections, dry_run=True)

    assert len(keys) > 0
    # Should include keys for all selected features
    assert any(k.startswith("security.spotlighting.") for k in keys)
    assert any(k.startswith("security.crypto.") for k in keys)
    assert any(k.startswith("security.sleuth.") for k in keys)
    assert any(k.startswith("security.lodo.") for k in keys)


def test_security_summary_readable():
    """Security summary must be human-readable for all combinations."""
    selections_variants = [
        {"spotlighting": True, "crypto": True, "sleuth": True, "lodo": True},
        {"spotlighting": False, "crypto": False, "sleuth": False, "lodo": False},
        {"spotlighting": True, "crypto": False, "sleuth": False, "lodo": True},
    ]
    for selections in selections_variants:
        summary = get_security_summary(selections)
        assert isinstance(summary, str)
        assert len(summary) > 0
        # Should mention each feature by name
        for feat_id in selections:
            # At least the feature ID concept should be referenced
            assert any(
                word in summary.lower()
                for word in [feat_id, feat_id.replace("_", " ")]
            ), f"Feature {feat_id} not mentioned in summary: {summary}"


def test_live_progress_display_lifecycle():
    """LiveProgressDisplay must start, accept events, and stop without errors."""
    console = Console(file=StringIO(), force_terminal=True, width=100)
    display = LiveProgressDisplay(console=console, dry_run=False)
    display.start()

    display.begin_section("MCP Daemon")
    display.add_step("Starting daemon")
    display.complete_step(success=True)
    display.add_step("Checking health")
    display.complete_step(success=False)

    display.begin_section("Claude Code", index=1, total=2)
    display.add_step("Installing hooks")
    display.complete_step(success=True)

    display.skip_section("Platform not found")

    display.stop()


def test_live_progress_display_renders_sections():
    """LiveProgressDisplay output must contain section headers and step text."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    display = LiveProgressDisplay(console=console, dry_run=False)
    display.start()

    display.begin_section("Test Platform", index=1, total=3)
    display.add_step("Step one")
    display.complete_step(success=True)
    display.add_step("Step two")
    display.complete_step(success=False)

    display.stop()

    output = buf.getvalue()
    assert "Test Platform" in output
    assert "Step one" in output
    assert "Step two" in output
    assert "Elapsed" in output


def test_completion_summary_success():
    """Completion summary for all-success must show checkmarks and 'Complete'."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    render_completion_summary(
        console,
        platforms_installed=["claude_code", "opencode"],
        platforms_failed=[],
        elapsed_seconds=42.5,
    )
    output = buf.getvalue()
    assert "Complete" in output
    assert "42s" in output
    # Checkmark character
    assert "\u2713" in output


def test_completion_summary_with_failures():
    """Completion summary with failures must show X marks and 'Failed'."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    render_completion_summary(
        console,
        platforms_installed=["claude_code"],
        platforms_failed=["gemini"],
        elapsed_seconds=15.0,
    )
    output = buf.getvalue()
    assert "Failed" in output
    # X mark character
    assert "\u2717" in output
