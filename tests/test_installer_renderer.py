"""Tests for InstallerRenderer ABC, PlainTextRenderer, and RichRenderer in installer/renderer.py."""

import sys
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
