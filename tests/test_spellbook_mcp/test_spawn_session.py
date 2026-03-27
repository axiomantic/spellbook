"""Tests for spawn_claude_session MCP tool and terminal detection utilities."""

import os
import subprocess
import sys

import bigfoot
import pytest

from spellbook.daemon.terminal import (
    detect_terminal,
    detect_macos_terminal,
    detect_linux_terminal,
    detect_windows_terminal,
    spawn_terminal_window,
    spawn_macos_terminal,
    spawn_linux_terminal,
)


class TestDetectMacOSTerminal:
    """Test macOS terminal detection."""

    def test_detect_running_iterm(self, monkeypatch):
        """Test detection of running iTerm2 process."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_result = type("Result", (), {"returncode": 0, "stdout": "12345\n"})()
        mock_run.returns(mock_result)

        mock_exists = bigfoot.mock("spellbook.daemon.terminal:os.path.exists")
        mock_exists.__call__.required(False)

        with bigfoot:
            result = detect_macos_terminal()

        assert result == "iTerm2"
        mock_run.assert_call(
            args=(["pgrep", "-x", "iTerm2"],),
            kwargs={"capture_output": True, "text": True, "timeout": 5},
        )

    def test_detect_installed_warp(self, monkeypatch):
        """Test detection of installed Warp app."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_result_fail = type("Result", (), {"returncode": 1})()
        # 3 pgrep calls: iTerm2, Warp, Terminal -- all fail
        mock_run.returns(mock_result_fail).returns(mock_result_fail).returns(mock_result_fail)

        mock_exists = bigfoot.mock("spellbook.daemon.terminal:os.path.exists")
        # /Applications/iTerm.app -> False, /Applications/Warp.app -> True
        mock_exists.returns(False).returns(True)

        with bigfoot:
            result = detect_macos_terminal()

        assert result == "Warp"
        with bigfoot.in_any_order():
            mock_run.assert_call(
                args=(["pgrep", "-x", "iTerm2"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["pgrep", "-x", "Warp"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["pgrep", "-x", "Terminal"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5},
            )
        # First exists check: /Applications/iTerm.app (False), second: /Applications/Warp.app (True)
        mock_exists.assert_call(args=("/Applications/iTerm.app",))
        mock_exists.assert_call(args=("/Applications/Warp.app",))

    def test_detect_fallback_terminal(self, monkeypatch):
        """Test fallback to Terminal.app."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_result_fail = type("Result", (), {"returncode": 1})()
        mock_run.returns(mock_result_fail).returns(mock_result_fail).returns(mock_result_fail)

        mock_exists = bigfoot.mock("spellbook.daemon.terminal:os.path.exists")
        mock_exists.returns(False).returns(False).returns(False)

        with bigfoot:
            result = detect_macos_terminal()

        assert result == "terminal"
        with bigfoot.in_any_order():
            mock_run.assert_call(
                args=(["pgrep", "-x", "iTerm2"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["pgrep", "-x", "Warp"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["pgrep", "-x", "Terminal"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5},
            )
        mock_exists.assert_call(args=("/Applications/iTerm.app",))
        mock_exists.assert_call(args=("/Applications/Warp.app",))
        mock_exists.assert_call(args=("/System/Applications/Utilities/Terminal.app",))


class TestDetectLinuxTerminal:
    """Test Linux terminal detection."""

    def test_detect_from_env_var(self, monkeypatch):
        """Test detection from TERMINAL environment variable (validated via which)."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr(os, "environ", {"TERMINAL": "gnome-terminal"})

        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/bin/gnome-terminal")

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "gnome-terminal"
        mock_which.assert_call(args=("gnome-terminal",))

    def test_detect_installed_konsole(self, monkeypatch):
        """Test detection of installed konsole."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr(os, "environ", {})

        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_fail = type("Result", (), {"returncode": 1})()
        mock_ok = type("Result", (), {"returncode": 0})()
        # gnome-terminal fails, konsole succeeds
        mock_run.returns(mock_fail).returns(mock_ok)

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

    def test_detect_fallback_xterm(self, monkeypatch):
        """Test fallback to xterm."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr(os, "environ", {})

        mock_run = bigfoot.mock("spellbook.daemon.terminal:subprocess.run")
        mock_result_fail = type("Result", (), {"returncode": 1})()
        # 5 common terminals all fail
        (mock_run
         .returns(mock_result_fail)
         .returns(mock_result_fail)
         .returns(mock_result_fail)
         .returns(mock_result_fail)
         .returns(mock_result_fail))

        with bigfoot:
            result = detect_linux_terminal()

        assert result == "xterm"
        with bigfoot.in_any_order():
            mock_run.assert_call(
                args=(["which", "gnome-terminal"],),
                kwargs={"capture_output": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["which", "konsole"],),
                kwargs={"capture_output": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["which", "xterm"],),
                kwargs={"capture_output": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["which", "terminator"],),
                kwargs={"capture_output": True, "timeout": 5},
            )
            mock_run.assert_call(
                args=(["which", "alacritty"],),
                kwargs={"capture_output": True, "timeout": 5},
            )


class TestDetectWindowsTerminal:
    """Test Windows terminal detection."""

    def test_windows_terminal_detected(self):
        """Test that Windows Terminal is detected when wt is available."""
        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns("/usr/bin/wt")

        with bigfoot:
            result = detect_windows_terminal()

        assert result == "windows-terminal"
        mock_which.assert_call(args=("wt",))

    def test_pwsh_fallback(self):
        """Test that PowerShell Core is detected as fallback."""
        mock_which = bigfoot.mock("shutil:which")
        # wt not found, pwsh found
        mock_which.returns(None).returns("/usr/bin/pwsh")

        with bigfoot:
            result = detect_windows_terminal()

        assert result == "pwsh"
        mock_which.assert_call(args=("wt",))
        mock_which.assert_call(args=("pwsh",))

    def test_cmd_fallback(self):
        """Test that cmd is the final fallback."""
        mock_which = bigfoot.mock("shutil:which")
        mock_which.returns(None).returns(None)

        with bigfoot:
            result = detect_windows_terminal()

        assert result == "cmd"
        mock_which.assert_call(args=("wt",))
        mock_which.assert_call(args=("pwsh",))


class TestDetectTerminal:
    """Test main detect_terminal function."""

    def test_delegates_to_macos(self, monkeypatch):
        """Test delegation to macOS detection."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_macos = bigfoot.mock("spellbook.daemon.terminal:detect_macos_terminal")
        mock_macos.returns("iTerm2")

        with bigfoot:
            result = detect_terminal()

        assert result == "iTerm2"
        mock_macos.assert_call(args=(), kwargs={})

    def test_delegates_to_linux(self, monkeypatch):
        """Test delegation to Linux detection."""
        monkeypatch.setattr("sys.platform", "linux")

        mock_linux = bigfoot.mock("spellbook.daemon.terminal:detect_linux_terminal")
        mock_linux.returns("gnome-terminal")

        with bigfoot:
            result = detect_terminal()

        assert result == "gnome-terminal"
        mock_linux.assert_call(args=(), kwargs={})

    def test_delegates_to_windows(self, monkeypatch):
        """Test delegation to Windows detection."""
        monkeypatch.setattr("sys.platform", "win32")

        mock_windows = bigfoot.mock("spellbook.daemon.terminal:detect_windows_terminal")
        mock_windows.returns("windows-terminal")

        with bigfoot:
            result = detect_terminal()

        assert result == "windows-terminal"
        mock_windows.assert_call(args=(), kwargs={})


class TestSpawnMacOSTerminal:
    """Test macOS terminal spawning."""

    def test_spawn_iterm2(self, monkeypatch):
        """Test spawning iTerm2 with AppleScript."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 12345})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_macos_terminal("iTerm2", "test prompt", "/tmp")

        assert result["status"] == "spawned"
        assert result["terminal"] == "iTerm2"
        assert result["pid"] == 12345
        # Verify osascript was called with iTerm2 AppleScript
        expected_cmd = "cd /tmp && claude 'test prompt'"
        expected_script = (
            '\ntell application "iTerm2"\n'
            "    create window with default profile\n"
            "    tell current session of current window\n"
            f'        write text "{expected_cmd}"\n'
            "    end tell\n"
            "end tell\n"
        )
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_script],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_spawn_terminal_app(self, monkeypatch):
        """Test spawning Terminal.app with AppleScript."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 54321})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_macos_terminal("terminal", "another prompt", "/home")

        assert result["status"] == "spawned"
        assert result["terminal"] == "terminal"
        assert result["pid"] == 54321
        expected_cmd = "cd /home && claude 'another prompt'"
        expected_script = (
            '\ntell application "Terminal"\n'
            f'    do script "{expected_cmd}"\n'
            "    activate\n"
            "end tell\n"
        )
        mock_popen.assert_call(
            args=(["osascript", "-e", expected_script],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )


class TestSpawnLinuxTerminal:
    """Test Linux terminal spawning."""

    def test_spawn_gnome_terminal(self, monkeypatch):
        """Test spawning gnome-terminal."""
        monkeypatch.setattr("sys.platform", "linux")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 99999})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_linux_terminal("gnome-terminal", "test prompt", "/var")

        assert result["status"] == "spawned"
        assert result["terminal"] == "gnome-terminal"
        assert result["pid"] == 99999
        expected_cmd = "cd /var && claude 'test prompt'; exec bash"
        mock_popen.assert_call(
            args=(["gnome-terminal", "--", "bash", "-c", expected_cmd],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )

    def test_spawn_xterm(self, monkeypatch):
        """Test spawning xterm."""
        monkeypatch.setattr("sys.platform", "linux")

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 11111})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_linux_terminal("xterm", "xterm test", "/root")

        assert result["status"] == "spawned"
        assert result["terminal"] == "xterm"
        expected_cmd = "cd /root && claude 'xterm test'; exec bash"
        mock_popen.assert_call(
            args=(["xterm", "-e", "bash", "-c", expected_cmd],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE},
        )


class TestSpawnTerminalWindow:
    """Test main spawn_terminal_window function."""

    def test_delegates_to_macos(self, monkeypatch):
        """Test delegation to macOS spawning."""
        monkeypatch.setattr("sys.platform", "darwin")

        mock_macos_spawn = bigfoot.mock("spellbook.daemon.terminal:spawn_macos_terminal")
        mock_macos_spawn.returns({
            "status": "spawned",
            "terminal": "iTerm2",
            "pid": 12345,
        })

        with bigfoot:
            result = spawn_terminal_window("iTerm2", "test", "/tmp")

        assert result["status"] == "spawned"
        mock_macos_spawn.assert_call(
            args=("iTerm2", "test", "/tmp", "claude"),
            kwargs={},
        )

    def test_delegates_to_linux(self, monkeypatch):
        """Test delegation to Linux spawning."""
        monkeypatch.setattr("sys.platform", "linux")

        mock_linux_spawn = bigfoot.mock("spellbook.daemon.terminal:spawn_linux_terminal")
        mock_linux_spawn.returns({
            "status": "spawned",
            "terminal": "gnome-terminal",
            "pid": 99999,
        })

        with bigfoot:
            result = spawn_terminal_window("gnome-terminal", "test", "/var")

        assert result["status"] == "spawned"
        mock_linux_spawn.assert_call(
            args=("gnome-terminal", "test", "/var", "claude"),
            kwargs={},
        )

    def test_delegates_to_windows(self, monkeypatch):
        """Test delegation to Windows spawning."""
        monkeypatch.setattr("sys.platform", "win32")

        mock_windows_spawn = bigfoot.mock("spellbook.daemon.terminal:spawn_windows_terminal")
        mock_windows_spawn.returns({
            "status": "spawned",
            "terminal": "cmd",
            "pid": 12345,
        })

        with bigfoot:
            result = spawn_terminal_window("cmd", "test", "C:\\")

        assert result["status"] == "spawned"
        mock_windows_spawn.assert_call(
            args=("cmd", "test", "C:\\", "claude"),
            kwargs={},
        )


class TestSpawnWindowsTerminal:
    """Test Windows terminal spawning."""

    def test_spawn_windows_terminal_wt(self):
        """Test spawning Windows Terminal (wt)."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 44444})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_windows_terminal("windows-terminal", "test prompt", "C:\\Users\\test")

        assert result["status"] == "spawned"
        assert result["terminal"] == "windows-terminal"
        assert result["pid"] == 44444
        safe_cli_prompt = subprocess.list2cmdline(["claude", "test prompt"])
        mock_popen.assert_call(
            args=(["wt", "-d", "C:\\Users\\test", "cmd", "/c", safe_cli_prompt],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )

    def test_spawn_windows_terminal_pwsh(self):
        """Test spawning PowerShell Core."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 55555})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_windows_terminal("pwsh", "test prompt", "C:\\Users\\test")

        assert result["status"] == "spawned"
        assert result["terminal"] == "pwsh"
        assert result["pid"] == 55555
        mock_popen.assert_call(
            args=(["pwsh", "-NoExit", "-Command",
                   "Set-Location 'C:\\Users\\test'; & 'claude' 'test prompt'"],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )

    def test_spawn_windows_terminal_cmd(self):
        """Test spawning cmd.exe (default fallback)."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 66666})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_windows_terminal("cmd", "test prompt", "C:\\Users\\test")

        assert result["status"] == "spawned"
        assert result["terminal"] == "cmd"
        assert result["pid"] == 66666
        safe_cli_prompt = subprocess.list2cmdline(["claude", "test prompt"])
        mock_popen.assert_call(
            args=(["cmd", "/c", "start", "cmd", "/k",
                   f'cd /d "C:\\Users\\test" && {safe_cli_prompt}'],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )

    def test_spawn_windows_terminal_custom_cli_command(self):
        """Test spawning with a custom CLI command (e.g., 'codex')."""
        from spellbook.daemon.terminal import spawn_windows_terminal

        mock_popen = bigfoot.mock("spellbook.daemon.terminal:subprocess.Popen")
        mock_process = type("Process", (), {"pid": 77777})()
        mock_popen.returns(mock_process)

        with bigfoot:
            result = spawn_windows_terminal("cmd", "test prompt", "C:\\", cli_command="codex")

        assert result["status"] == "spawned"
        safe_cli_prompt = subprocess.list2cmdline(["codex", "test prompt"])
        mock_popen.assert_call(
            args=(["cmd", "/c", "start", "cmd", "/k",
                   f'cd /d "C:\\" && {safe_cli_prompt}'],),
            kwargs={"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)},
        )


class TestSpawnClaudeSessionMCPTool:
    """Test the spawn_claude_session MCP tool logic."""

    def test_spawn_with_auto_detect(self):
        """Test spawning with auto-detected terminal."""
        import spellbook.daemon.terminal as terminal_mod

        mock_detect = bigfoot.mock("spellbook.daemon.terminal:detect_terminal")
        mock_detect.returns("iTerm2")

        mock_spawn = bigfoot.mock("spellbook.daemon.terminal:spawn_terminal_window")
        mock_spawn.returns({
            "status": "spawned",
            "terminal": "iTerm2",
            "pid": 12345,
        })

        with bigfoot:
            terminal = terminal_mod.detect_terminal()
            working_directory = "/tmp"
            result = terminal_mod.spawn_terminal_window(terminal, "test prompt", working_directory)

        assert result["status"] == "spawned"
        assert result["terminal"] == "iTerm2"
        assert result["pid"] == 12345
        mock_detect.assert_call(args=(), kwargs={})
        mock_spawn.assert_call(args=("iTerm2", "test prompt", "/tmp"), kwargs={})

    def test_spawn_with_specified_terminal(self):
        """Test spawning with user-specified terminal."""
        import spellbook.daemon.terminal as terminal_mod

        mock_spawn = bigfoot.mock("spellbook.daemon.terminal:spawn_terminal_window")
        mock_spawn.returns({
            "status": "spawned",
            "terminal": "Warp",
            "pid": 54321,
        })

        with bigfoot:
            terminal = "Warp"
            working_directory = "/home/user"
            result = terminal_mod.spawn_terminal_window(terminal, "specific test", working_directory)

        assert result["status"] == "spawned"
        assert result["terminal"] == "Warp"
        assert result["pid"] == 54321
        mock_spawn.assert_call(args=("Warp", "specific test", "/home/user"), kwargs={})
