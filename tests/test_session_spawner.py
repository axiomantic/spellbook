"""Tests for session spawning functionality."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from spellbook_mcp.session.spawner import SessionSpawner


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

    def test_detect_terminal_type_iterm2(self, spawner):
        """Test detecting iTerm2 terminal."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}):
            terminal_type = spawner.detect_terminal()
            assert terminal_type == "iterm2"

    def test_detect_terminal_type_terminal(self, spawner):
        """Test detecting Terminal.app."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "Apple_Terminal"}):
            terminal_type = spawner.detect_terminal()
            assert terminal_type == "terminal"

    def test_detect_terminal_type_tmux(self, spawner):
        """Test detecting tmux."""
        with patch.dict(os.environ, {"TERM": "screen"}, clear=True):
            with patch("shutil.which", return_value="/usr/local/bin/tmux"):
                terminal_type = spawner.detect_terminal()
                assert terminal_type == "tmux"

    def test_detect_terminal_type_fallback(self, spawner):
        """Test fallback when terminal cannot be detected."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value=None):
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

    def test_build_env_vars_inherits_current_env(self, spawner):
        """Test that build_env_vars inherits current environment."""
        with patch.dict(
            os.environ,
            {
                "PATH": "/usr/bin:/bin",
                "HOME": "/home/test",
                "CUSTOM_VAR": "inherited-value",
            },
        ):
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
        mock_run = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=0))

        with patch("subprocess.run", mock_run):
            result = spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

            assert result is True
            mock_run.assert_called_once()

            # Verify AppleScript was generated correctly
            call_args = mock_run.call_args
            assert "osascript" in call_args[0][0]
            assert "tell application" in " ".join(call_args[0][0])
            assert "iTerm" in " ".join(call_args[0][0])

    def test_spawn_iterm2_session_failure(self, spawner, mock_env_vars):
        """Test iTerm2 spawning handles failures."""
        mock_run = Mock(side_effect=subprocess.CalledProcessError(1, "osascript"))

        with patch("subprocess.run", mock_run):
            result = spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

            assert result is False

    def test_spawn_terminal_session(self, spawner, mock_env_vars):
        """Test spawning Terminal.app session."""
        mock_run = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=0))

        with patch("subprocess.run", mock_run):
            result = spawner.spawn_terminal(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

            assert result is True
            mock_run.assert_called_once()

            # Verify AppleScript was generated correctly
            call_args = mock_run.call_args
            assert "osascript" in call_args[0][0]
            assert "tell application" in " ".join(call_args[0][0])
            assert "Terminal" in " ".join(call_args[0][0])

    def test_spawn_terminal_session_failure(self, spawner, mock_env_vars):
        """Test Terminal.app spawning handles failures."""
        mock_run = Mock(side_effect=subprocess.CalledProcessError(1, "osascript"))

        with patch("subprocess.run", mock_run):
            result = spawner.spawn_terminal(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

            assert result is False

    def test_spawn_tmux_session(self, spawner, mock_env_vars):
        """Test spawning tmux session."""
        mock_run = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=0))

        with patch("subprocess.run", mock_run):
            with patch("shutil.which", return_value="/usr/local/bin/tmux"):
                result = spawner.spawn_tmux(
                    command="echo 'test'",
                    working_dir="/test/dir",
                    env_vars=mock_env_vars,
                    session_name="test-session",
                )

                assert result is True
                # Should be called twice: new-session and send-keys
                assert mock_run.call_count == 2

    def test_spawn_tmux_session_not_installed(self, spawner, mock_env_vars):
        """Test tmux spawning fails gracefully when tmux not installed."""
        with patch("shutil.which", return_value=None):
            result = spawner.spawn_tmux(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

            assert result is False

    def test_spawn_tmux_session_failure(self, spawner, mock_env_vars):
        """Test tmux spawning handles failures."""
        mock_run = Mock(side_effect=subprocess.CalledProcessError(1, "tmux"))

        with patch("subprocess.run", mock_run):
            with patch("shutil.which", return_value="/usr/local/bin/tmux"):
                result = spawner.spawn_tmux(
                    command="echo 'test'",
                    working_dir="/test/dir",
                    env_vars=mock_env_vars,
                )

                assert result is False

    def test_spawn_auto_detects_terminal(self, spawner, mock_env_vars):
        """Test spawn method auto-detects terminal type."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}):
            with patch.object(spawner, "spawn_iterm2", return_value=True) as mock_iterm:
                result = spawner.spawn(
                    command="echo 'test'",
                    working_dir="/test/dir",
                    swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
                    packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
                )

                assert result is True
                mock_iterm.assert_called_once()

    def test_spawn_uses_explicit_terminal_type(self, spawner, mock_env_vars):
        """Test spawn method respects explicit terminal_type parameter."""
        with patch.object(spawner, "spawn_tmux", return_value=True) as mock_tmux:
            result = spawner.spawn(
                command="echo 'test'",
                working_dir="/test/dir",
                swarm_id=mock_env_vars["SPELLBOOK_SWARM_ID"],
                packet_id=mock_env_vars["SPELLBOOK_PACKET_ID"],
                terminal_type="tmux",
            )

            assert result is True
            mock_tmux.assert_called_once()

    def test_spawn_builds_env_vars(self, spawner, mock_env_vars):
        """Test spawn method builds environment variables correctly."""
        with patch.object(spawner, "spawn_iterm2", return_value=True) as mock_iterm:
            with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}):
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

                call_args = mock_iterm.call_args
                env_vars = call_args[1]["env_vars"]

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
        mock_run = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=0))

        with patch("subprocess.run", mock_run):
            spawner.spawn_iterm2(
                command="echo 'test'",
                working_dir="/test/dir",
                env_vars=mock_env_vars,
            )

            call_args = mock_run.call_args
            applescript = " ".join(call_args[0][0])

            # Verify each environment variable is in the AppleScript
            for key, value in mock_env_vars.items():
                assert f"export {key}=" in applescript

    def test_working_dir_validation(self, spawner, mock_env_vars):
        """Test that working directory is validated."""
        mock_run = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=0))

        with patch("subprocess.run", mock_run):
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
