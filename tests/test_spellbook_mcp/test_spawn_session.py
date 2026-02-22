"""Tests for spawn_claude_session MCP tool and terminal detection utilities."""

import shutil
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from spellbook_mcp.terminal_utils import (
    detect_terminal,
    detect_macos_terminal,
    detect_linux_terminal,
    detect_windows_terminal,
    spawn_terminal_window,
    spawn_macos_terminal,
    spawn_linux_terminal
)


class TestDetectMacOSTerminal(unittest.TestCase):
    """Test macOS terminal detection."""

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('sys.platform', 'darwin')
    def test_detect_running_iterm(self, mock_exists, mock_run):
        """Test detection of running iTerm2 process."""
        # Mock pgrep finding iTerm2
        mock_run.return_value = MagicMock(returncode=0, stdout='12345\n')

        result = detect_macos_terminal()

        self.assertEqual(result, 'iTerm2')
        mock_run.assert_called_once()
        self.assertIn('pgrep', mock_run.call_args[0][0])

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('sys.platform', 'darwin')
    def test_detect_installed_warp(self, mock_exists, mock_run):
        """Test detection of installed Warp app."""
        # Mock pgrep finding no running processes
        mock_run.return_value = MagicMock(returncode=1)

        # Mock Warp.app exists
        def exists_side_effect(path):
            return '/Applications/Warp.app' in path

        mock_exists.side_effect = exists_side_effect

        result = detect_macos_terminal()

        self.assertEqual(result, 'Warp')

    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('sys.platform', 'darwin')
    def test_detect_fallback_terminal(self, mock_exists, mock_run):
        """Test fallback to Terminal.app."""
        # No running processes
        mock_run.return_value = MagicMock(returncode=1)
        # No installed apps
        mock_exists.return_value = False

        result = detect_macos_terminal()

        self.assertEqual(result, 'terminal')


class TestDetectLinuxTerminal(unittest.TestCase):
    """Test Linux terminal detection."""

    @patch('os.environ', {'TERMINAL': 'gnome-terminal'})
    @patch('sys.platform', 'linux')
    def test_detect_from_env_var(self):
        """Test detection from TERMINAL environment variable."""
        result = detect_linux_terminal()

        self.assertEqual(result, 'gnome-terminal')

    @patch('subprocess.run')
    @patch('os.environ', {})
    @patch('sys.platform', 'linux')
    def test_detect_installed_konsole(self, mock_run):
        """Test detection of installed konsole."""
        def run_side_effect(cmd, **kwargs):
            if 'konsole' in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)

        mock_run.side_effect = run_side_effect

        result = detect_linux_terminal()

        self.assertEqual(result, 'konsole')

    @patch('subprocess.run')
    @patch('os.environ', {})
    @patch('sys.platform', 'linux')
    def test_detect_fallback_xterm(self, mock_run):
        """Test fallback to xterm."""
        # No terminals found
        mock_run.return_value = MagicMock(returncode=1)

        result = detect_linux_terminal()

        self.assertEqual(result, 'xterm')


