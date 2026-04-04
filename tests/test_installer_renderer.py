"""Tests for InstallerRenderer ABC, PlainTextRenderer, and RichRenderer in installer/renderer.py."""

from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# InstallerRenderer (ABC)
# ---------------------------------------------------------------------------


class TestInstallerRendererIsAbstract:
    def test_cannot_instantiate_directly(self):
        """InstallerRenderer is abstract and cannot be instantiated directly."""
        from installer.renderer import InstallerRenderer

        with pytest.raises(TypeError):
            InstallerRenderer()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# PlainTextRenderer
# ---------------------------------------------------------------------------


class TestPlainTextRendererInstantiation:
    def test_instantiation_no_args(self):
        """PlainTextRenderer can be instantiated without arguments."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        assert renderer.auto_yes is False

    def test_instantiation_auto_yes(self):
        """PlainTextRenderer accepts auto_yes=True."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer(auto_yes=True)
        assert renderer.auto_yes is True


class TestPlainTextRendererRenderWarning:
    def test_writes_to_stderr(self, capsys):
        """render_warning writes 'Warning: <message>' to stderr."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_warning("something went wrong")

        captured = capsys.readouterr()
        assert captured.err == "Warning: something went wrong\n"
        assert captured.out == ""

    def test_warning_message_included(self, capsys):
        """render_warning includes the exact message text."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_warning("disk almost full")

        captured = capsys.readouterr()
        assert "disk almost full" in captured.err


class TestPlainTextRendererRenderError:
    def test_writes_to_stderr(self, capsys):
        """render_error writes 'Error: <exception>' to stderr."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_error(ValueError("bad value"))

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "bad value" in captured.err
        assert captured.out == ""

    def test_with_context(self, capsys):
        """render_error includes context in the prefix when provided."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_error(RuntimeError("oops"), context="platform install")

        captured = capsys.readouterr()
        assert "platform install" in captured.err
        assert "oops" in captured.err


class TestPlainTextRendererRenderWelcome:
    def test_install_writes_to_stdout(self, capsys):
        """render_welcome (fresh install) writes to stdout."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_welcome("1.2.3", is_upgrade=False)

        captured = capsys.readouterr()
        assert "1.2.3" in captured.out
        assert "Installing" in captured.out
        assert captured.err == ""

    def test_upgrade_writes_to_stdout(self, capsys):
        """render_welcome (upgrade) writes 'Upgrading' to stdout."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_welcome("2.0.0", is_upgrade=True)

        captured = capsys.readouterr()
        assert "Upgrading" in captured.out
        assert "2.0.0" in captured.out


