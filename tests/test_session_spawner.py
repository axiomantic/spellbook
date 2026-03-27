"""Tests for session spawning functionality."""

import os
import subprocess
from pathlib import Path

import bigfoot
import pytest
from dirty_equals import IsInstance, IsTuple

from spellbook.session.spawner import SessionSpawner


@pytest.fixture
def spawner():
    """Create a SessionSpawner instance."""
    return SessionSpawner()


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    return {
        "SPELLBOOK_SWARM_ID": "test-swarm-123",
        "SPELLBOOK_PACKET_ID": "packet-456",
        "SPELLBOOK_COORDINATION_BACKEND": "filesystem",
        "SPELLBOOK_CONFIG_PATH": "/test/config/path",
    }


class TestSessionSpawner:
    """Test SessionSpawner class."""

    def test_spawner_initialization(self, spawner):
        """Test that spawner initializes correctly."""
        assert spawner is not None
        assert isinstance(spawner, SessionSpawner)

    def test_detect_terminal_type_iterm2(self, spawner, monkeypatch):
        """Test detecting iTerm2 terminal."""
        monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
        terminal_type = spawner.detect_terminal()
        assert terminal_type == "iterm2"

    def test_detect_terminal_type_terminal(self, spawner, monkeypatch):
        """Test detecting Terminal.app."""
        monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
        terminal_type = spawner.detect_terminal()
        assert terminal_type == "terminal"

    def test_detect_terminal_type_tmux(self, spawner, monkeypatch):
        """Test detecting tmux."""
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.setenv("TERM", "screen")

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/local/bin/tmux")

        with bigfoot:
            terminal_type = spawner.detect_terminal()

        assert terminal_type == "tmux"
        mock_which.assert_call(args=("tmux",), kwargs={})

    def test_detect_terminal_type_fallback(self, spawner, monkeypatch):
        """Test fallback when terminal cannot be detected."""
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        monkeypatch.delenv("TERM", raising=False)

        terminal_type = spawner.detect_terminal()

        assert terminal_type == "terminal"  # Default fallback

    def test_build_env_vars(self, spawner, mock_env_vars):
        """Test building environment variables for spawned session."""
        env_vars = spawner.build_env_vars(
            swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
            packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
            coordination_backend=mock_env_vars["SPELLBOOK_COORDINATION_BACKEND"],
            config_path=Path(mock_env_vars["SPELLBOOK_CONFIG_PATH"]),
        )

        assert env_vars["SPELLBOOK_SWARM_ID"] == mock_env_vars["SPELLBOOK_SWARM_ID"]
        assert env_vars["SPELLBOOK_PACKET_ID"] == mock_env_vars["SPELLBOOK_PACKET_ID"]
        assert (
            env_vars["SPELLBOOK_COORDINATION_BACKEND"]
            == mock_env_vars["SPELLBOOK_COORDINATION_BACKEND"]
        )
        # config_path is converted via str(Path(...)) which may normalize separators
        assert (
            env_vars["SPELLBOOK_CONFIG_PATH"]
            == str(Path(mock_env_vars["SPELLBOOK_CONFIG_PATH"]))
        )

    def test_build_env_vars_inherits_current_env(self, spawner, monkeypatch):
        """Test that build_env_vars inherits current environment."""
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("HOME", "/home/test")
        monkeypatch.setenv("CUSTOM_VAR", "inherited-value")

        env_vars = spawner.build_env_vars(
            swarm_id="test-swarm", packet_id="test-packet"
        )

        assert env_vars["PATH"] == "/usr/bin:/bin"
        assert env_vars["HOME"] == "/home/test"
        assert env_vars["CUSTOM_VAR"] == "inherited-value"
        assert env_vars["SPELLBOOK_SWARM_ID"] == "test-swarm"
        assert env_vars["SPELLBOOK_PACKET_ID"] == "test-packet"

    def test_spawn_iterm2_session(self, spawner, mock_env_vars):
        """Test spawning iTerm2 session."""
        captured_args = []

        def capture_run(*args, **kwargs):
            captured_args.append(args)
            return subprocess.CompletedProcess(args=[], returncode=0)

        mock_run = bigfoot.mock("subprocess:run")
        mock_run.calls(capture_run)

        with bigfoot:
            result = spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        assert result is True
        mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))

        # Verify AppleScript was generated correctly
        cmd_args = captured_args[0][0]
        assert "osascript" in cmd_args
        assert "tell application" in " ".join(cmd_args)
        assert "iTerm" in " ".join(cmd_args)

    def test_spawn_iterm2_session_failure(self, spawner, mock_env_vars):
        """Test iTerm2 spawning handles failures."""
        mock_run = bigfoot.mock("subprocess:run")
        mock_run.raises(subprocess.CalledProcessError(1, "osascript"))

        with bigfoot:
            result = spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        assert result is False
        mock_run.assert_call(
            args=(IsInstance(list),),
            kwargs=IsInstance(dict),
            raised=IsInstance(subprocess.CalledProcessError),
        )

    def test_spawn_terminal_session(self, spawner, mock_env_vars):
        """Test spawning Terminal.app session."""
        captured_args = []

        def capture_run(*args, **kwargs):
            captured_args.append(args)
            return subprocess.CompletedProcess(args=[], returncode=0)

        mock_run = bigfoot.mock("subprocess:run")
        mock_run.calls(capture_run)

        with bigfoot:
            result = spawner.spawn_terminal(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        assert result is True
        mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))

        # Verify AppleScript was generated correctly
        cmd_args = captured_args[0][0]
        assert "osascript" in cmd_args
        assert "tell application" in " ".join(cmd_args)
        assert "Terminal" in " ".join(cmd_args)

    def test_spawn_terminal_session_failure(self, spawner, mock_env_vars):
        """Test Terminal.app spawning handles failures."""
        mock_run = bigfoot.mock("subprocess:run")
        mock_run.raises(subprocess.CalledProcessError(1, "osascript"))

        with bigfoot:
            result = spawner.spawn_terminal(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        assert result is False
        mock_run.assert_call(
            args=(IsInstance(list),),
            kwargs=IsInstance(dict),
            raised=IsInstance(subprocess.CalledProcessError),
        )

    def test_spawn_tmux_session(self, spawner, mock_env_vars):
        """Test spawning tmux session."""
        mock_run = bigfoot.mock("subprocess:run")
        mock_run.returns(subprocess.CompletedProcess(args=[], returncode=0))
        mock_run.returns(subprocess.CompletedProcess(args=[], returncode=0))

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/local/bin/tmux")

        with bigfoot:
            result = spawner.spawn_tmux(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
                session_name="test-session",
            )

        assert result is True
        # Should be called twice: new-session and send-keys
        with bigfoot.in_any_order():
            mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))
            mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))
            mock_which.assert_call(args=(IsInstance(str),), kwargs={})

    def test_spawn_tmux_session_not_installed(self, spawner, mock_env_vars):
        """Test tmux spawning fails gracefully when tmux not installed."""
        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns(None)

        with bigfoot:
            result = spawner.spawn_tmux(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        assert result is False
        mock_which.assert_call(args=(IsInstance(str),), kwargs={})

    def test_spawn_tmux_session_failure(self, spawner, mock_env_vars):
        """Test tmux spawning handles failures."""
        mock_run = bigfoot.mock("subprocess:run")
        mock_run.raises(subprocess.CalledProcessError(1, "tmux"))

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/local/bin/tmux")

        with bigfoot:
            result = spawner.spawn_tmux(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        assert result is False
        with bigfoot.in_any_order():
            mock_run.assert_call(
                args=(IsInstance(list),),
                kwargs=IsInstance(dict),
                raised=IsInstance(subprocess.CalledProcessError),
            )
            mock_which.assert_call(args=(IsInstance(str),), kwargs={})

    def test_spawn_auto_detects_terminal(self, spawner, mock_env_vars, monkeypatch):
        """Test spawn method auto-detects terminal type."""
        monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")

        mock_iterm = bigfoot.mock.object(spawner, "spawn_iterm2")
        mock_iterm.returns(True)

        with bigfoot:
            result = spawner.spawn(
                command="echo 'test'",
                working_dir="/test/dir",
                swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
                packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
            )

        assert result is True
        mock_iterm.assert_call(args=(), kwargs=IsInstance(dict))

    def test_spawn_uses_explicit_terminal_type(self, spawner, mock_env_vars):
        """Test spawn method respects explicit terminal_type parameter."""
        mock_tmux = bigfoot.mock.object(spawner, "spawn_tmux")
        mock_tmux.returns(True)

        with bigfoot:
            result = spawner.spawn(
                command="echo 'test'",
                working_dir="/test/dir",
                swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
                packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
                terminal_type="tmux",
            )

        assert result is True
        mock_tmux.assert_call(args=(), kwargs=IsInstance(dict))

    def test_spawn_builds_env_vars(self, spawner, mock_env_vars, monkeypatch):
        """Test spawn method builds environment variables correctly."""
        monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")

        captured_kwargs = []

        def capture_spawn_iterm2(**kwargs):
            captured_kwargs.append(kwargs)
            return True

        mock_iterm = bigfoot.mock.object(spawner, "spawn_iterm2")
        mock_iterm.calls(capture_spawn_iterm2)

        with bigfoot:
            spawner.spawn(
                command="echo 'test'",
                working_dir="/test/dir",
                swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
                packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
                coordination_backend=mock_env_vars[
                    "SPELLBOOK_COORDINATION_BACKEND"
                ],
                config_path=Path(mock_env_vars["SPELLBOOK_CONFIG_PATH"]),
            )

        mock_iterm.assert_call(args=(), kwargs=IsInstance(dict))
        env_vars = captured_kwargs[0]["env_vars"]

        assert (
            env_vars["SPELLBOOK_SWARM_ID"]
            == mock_env_vars["SPELLBOOK_SWARM_ID"]
        )
        assert (
            env_vars["SPELLBOOK_PACKET_ID"]
            == mock_env_vars["SPELLBOOK_PACKET_ID"]
        )
        assert (
            env_vars["SPELLBOOK_COORDINATION_BACKEND"]
            == mock_env_vars["SPELLBOOK_COORDINATION_BACKEND"]
        )

    def test_spawn_invalid_terminal_type(self, spawner, mock_env_vars):
        """Test spawn method handles invalid terminal type."""
        with pytest.raises(ValueError, match="Unsupported terminal type"):
            spawner.spawn(
                command="echo 'test'",
                working_dir="/test/dir",
                swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
                packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
                terminal_type="invalid",
            )

    def test_applescript_escaping(self, spawner):
        """Test that AppleScript strings are properly escaped."""
        # Test with special characters that need escaping
        test_cases = [
            ('test "quoted" string', 'test \\"quoted\\" string'),
            ("test \\backslash", "test \\\\backslash"),
            ("test\nnewline", "test\\nnewline"),
        ]

        for input_str, expected in test_cases:
            escaped = spawner._escape_applescript(input_str)
            assert escaped == expected

    def test_env_var_serialization_for_applescript(self, spawner, mock_env_vars):
        """Test that environment variables are properly formatted for AppleScript."""
        captured_args = []

        def capture_run(*args, **kwargs):
            captured_args.append(args)
            return subprocess.CompletedProcess(args=[], returncode=0)

        mock_run = bigfoot.mock("subprocess:run")
        mock_run.calls(capture_run)

        with bigfoot:
            spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

        mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))
        applescript = " ".join(captured_args[0][0])

        # Verify each environment variable is in the AppleScript
        for key, value in mock_env_vars.items():
            assert f"export {key}=" in applescript

    def test_working_dir_validation(self, spawner, mock_env_vars):
        """Test that working directory is validated."""
        mock_run = bigfoot.mock("subprocess:run")
        mock_run.returns(subprocess.CompletedProcess(args=[], returncode=0))
        mock_run.returns(subprocess.CompletedProcess(args=[], returncode=0))

        with bigfoot:
            # Should not raise for strings
            result = spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/valid/path",
                env_vars=mock_env_vars,
            )
            # Will fail because path doesn't exist, but shouldn't raise ValueError

            # Path objects should also work
            result = spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir=Path("/valid/path"),
                env_vars=mock_env_vars,
            )
            # Will fail because path doesn't exist, but shouldn't raise ValueError

        mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))
        mock_run.assert_call(args=(IsInstance(list),), kwargs=IsInstance(dict))