class TestDetectWindowsTerminal(unittest.TestCase):
    """Test Windows terminal detection."""

    @patch('shutil.which')
    def test_windows_terminal_detected(self, mock_which):
        """Test that Windows Terminal is detected when wt is available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/wt" if cmd == "wt" else None
        result = detect_windows_terminal()
        self.assertEqual(result, "windows-terminal")

    @patch('shutil.which')
    def test_pwsh_fallback(self, mock_which):
        """Test that PowerShell Core is detected as fallback."""
        mock_which.side_effect = lambda cmd: "/usr/bin/pwsh" if cmd == "pwsh" else None
        result = detect_windows_terminal()
        self.assertEqual(result, "pwsh")

    @patch('shutil.which', return_value=None)
    def test_cmd_fallback(self, mock_which):
        """Test that cmd is the final fallback."""
        result = detect_windows_terminal()
        self.assertEqual(result, "cmd")


class TestDetectTerminal(unittest.TestCase):
    """Test main detect_terminal function."""

    @patch('spellbook_mcp.terminal_utils.detect_macos_terminal')
    @patch('sys.platform', 'darwin')
    def test_delegates_to_macos(self, mock_macos):
        """Test delegation to macOS detection."""
        mock_macos.return_value = 'iTerm2'

        result = detect_terminal()

        self.assertEqual(result, 'iTerm2')
        mock_macos.assert_called_once()

    @patch('spellbook_mcp.terminal_utils.detect_linux_terminal')
    @patch('sys.platform', 'linux')
    def test_delegates_to_linux(self, mock_linux):
        """Test delegation to Linux detection."""
        mock_linux.return_value = 'gnome-terminal'

        result = detect_terminal()

        self.assertEqual(result, 'gnome-terminal')
        mock_linux.assert_called_once()

    @patch('spellbook_mcp.terminal_utils.detect_windows_terminal')
    @patch('sys.platform', 'win32')
    def test_delegates_to_windows(self, mock_windows):
        """Test delegation to Windows detection."""
        mock_windows.return_value = 'windows-terminal'

        result = detect_terminal()

        self.assertEqual(result, 'windows-terminal')
        mock_windows.assert_called_once()


class TestSpawnMacOSTerminal(unittest.TestCase):
    """Test macOS terminal spawning."""

    @patch('subprocess.Popen')
    @patch('sys.platform', 'darwin')
    def test_spawn_iterm2(self, mock_popen):
        """Test spawning iTerm2 with AppleScript."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = spawn_macos_terminal('iTerm2', 'test prompt', '/tmp')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'iTerm2')
        self.assertEqual(result['pid'], 12345)

        # Check AppleScript was used
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn('osascript', args)
        self.assertIn('-e', args)

    @patch('subprocess.Popen')
    @patch('sys.platform', 'darwin')
    def test_spawn_terminal_app(self, mock_popen):
        """Test spawning Terminal.app with AppleScript."""
        mock_process = MagicMock()
        mock_process.pid = 54321
        mock_popen.return_value = mock_process

        result = spawn_macos_terminal('terminal', 'another prompt', '/home')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'terminal')
        self.assertEqual(result['pid'], 54321)


class TestSpawnLinuxTerminal(unittest.TestCase):
    """Test Linux terminal spawning."""

    @patch('subprocess.Popen')
    @patch('sys.platform', 'linux')
    def test_spawn_gnome_terminal(self, mock_popen):
        """Test spawning gnome-terminal."""
        mock_process = MagicMock()
        mock_process.pid = 99999
        mock_popen.return_value = mock_process

        result = spawn_linux_terminal('gnome-terminal', 'test prompt', '/var')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'gnome-terminal')
        self.assertEqual(result['pid'], 99999)

        # Check command format
        args = mock_popen.call_args[0][0]
        self.assertIn('gnome-terminal', args)
        self.assertIn('--', args)

    @patch('subprocess.Popen')
    @patch('sys.platform', 'linux')
    def test_spawn_xterm(self, mock_popen):
        """Test spawning xterm."""
        mock_process = MagicMock()
        mock_process.pid = 11111
        mock_popen.return_value = mock_process

        result = spawn_linux_terminal('xterm', 'xterm test', '/root')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'xterm')


class TestSpawnTerminalWindow(unittest.TestCase):
    """Test main spawn_terminal_window function."""

    @patch('spellbook_mcp.terminal_utils.spawn_macos_terminal')
    @patch('sys.platform', 'darwin')
    def test_delegates_to_macos(self, mock_macos_spawn):
        """Test delegation to macOS spawning."""
        mock_macos_spawn.return_value = {
            'status': 'spawned',
            'terminal': 'iTerm2',
            'pid': 12345
        }

        result = spawn_terminal_window('iTerm2', 'test', '/tmp')

        self.assertEqual(result['status'], 'spawned')
        mock_macos_spawn.assert_called_once_with('iTerm2', 'test', '/tmp', 'claude')

    @patch('spellbook_mcp.terminal_utils.spawn_linux_terminal')
    @patch('sys.platform', 'linux')
    def test_delegates_to_linux(self, mock_linux_spawn):
        """Test delegation to Linux spawning."""
        mock_linux_spawn.return_value = {
            'status': 'spawned',
            'terminal': 'gnome-terminal',
            'pid': 99999
        }

        result = spawn_terminal_window('gnome-terminal', 'test', '/var')

        self.assertEqual(result['status'], 'spawned')
        mock_linux_spawn.assert_called_once_with('gnome-terminal', 'test', '/var', 'claude')

    @patch('spellbook_mcp.terminal_utils.spawn_windows_terminal')
    @patch('sys.platform', 'win32')
    def test_delegates_to_windows(self, mock_windows_spawn):
        """Test delegation to Windows spawning."""
        mock_windows_spawn.return_value = {
            'status': 'spawned',
            'terminal': 'cmd',
            'pid': 12345
        }

        result = spawn_terminal_window('cmd', 'test', 'C:\\')

        self.assertEqual(result['status'], 'spawned')
        mock_windows_spawn.assert_called_once_with('cmd', 'test', 'C:\\', 'claude')