class TestPlainTextRendererPromptYn:
    def test_yes_answer_returns_true(self, monkeypatch):
        """prompt_yn returns True when user enters 'y'."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "y")
        renderer = PlainTextRenderer()
        result = renderer.prompt_yn("Continue?")
        assert result is True

    def test_no_answer_returns_false(self, monkeypatch):
        """prompt_yn returns False when user enters 'n'."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "n")
        renderer = PlainTextRenderer()
        result = renderer.prompt_yn("Continue?", default=True)
        assert result is False

    def test_auto_yes_returns_default_without_input(self, monkeypatch):
        """prompt_yn with auto_yes=True returns default without calling input()."""
        from installer.renderer import PlainTextRenderer

        # input() should never be called; raising an error if it is.
        monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(AssertionError("input() called")))
        renderer = PlainTextRenderer(auto_yes=True)
        assert renderer.prompt_yn("Continue?", default=False) is False
        assert renderer.prompt_yn("Continue?", default=True) is True

    def test_empty_answer_returns_default(self, monkeypatch):
        """Pressing Enter (empty string) returns the default."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "")
        renderer = PlainTextRenderer()
        assert renderer.prompt_yn("Continue?", default=True) is True
        assert renderer.prompt_yn("Continue?", default=False) is False


# ---------------------------------------------------------------------------
# RichRenderer
# ---------------------------------------------------------------------------


class TestPlainTextRendererRenderConfigWizard:
    def test_auto_yes_returns_empty(self):
        """render_config_wizard returns {} immediately when auto_yes=True."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_config_wizard(["spotlighting"], {"foo": "bar"}, is_upgrade=False)
        assert result == {}

    def test_empty_unset_keys_returns_empty(self):
        """render_config_wizard returns {} when unset_keys is empty."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard([], {}, is_upgrade=False)
        assert result == {}

    def test_prompts_for_each_unset_key(self, monkeypatch, capsys):
        """render_config_wizard prompts for each key and collects responses."""
        from installer.renderer import PlainTextRenderer

        inputs = iter(["y", "n"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            ["spotlighting", "crypto"], {}, is_upgrade=False
        )
        assert result == {"spotlighting": True, "crypto": False}

    def test_upgrade_shows_existing_config(self, monkeypatch, capsys):
        """render_config_wizard displays existing config during upgrades."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "y")
        renderer = PlainTextRenderer()
        renderer.render_config_wizard(
            ["spotlighting"], {"crypto": True}, is_upgrade=True
        )
        captured = capsys.readouterr()
        assert "Existing configuration" in captured.out
        assert "crypto" in captured.out

    def test_empty_answer_uses_default(self, monkeypatch):
        """Pressing Enter uses the feature's default value."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "")
        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(["spotlighting"], {}, is_upgrade=False)
        # spotlighting defaults to True
        assert result == {"spotlighting": True}


class TestPlainTextRendererRenderConfigSummary:
    def test_empty_config_returns_true(self):
        """render_config_summary returns True for empty config without prompting."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        assert renderer.render_config_summary({}, confirmed=False) is True

    def test_confirmed_returns_true(self, capsys):
        """render_config_summary returns True when confirmed=True."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        result = renderer.render_config_summary({"crypto": True}, confirmed=True)
        assert result is True
        captured = capsys.readouterr()
        assert "crypto" in captured.out

    def test_auto_yes_returns_true(self, capsys):
        """render_config_summary returns True when auto_yes=True."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_config_summary({"crypto": True}, confirmed=False)
        assert result is True

    def test_user_confirms(self, monkeypatch, capsys):
        """render_config_summary returns True when user types 'y'."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "y")
        renderer = PlainTextRenderer()
        result = renderer.render_config_summary({"crypto": True}, confirmed=False)
        assert result is True

    def test_user_declines(self, monkeypatch, capsys):
        """render_config_summary returns False when user types 'n'."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "n")
        renderer = PlainTextRenderer()
        result = renderer.render_config_summary({"crypto": True}, confirmed=False)
        assert result is False


