"""Session spawning for swarm coordination.

This module provides functionality to spawn new terminal sessions with
environment variables for swarm coordination. Supports iTerm2, Terminal.app,
and tmux.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Literal, Optional, Union


class SessionSpawner:
    """Spawns new terminal sessions with environment variables for swarm coordination."""

    def detect_terminal(self) -> Literal["iterm2", "terminal", "tmux"]:
        """Detect the current terminal type.

        Returns:
            Terminal type: "iterm2", "terminal", or "tmux"
        """
        term_program = os.environ.get("TERM_PROGRAM", "")

        if term_program == "iTerm.app":
            return "iterm2"
        elif term_program == "Apple_Terminal":
            return "terminal"
        elif "screen" in os.environ.get("TERM", "") and shutil.which("tmux"):
            return "tmux"

        # Default fallback to Terminal.app (most compatible)
        return "terminal"

    def build_env_vars(
        self,
        swarm_id: str,
        packet_id: str,
        coordination_backend: Optional[str] = None,
        config_path: Optional[Path] = None,
    ) -> Dict[str, str]:
        """Build environment variables for spawned session.

        Args:
            swarm_id: Swarm identifier
            packet_id: Work packet identifier
            coordination_backend: Coordination backend type (optional)
            config_path: Path to spellbook config (optional)

        Returns:
            Dictionary of environment variables
        """
        # Start with current environment to inherit PATH, HOME, etc.
        env_vars = dict(os.environ)

        # Set spellbook-specific variables
        env_vars["SPELLBOOK_SWARM_ID"] = swarm_id
        env_vars["SPELLBOOK_PACKET_ID"] = packet_id

        if coordination_backend:
            env_vars["SPELLBOOK_COORDINATION_BACKEND"] = coordination_backend

        if config_path:
            env_vars["SPELLBOOK_CONFIG_PATH"] = str(config_path)

        return env_vars

    def _escape_applescript(self, text: str) -> str:
        """Escape special characters for AppleScript strings.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for AppleScript
        """
        # Escape backslashes first, then quotes, then newlines
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        text = text.replace("\n", "\\n")
        return text

    def _serialize_env_for_applescript(self, env_vars: Dict[str, str]) -> str:
        """Serialize environment variables for AppleScript.

        Args:
            env_vars: Dictionary of environment variables

        Returns:
            AppleScript-compatible export statements
        """
        exports = []
        for key, value in env_vars.items():
            # Escape the value for shell
            escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
            exports.append(f'export {key}="{escaped_value}"')
        return "; ".join(exports)

    def spawn_iterm2(
        self,
        command: str,
        working_dir: Union[str, Path],
        env_vars: Dict[str, str],
    ) -> bool:
        """Spawn a new iTerm2 session.

        Args:
            command: Command to execute in the new session
            working_dir: Working directory for the session
            env_vars: Environment variables to set

        Returns:
            True if successful, False otherwise
        """
        try:
            working_dir_str = str(working_dir)
            env_exports = self._serialize_env_for_applescript(env_vars)

            # Build AppleScript to create new iTerm2 window
            applescript = f'''
tell application "iTerm"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow
        write text "cd {self._escape_applescript(working_dir_str)}"
        write text "{self._escape_applescript(env_exports)}"
        write text "{self._escape_applescript(command)}"
    end tell
end tell
'''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                check=True,
                capture_output=True,
                text=True,
            )
            return True

        except subprocess.CalledProcessError as e:
            print(f"Failed to spawn iTerm2 session: {e}")
            return False
        except Exception as e:
            print(f"Error spawning iTerm2 session: {e}")
            return False

    def spawn_terminal(
        self,
        command: str,
        working_dir: Union[str, Path],
        env_vars: Dict[str, str],
    ) -> bool:
        """Spawn a new Terminal.app session.

        Args:
            command: Command to execute in the new session
            working_dir: Working directory for the session
            env_vars: Environment variables to set

        Returns:
            True if successful, False otherwise
        """
        try:
            working_dir_str = str(working_dir)
            env_exports = self._serialize_env_for_applescript(env_vars)

            # Build AppleScript to create new Terminal window
            applescript = f'''
tell application "Terminal"
    activate
    do script "cd {self._escape_applescript(working_dir_str)}; {self._escape_applescript(env_exports)}; {self._escape_applescript(command)}"
end tell
'''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                check=True,
                capture_output=True,
                text=True,
            )
            return True

        except subprocess.CalledProcessError as e:
            print(f"Failed to spawn Terminal session: {e}")
            return False
        except Exception as e:
            print(f"Error spawning Terminal session: {e}")
            return False

    def spawn_tmux(
        self,
        command: str,
        working_dir: Union[str, Path],
        env_vars: Dict[str, str],
        session_name: Optional[str] = None,
    ) -> bool:
        """Spawn a new tmux session.

        Args:
            command: Command to execute in the new session
            working_dir: Working directory for the session
            env_vars: Environment variables to set
            session_name: Name for the tmux session (optional)

        Returns:
            True if successful, False otherwise
        """
        # Check if tmux is installed
        if not shutil.which("tmux"):
            print("tmux is not installed")
            return False

        try:
            working_dir_str = str(working_dir)

            # Generate session name if not provided
            if not session_name:
                session_name = f"spellbook-{env_vars.get('SPELLBOOK_PACKET_ID', 'session')}"

            # Create new tmux session
            subprocess.run(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-s",
                    session_name,
                    "-c",
                    working_dir_str,
                ],
                check=True,
                env=env_vars,
                capture_output=True,
            )

            # Send command to the session
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, command, "Enter"],
                check=True,
                env=env_vars,
                capture_output=True,
            )

            return True

        except subprocess.CalledProcessError as e:
            print(f"Failed to spawn tmux session: {e}")
            return False
        except Exception as e:
            print(f"Error spawning tmux session: {e}")
            return False

    def spawn(
        self,
        command: str,
        working_dir: Union[str, Path],
        swarm_id: str,
        packet_id: str,
        coordination_backend: Optional[str] = None,
        config_path: Optional[Path] = None,
        terminal_type: Optional[Literal["iterm2", "terminal", "tmux"]] = None,
        session_name: Optional[str] = None,
    ) -> bool:
        """Spawn a new terminal session with swarm environment variables.

        This is the main entry point for spawning sessions. It auto-detects
        the terminal type if not specified and builds the appropriate environment
        variables.

        Args:
            command: Command to execute in the new session
            working_dir: Working directory for the session
            swarm_id: Swarm identifier
            packet_id: Work packet identifier
            coordination_backend: Coordination backend type (optional)
            config_path: Path to spellbook config (optional)
            terminal_type: Explicit terminal type to use (optional, auto-detected if not provided)
            session_name: Name for tmux session (only used for tmux, optional)

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If terminal_type is invalid
        """
        # Build environment variables
        env_vars = self.build_env_vars(
            swarm_id=swarm_id,
            packet_id=packet_id,
            coordination_backend=coordination_backend,
            config_path=config_path,
        )

        # Detect or validate terminal type
        if terminal_type is None:
            terminal_type = self.detect_terminal()
        elif terminal_type not in ("iterm2", "terminal", "tmux"):
            raise ValueError(f"Unsupported terminal type: {terminal_type}")

        # Spawn based on terminal type
        if terminal_type == "iterm2":
            return self.spawn_iterm2(
                command=command, working_dir=working_dir, env_vars=env_vars
            )
        elif terminal_type == "terminal":
            return self.spawn_terminal(
                command=command, working_dir=working_dir, env_vars=env_vars
            )
        elif terminal_type == "tmux":
            return self.spawn_tmux(
                command=command,
                working_dir=working_dir,
                env_vars=env_vars,
                session_name=session_name,
            )
        else:
            # This should never happen due to validation above
            raise ValueError(f"Unsupported terminal type: {terminal_type}")
