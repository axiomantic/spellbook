"""Terminal detection and spawning utilities for spawn_session MCP tool."""

import sys
import os
import subprocess
from typing import Optional


def detect_terminal() -> str:
    """
    Detect the current terminal application.

    Returns:
        Terminal name (e.g., 'iTerm2', 'gnome-terminal', 'xterm')

    Raises:
        NotImplementedError: On Windows (not supported in MVP)
    """
    if sys.platform == 'darwin':
        return detect_macos_terminal()
    elif sys.platform.startswith('linux'):
        return detect_linux_terminal()
    elif sys.platform == 'win32':
        return detect_windows_terminal()
    else:
        raise NotImplementedError(f"Platform {sys.platform} not supported")


def detect_macos_terminal() -> str:
    """
    Detect terminal application on macOS.

    Detection order:
    1. Check running processes (iTerm2, Warp, Terminal)
    2. Check installed applications
    3. Fallback to 'terminal' (always available on macOS)

    Returns:
        Terminal name
    """
    # Check running processes
    terminals_to_check = ['iTerm2', 'Warp', 'Terminal']
    for terminal in terminals_to_check:
        try:
            result = subprocess.run(
                ['pgrep', '-x', terminal],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return terminal
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # Check installed applications
    app_paths = [
        ('/Applications/iTerm.app', 'iTerm2'),
        ('/Applications/Warp.app', 'Warp'),
        ('/System/Applications/Utilities/Terminal.app', 'terminal')
    ]

    for path, name in app_paths:
        if os.path.exists(path):
            return name

    # Fallback (macOS always has Terminal.app)
    return 'terminal'


def detect_linux_terminal() -> str:
    """
    Detect terminal application on Linux.

    Detection order:
    1. Check TERMINAL environment variable
    2. Check for common installed terminals
    3. Fallback to 'xterm'

    Returns:
        Terminal name
    """
    # Check TERMINAL environment variable
    terminal_env = os.environ.get('TERMINAL')
    if terminal_env:
        return terminal_env

    # Check for common terminals
    common_terminals = [
        'gnome-terminal',
        'konsole',
        'xterm',
        'terminator',
        'alacritty'
    ]

    for terminal in common_terminals:
        try:
            result = subprocess.run(
                ['which', terminal],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return terminal
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # Fallback
    return 'xterm'


def detect_windows_terminal() -> str:
    """
    Detect terminal application on Windows.

    Raises:
        NotImplementedError: Windows not supported in MVP
    """
    raise NotImplementedError("Windows terminal detection not implemented in MVP")


def spawn_terminal_window(
    terminal: str,
    prompt: str,
    working_directory: Optional[str] = None,
    cli_command: Optional[str] = None
) -> dict:
    """
    Spawn a new terminal window with an AI assistant session.

    Args:
        terminal: Terminal application name
        prompt: Initial prompt to send to the AI assistant
        working_directory: Directory to start in (defaults to cwd)
        cli_command: CLI command to invoke (defaults to 'claude', supports 'codex', 'gemini', etc.)

    Returns:
        {"status": "spawned", "terminal": str, "pid": int | None}

    Raises:
        NotImplementedError: On Windows (not supported in MVP)
    """
    if working_directory is None:
        working_directory = os.getcwd()

    if cli_command is None:
        cli_command = os.environ.get('SPELLBOOK_CLI_COMMAND', 'claude')

    if sys.platform == 'darwin':
        return spawn_macos_terminal(terminal, prompt, working_directory, cli_command)
    elif sys.platform.startswith('linux'):
        return spawn_linux_terminal(terminal, prompt, working_directory, cli_command)
    elif sys.platform == 'win32':
        raise NotImplementedError("Windows terminal spawning not implemented in MVP")
    else:
        raise NotImplementedError(f"Platform {sys.platform} not supported")


def spawn_macos_terminal(
    terminal: str,
    prompt: str,
    working_directory: str,
    cli_command: str = 'claude'
) -> dict:
    """
    Spawn a macOS terminal window using AppleScript.

    Args:
        terminal: Terminal application name ('iTerm2', 'Warp', 'terminal')
        prompt: Initial prompt to send to the AI assistant
        working_directory: Directory to start in
        cli_command: CLI command to invoke (e.g., 'claude', 'codex', 'gemini')

    Returns:
        {"status": "spawned", "terminal": str, "pid": int | None}
    """
    # Escape quotes in prompt and directory
    escaped_prompt = prompt.replace('"', '\\"')
    escaped_wd = working_directory.replace('"', '\\"')

    # Build command to execute
    command = f'cd "{escaped_wd}" && {cli_command} "{escaped_prompt}"'

    if terminal.lower() == 'iterm2':
        applescript = f'''
tell application "iTerm2"
    create window with default profile
    tell current session of current window
        write text "{command}"
    end tell
end tell
'''
    elif terminal.lower() == 'warp':
        applescript = f'''
tell application "Warp"
    activate
    tell application "System Events"
        keystroke "t" using {{command down}}
        delay 0.5
        keystroke "{command}"
        keystroke return
    end tell
end tell
'''
    else:  # terminal (Terminal.app)
        applescript = f'''
tell application "Terminal"
    do script "{command}"
    activate
end tell
'''

    # Execute AppleScript
    process = subprocess.Popen(
        ['osascript', '-e', applescript],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return {
        'status': 'spawned',
        'terminal': terminal,
        'pid': process.pid
    }


def spawn_linux_terminal(
    terminal: str,
    prompt: str,
    working_directory: str,
    cli_command: str = 'claude'
) -> dict:
    """
    Spawn a Linux terminal window.

    Args:
        terminal: Terminal application name
        prompt: Initial prompt to send to the AI assistant
        working_directory: Directory to start in
        cli_command: CLI command to invoke (e.g., 'claude', 'codex', 'gemini')

    Returns:
        {"status": "spawned", "terminal": str, "pid": int | None}
    """
    # Escape quotes
    escaped_prompt = prompt.replace('"', '\\"')
    escaped_wd = working_directory.replace('"', '\\"')

    # Build command
    command = f'cd "{escaped_wd}" && {cli_command} "{escaped_prompt}"; exec bash'

    # Build terminal-specific command
    if terminal == 'gnome-terminal':
        cmd = ['gnome-terminal', '--', 'bash', '-c', command]
    elif terminal == 'konsole':
        cmd = ['konsole', '-e', 'bash', '-c', command]
    elif terminal == 'xterm':
        cmd = ['xterm', '-e', 'bash', '-c', command]
    elif terminal == 'terminator':
        cmd = ['terminator', '-e', f'bash -c "{command}"']
    elif terminal == 'alacritty':
        cmd = ['alacritty', '-e', 'bash', '-c', command]
    else:
        # Generic fallback
        cmd = [terminal, '-e', 'bash', '-c', command]

    # Spawn process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return {
        'status': 'spawned',
        'terminal': terminal,
        'pid': process.pid
    }