class TestPlainTextRendererProgressStart:
    def test_prints_step_count(self, capsys):
        """render_progress_start prints the total step count."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_progress_start(5)
        captured = capsys.readouterr()
        assert "5 steps" in captured.out


class TestPlainTextRendererRenderStep:
    def test_platform_start_with_index(self, capsys):
        """render_step 'platform_start' prints name with index/total."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("platform_start", {"name": "Claude", "index": 1, "total": 3})
        captured = capsys.readouterr()
        assert "[1/3]" in captured.out
        assert "Claude" in captured.out

    def test_platform_start_no_index(self, capsys):
        """render_step 'platform_start' prints just name when index/total are 0."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("platform_start", {"name": "Claude", "index": 0, "total": 0})
        captured = capsys.readouterr()
        assert "Claude" in captured.out

    def test_platform_skip(self, capsys):
        """render_step 'platform_skip' prints skip message."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("platform_skip", {"name": "Gemini", "message": "not installed"})
        captured = capsys.readouterr()
        assert "Skipped" in captured.out
        assert "not installed" in captured.out

    def test_step_event(self, capsys):
        """render_step 'step' prints the message."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("step", {"message": "Writing config file"})
        captured = capsys.readouterr()
        assert "Writing config file" in captured.out

    def test_result_success(self, capsys):
        """render_step 'result' prints [OK] for successful result."""
        from installer.renderer import PlainTextRenderer

        result_obj = SimpleNamespace(success=True)
        renderer = PlainTextRenderer()
        renderer.render_step("result", {"result": result_obj})
        captured = capsys.readouterr()
        assert "[OK]" in captured.out

    def test_result_failure(self, capsys):
        """render_step 'result' prints [FAILED] for failed result."""
        from installer.renderer import PlainTextRenderer

        result_obj = SimpleNamespace(success=False)
        renderer = PlainTextRenderer()
        renderer.render_step("result", {"result": result_obj})
        captured = capsys.readouterr()
        assert "[FAILED]" in captured.out

    def test_daemon_start(self, capsys):
        """render_step 'daemon_start' prints daemon message."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("daemon_start", {})
        captured = capsys.readouterr()
        assert "daemon" in captured.out.lower()

    def test_health_start(self, capsys):
        """render_step 'health_start' prints health check message."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("health_start", {})
        captured = capsys.readouterr()
        assert "Health check" in captured.out

    def test_unknown_event_is_noop(self, capsys):
        """render_step silently ignores unknown events."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_step("alien_event", {"foo": "bar"})
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestPlainTextRendererProgressEnd:
    def test_is_noop(self, capsys):
        """render_progress_end is a no-op for PlainTextRenderer."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_progress_end()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestPlainTextRendererRenderCompletion:
    def test_shows_installed_and_failed(self, capsys):
        """render_completion shows installed and failed platforms with elapsed time."""
        from installer.renderer import PlainTextRenderer

        results = SimpleNamespace(
            platforms_installed=["Claude", "Cursor"],
            platforms_failed=["Gemini"],
        )
        renderer = PlainTextRenderer()
        renderer.render_completion(results, elapsed=75.0)
        captured = capsys.readouterr()
        assert "Installation complete" in captured.out
        assert "1m 15s" in captured.out
        assert "[OK]" in captured.out
        assert "Claude" in captured.out
        assert "Cursor" in captured.out
        assert "[FAILED]" in captured.out
        assert "Gemini" in captured.out

    def test_shows_seconds_only(self, capsys):
        """render_completion shows seconds only when under 60s."""
        from installer.renderer import PlainTextRenderer

        results = SimpleNamespace(platforms_installed=["Claude"], platforms_failed=[])
        renderer = PlainTextRenderer()
        renderer.render_completion(results, elapsed=42.0)
        captured = capsys.readouterr()
        assert "42s" in captured.out
        # Should NOT show "0m"
        assert "0m" not in captured.out


class TestPlainTextRendererRenderAdminInfo:
    def test_with_url(self, capsys):
        """render_admin_info prints admin URL."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_admin_info("http://localhost:8765/admin")
        captured = capsys.readouterr()
        assert "http://localhost:8765/admin" in captured.out

    def test_disabled(self, capsys):
        """render_admin_info prints 'disabled' when URL is empty."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_admin_info("")
        captured = capsys.readouterr()
        assert "disabled" in captured.out

    def test_show_token(self, capsys):
        """render_admin_info prints token path when show_token=True."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_admin_info("http://localhost:8765/admin", show_token=True)
        captured = capsys.readouterr()
        assert ".mcp-token" in captured.out

    def test_show_token_no_url(self, capsys):
        """render_admin_info does not show token when URL is empty."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_admin_info("", show_token=True)
        captured = capsys.readouterr()
        assert ".mcp-token" not in captured.out


class TestPlainTextRendererRenderPostInstall:
    def test_empty_notes_no_output(self, capsys):
        """render_post_install produces no output with empty notes list."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_post_install([])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_prints_notes(self, capsys):
        """render_post_install prints each note."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_post_install(["Restart Gemini CLI", "Reload Claude Code"])
        captured = capsys.readouterr()
        assert "Next steps" in captured.out
        assert "Restart Gemini CLI" in captured.out
        assert "Reload Claude Code" in captured.out


class TestPlainTextRendererPromptChoice:
    def test_auto_yes_returns_default(self, monkeypatch):
        """prompt_choice returns default index when auto_yes=True."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr(
            "builtins.input",
            lambda _: (_ for _ in ()).throw(AssertionError("input() called")),
        )
        renderer = PlainTextRenderer(auto_yes=True)
        assert renderer.prompt_choice("Pick:", ["a", "b", "c"], default=1) == 1

    def test_user_selects(self, monkeypatch, capsys):
        """prompt_choice returns selected index (1-based input, 0-based output)."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "2")
        renderer = PlainTextRenderer()
        result = renderer.prompt_choice("Pick:", ["alpha", "beta", "gamma"])
        assert result == 1  # 0-based index for "beta"

    def test_empty_input_returns_default(self, monkeypatch):
        """prompt_choice returns default when user presses Enter."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "")
        renderer = PlainTextRenderer()
        result = renderer.prompt_choice("Pick:", ["a", "b"], default=1)
        assert result == 1

    def test_invalid_input_returns_default(self, monkeypatch):
        """prompt_choice returns default on non-numeric input."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "abc")
        renderer = PlainTextRenderer()
        result = renderer.prompt_choice("Pick:", ["a", "b"], default=0)
        assert result == 0

    def test_out_of_range_clamped(self, monkeypatch):
        """prompt_choice clamps out-of-range values."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "99")
        renderer = PlainTextRenderer()
        result = renderer.prompt_choice("Pick:", ["a", "b", "c"])
        assert result == 2  # clamped to last index

    def test_displays_choices_with_marker(self, monkeypatch, capsys):
        """prompt_choice displays choices with default marker."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "")
        renderer = PlainTextRenderer()
        renderer.prompt_choice("Pick one:", ["alpha", "beta"], default=0)
        captured = capsys.readouterr()
        assert "Pick one:" in captured.out
        assert "alpha" in captured.out
        assert "beta" in captured.out


# ---------------------------------------------------------------------------
# RichRenderer
# ---------------------------------------------------------------------------


class TestRichRendererInstantiation:
    def test_instantiation_no_args(self):
        """RichRenderer can be instantiated without arguments (Rich may or may not be installed)."""
        pytest.importorskip("rich", reason="Rich not installed")
        from installer.renderer import RichRenderer

        renderer = RichRenderer()
        assert renderer.auto_yes is False
        assert renderer._console is None

    def test_instantiation_auto_yes(self):
        """RichRenderer accepts auto_yes=True."""
        pytest.importorskip("rich", reason="Rich not installed")
        from installer.renderer import RichRenderer

        renderer = RichRenderer(auto_yes=True)
        assert renderer.auto_yes is True

    def test_instantiation_with_console(self):
        """RichRenderer stores provided console object."""
        rich = pytest.importorskip("rich", reason="Rich not installed")
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console()
        renderer = RichRenderer(console=console)
        assert renderer._console is console


# ---------------------------------------------------------------------------
# RichRenderer smoke tests (verify methods don't raise)
# ---------------------------------------------------------------------------

_rich_available = pytest.importorskip is not None  # always True; used for skipif below
try:
    import rich as _rich_mod
    _has_rich = True
except ImportError:
    _has_rich = False


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererRenderWelcome:
    def _make_renderer(self):
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        return RichRenderer(console=console), console

    def test_fresh_install(self):
        """render_welcome for fresh install does not raise."""
        renderer, console = self._make_renderer()
        renderer.render_welcome("1.0.0", is_upgrade=False)

    def test_upgrade(self):
        """render_welcome for upgrade does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_welcome("2.0.0", is_upgrade=True)


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererRenderError:
    def _make_renderer(self):
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        return RichRenderer(console=console), console

    def test_without_context(self):
        """render_error without context does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_error(RuntimeError("boom"))

    def test_with_context(self):
        """render_error with context does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_error(ValueError("bad"), context="install step")


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererRenderWarning:
    def _make_renderer(self):
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        return RichRenderer(console=console), console

    def test_warning(self):
        """render_warning does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_warning("heads up")


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererPromptYn:
    def test_auto_yes_returns_default(self):
        """prompt_yn returns default when auto_yes=True."""
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        renderer = RichRenderer(auto_yes=True, console=console)
        assert renderer.prompt_yn("Continue?", default=False) is False
        assert renderer.prompt_yn("Continue?", default=True) is True


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererPromptChoice:
    def test_auto_yes_returns_default(self):
        """prompt_choice returns default when auto_yes=True."""
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        renderer = RichRenderer(auto_yes=True, console=console)
        assert renderer.prompt_choice("Pick:", ["a", "b"], default=1) == 1


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererConfigWizard:
    def test_auto_yes_returns_empty(self):
        """render_config_wizard returns {} when auto_yes=True."""
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        renderer = RichRenderer(auto_yes=True, console=console)
        assert renderer.render_config_wizard(["spotlighting"], {}, is_upgrade=False) == {}

    def test_empty_unset_keys_returns_empty(self):
        """render_config_wizard returns {} when unset_keys is empty."""
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        renderer = RichRenderer(console=console)
        assert renderer.render_config_wizard([], {}, is_upgrade=False) == {}


# ---------------------------------------------------------------------------
# PlainTextRenderer upgrade tests
# ---------------------------------------------------------------------------


class TestPlainTextRendererUpgrade:
    def test_plain_text_render_welcome_upgrade(self, capsys):
        """render_welcome with is_upgrade=True prints 'Upgrading' and version."""
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer()
        renderer.render_welcome("3.1.0", is_upgrade=True)

        captured = capsys.readouterr()
        assert "Upgrading" in captured.out
        assert "3.1.0" in captured.out

    def test_plain_text_render_config_wizard_upgrade_shows_existing(self, monkeypatch, capsys):
        """When is_upgrade=True and existing_config has entries, existing config is printed before prompts."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "y")
        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            unset_keys=["sleuth"],
            existing_config={"spotlighting": True, "crypto": True, "lodo": True},
            is_upgrade=True,
        )
        captured = capsys.readouterr()
        # Existing config should be displayed
        assert "Existing configuration" in captured.out
        assert "spotlighting" in captured.out
        assert "crypto" in captured.out
        assert "lodo" in captured.out
        # The unset key should have been prompted and collected
        assert result == {"sleuth": True}

    def test_plain_text_render_config_wizard_upgrade_only_prompts_unset(self, monkeypatch, capsys):
        """When unset_keys has 1 of 4 keys, only that key is prompted."""
        from installer.renderer import PlainTextRenderer

        call_count = 0

        def counting_input(prompt):
            nonlocal call_count
            call_count += 1
            return "n"

        monkeypatch.setattr("builtins.input", counting_input)
        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            unset_keys=["crypto"],
            existing_config={"spotlighting": True, "sleuth": False, "lodo": True},
            is_upgrade=True,
        )
        # Only one prompt should have been issued (for the single unset key)
        assert call_count == 1
        assert result == {"crypto": False}
        # The existing keys should not appear as prompts
        captured = capsys.readouterr()
        assert "Existing configuration" in captured.out