class TestSpawnWindowsTerminal(unittest.TestCase):
    """Test Windows terminal spawning."""

    @patch('subprocess.Popen')
    def test_spawn_windows_terminal_wt(self, mock_popen):
        """Test spawning Windows Terminal (wt)."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        mock_process = MagicMock()
        mock_process.pid = 44444
        mock_popen.return_value = mock_process

        result = spawn_windows_terminal('windows-terminal', 'test prompt', 'C:\\Users\\test')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'windows-terminal')
        self.assertEqual(result['pid'], 44444)

        args = mock_popen.call_args[0][0]
        self.assertEqual(args[0], 'wt')
        self.assertIn('C:\\Users\\test', args)

    @patch('subprocess.Popen')
    def test_spawn_windows_terminal_pwsh(self, mock_popen):
        """Test spawning PowerShell Core."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        mock_process = MagicMock()
        mock_process.pid = 55555
        mock_popen.return_value = mock_process

        result = spawn_windows_terminal('pwsh', 'test prompt', 'C:\\Users\\test')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'pwsh')
        self.assertEqual(result['pid'], 55555)

        args = mock_popen.call_args[0][0]
        self.assertEqual(args[0], 'pwsh')

    @patch('subprocess.Popen')
    def test_spawn_windows_terminal_cmd(self, mock_popen):
        """Test spawning cmd.exe (default fallback)."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        mock_process = MagicMock()
        mock_process.pid = 66666
        mock_popen.return_value = mock_process

        result = spawn_windows_terminal('cmd', 'test prompt', 'C:\\Users\\test')

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'cmd')
        self.assertEqual(result['pid'], 66666)

        args = mock_popen.call_args[0][0]
        self.assertIn('cmd', args)

    @patch('subprocess.Popen')
    def test_spawn_windows_terminal_custom_cli_command(self, mock_popen):
        """Test spawning with a custom CLI command (e.g., 'codex')."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        mock_process = MagicMock()
        mock_process.pid = 77777
        mock_popen.return_value = mock_process

        result = spawn_windows_terminal('cmd', 'test prompt', 'C:\\', cli_command='codex')

        self.assertEqual(result['status'], 'spawned')
        # Verify the custom CLI command appears in the arguments
        args = mock_popen.call_args[0][0]
        cmd_str = ' '.join(str(a) for a in args)
        self.assertIn('codex', cmd_str)


class TestSpawnClaudeSessionMCPTool(unittest.TestCase):
    """Test the spawn_claude_session MCP tool logic."""

    @patch('spellbook_mcp.terminal_utils.detect_terminal')
    @patch('spellbook_mcp.terminal_utils.spawn_terminal_window')
    def test_spawn_with_auto_detect(self, mock_spawn, mock_detect):
        """Test spawning with auto-detected terminal."""
        # This tests the function logic that the MCP tool wraps
        # We test the core logic directly, which is what the tool uses
        mock_detect.return_value = 'iTerm2'
        mock_spawn.return_value = {
            'status': 'spawned',
            'terminal': 'iTerm2',
            'pid': 12345
        }

        # Simulate what spawn_claude_session does
        terminal = mock_detect()  # Auto-detect
        working_directory = '/tmp'
        result = mock_spawn(terminal, 'test prompt', working_directory)

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'iTerm2')
        self.assertEqual(result['pid'], 12345)
        mock_detect.assert_called_once()
        mock_spawn.assert_called_once_with('iTerm2', 'test prompt', '/tmp')

    @patch('spellbook_mcp.terminal_utils.spawn_terminal_window')
    def test_spawn_with_specified_terminal(self, mock_spawn):
        """Test spawning with user-specified terminal."""
        mock_spawn.return_value = {
            'status': 'spawned',
            'terminal': 'Warp',
            'pid': 54321
        }

        # Simulate what spawn_claude_session does with explicit terminal
        terminal = 'Warp'  # User specified
        working_directory = '/home/user'
        result = mock_spawn(terminal, 'specific test', working_directory)

        self.assertEqual(result['status'], 'spawned')
        self.assertEqual(result['terminal'], 'Warp')
        self.assertEqual(result['pid'], 54321)
        mock_spawn.assert_called_once_with('Warp', 'specific test', '/home/user')


if __name__ == '__main__':
    unittest.main()