# ---------------------------------------------------------------------------
# RichRenderer upgrade smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererUpgrade:
    def _make_renderer(self):
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        return RichRenderer(console=console), console

    def test_rich_render_welcome_upgrade(self):
        """render_welcome with is_upgrade=True renders upgrade panel without error."""
        renderer, console = self._make_renderer()
        renderer.render_welcome("3.0.0", is_upgrade=True)
        output = console.file.getvalue()
        assert "Upgrade" in output or "3.0.0" in output

    def test_rich_render_config_wizard_upgrade_shows_existing(self):
        """render_config_wizard with is_upgrade=True and existing_config does not raise."""
        from installer.renderer import RichRenderer

        renderer, console = self._make_renderer()
        renderer_auto = RichRenderer(auto_yes=True, console=console)
        # auto_yes=True skips prompts; we just verify no exception with upgrade args
        result = renderer_auto.render_config_wizard(
            unset_keys=["sleuth"],
            existing_config={"spotlighting": True, "crypto": True},
            is_upgrade=True,
        )
        assert result == {}


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererPostInstall:
    def _make_renderer(self):
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        return RichRenderer(console=console), console

    def test_empty_notes_no_output(self):
        """render_post_install with empty notes does not raise."""
        renderer, console = self._make_renderer()
        renderer.render_post_install([])

    def test_with_notes(self):
        """render_post_install with notes does not raise."""
        renderer, console = self._make_renderer()
        renderer.render_post_install(["Restart Claude", "Reload config"])


@pytest.mark.skipif(not _has_rich, reason="Rich not installed")
class TestRichRendererAdminInfo:
    def _make_renderer(self):
        from rich.console import Console
        from installer.renderer import RichRenderer

        console = Console(file=__import__("io").StringIO(), force_terminal=True)
        return RichRenderer(console=console), console

    def test_with_url(self):
        """render_admin_info with URL does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_admin_info("http://localhost:8765/admin")

    def test_disabled(self):
        """render_admin_info with empty URL does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_admin_info("")

    def test_with_token(self):
        """render_admin_info with show_token does not raise."""
        renderer, _ = self._make_renderer()
        renderer.render_admin_info("http://localhost:8765/admin", show_token=True)


# ---------------------------------------------------------------------------
# Config wizard filtering bug fix (dotted keys vs bare feature IDs)
# ---------------------------------------------------------------------------


class TestConfigWizardFilteringBugFix:
    """Verify that dotted config keys correctly match bare feature IDs.

    The bug: render_config_wizard receives unset_keys as dotted strings
    (e.g. "security.crypto.enabled") from get_unset_config_keys(), but
    feature IDs in get_feature_groups() are bare (e.g. "crypto"). The
    original code compared them directly, which never matched.
    """

    def test_rich_renderer_dotted_keys_match_features(self, monkeypatch):
        """RichRenderer.render_config_wizard matches dotted keys to feature IDs.

        Passes dotted keys like "security.crypto.enabled" as unset_keys.
        Before the fix, the filtering produces no matching features and
        returns {}. After the fix, features are matched and selections
        are collected.
        """
        pytest.importorskip("rich", reason="Rich not installed")
        import io
        from rich.console import Console
        from installer.renderer import RichRenderer

        # Mock Confirm.ask to always return True
        monkeypatch.setattr(
            "rich.prompt.Confirm.ask",
            lambda *a, **kw: True,
        )

        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = RichRenderer(console=console)

        result = renderer.render_config_wizard(
            unset_keys=["security.crypto.enabled", "security.sleuth.enabled"],
            existing_config={},
            is_upgrade=False,
        )

        # Before fix: {} (no features matched dotted keys)
        # After fix: {"crypto": True, "sleuth": True}
        assert result == {"crypto": True, "sleuth": True}

    def test_rich_renderer_bare_keys_still_work(self, monkeypatch):
        """RichRenderer.render_config_wizard still works with bare feature IDs.

        Ensures backwards compatibility: bare IDs like "crypto" that match
        feature IDs directly should continue to work.
        """
        pytest.importorskip("rich", reason="Rich not installed")
        import io
        from rich.console import Console
        from installer.renderer import RichRenderer

        monkeypatch.setattr(
            "rich.prompt.Confirm.ask",
            lambda *a, **kw: True,
        )

        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = RichRenderer(console=console)

        result = renderer.render_config_wizard(
            unset_keys=["crypto"],
            existing_config={},
            is_upgrade=False,
        )

        assert result == {"crypto": True}

    def test_rich_renderer_mixed_dotted_and_bare_keys(self, monkeypatch):
        """RichRenderer handles a mix of dotted and bare keys in unset_keys."""
        pytest.importorskip("rich", reason="Rich not installed")
        import io
        from rich.console import Console
        from installer.renderer import RichRenderer

        monkeypatch.setattr(
            "rich.prompt.Confirm.ask",
            lambda *a, **kw: True,
        )

        console = Console(file=io.StringIO(), force_terminal=True)
        renderer = RichRenderer(console=console)

        result = renderer.render_config_wizard(
            unset_keys=["security.crypto.enabled", "sleuth"],
            existing_config={},
            is_upgrade=False,
        )

        assert result == {"crypto": True, "sleuth": True}

    def test_plain_text_dotted_keys_match_features(self, monkeypatch):
        """PlainTextRenderer.render_config_wizard matches dotted keys to feature IDs.

        Before fix: _feature_meta.get("security.crypto.enabled") misses
        and falls through to {"name": "security.crypto.enabled", "default": True},
        returning {"security.crypto.enabled": True} instead of {"crypto": True}.
        After fix: extracts "crypto" from the dotted key, looks it up in
        _feature_meta, and returns {"crypto": True}.
        """
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "y")

        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            unset_keys=["security.crypto.enabled"],
            existing_config={},
            is_upgrade=False,
        )

        # After fix: key in result should be the bare feature ID
        assert result == {"crypto": True}

    def test_plain_text_dotted_keys_use_correct_metadata(self, monkeypatch):
        """PlainTextRenderer uses correct feature metadata for dotted keys.

        "security.sleuth.enabled" should map to the "sleuth" feature which
        has default=False. When user presses Enter (empty input), the
        default should be used.
        """
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "")

        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            unset_keys=["security.sleuth.enabled"],
            existing_config={},
            is_upgrade=False,
        )

        # sleuth's default is False
        assert result == {"sleuth": False}

    def test_plain_text_bare_keys_still_work(self, monkeypatch):
        """PlainTextRenderer still works with bare feature IDs (backwards compat)."""
        from installer.renderer import PlainTextRenderer

        monkeypatch.setattr("builtins.input", lambda _prompt: "y")

        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            unset_keys=["crypto"],
            existing_config={},
            is_upgrade=False,
        )

        assert result == {"crypto": True}

    def test_plain_text_multiple_dotted_keys(self, monkeypatch):
        """PlainTextRenderer handles multiple dotted keys correctly."""
        from installer.renderer import PlainTextRenderer

        inputs = iter(["y", "n"])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

        renderer = PlainTextRenderer()
        result = renderer.render_config_wizard(
            unset_keys=["security.spotlighting.enabled", "security.crypto.enabled"],
            existing_config={},
            is_upgrade=False,
        )

        assert result == {"spotlighting": True, "crypto": False}
