"""
Compaction detection and context recovery for Claude Code sessions.

Monitors session files for compaction events and provides context
that can be injected into subsequent tool responses.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CompactionEvent:
    """Represents a detected compaction event."""
    session_id: str
    summary: str
    leaf_uuid: str
    detected_at: float
    project_path: str
    injected: bool = False


# State file location
def _get_state_file() -> Path:
    """Get path to compaction state file."""
    state_dir = Path.home() / '.local' / 'spellbook' / 'state'
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / 'compaction_state.json'


def _encode_path(path: str) -> str:
    """Encode path for Claude Code session directory naming."""
    return '-' + path.replace('/', '-')


def _get_claude_session_dir(project_path: str) -> Path:
    """Get Claude Code session directory for a project."""
    encoded = _encode_path(project_path)
    return Path.home() / '.claude' / 'projects' / encoded


def _get_current_session_file(project_path: str) -> Optional[Path]:
    """Find the most recently modified session file for a project."""
    session_dir = _get_claude_session_dir(project_path)

    if not session_dir.exists():
        return None

    session_files = list(session_dir.glob('*.jsonl'))
    if not session_files:
        return None

    # Return most recently modified
    return max(session_files, key=lambda p: p.stat().st_mtime)


def load_state() -> Dict[str, Any]:
    """Load compaction state from file."""
    state_file = _get_state_file()

    if not state_file.exists():
        return {
            'pending_events': [],
            'last_check': {},  # project_path -> {session_id, line_count}
        }

    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {
            'pending_events': [],
            'last_check': {},
        }


def save_state(state: Dict[str, Any]) -> None:
    """Save compaction state to file."""
    state_file = _get_state_file()

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def check_for_compaction(project_path: str = None) -> Optional[CompactionEvent]:
    """
    Check for new compaction events in the current project's session.

    Args:
        project_path: Project path to check (defaults to cwd)

    Returns:
        CompactionEvent if new compaction detected, None otherwise
    """
    if project_path is None:
        project_path = os.getcwd()

    session_file = _get_current_session_file(project_path)
    if not session_file:
        return None

    state = load_state()
    session_id = session_file.stem

    # Get last check info for this project
    last_check = state['last_check'].get(project_path, {})
    last_session_id = last_check.get('session_id')
    last_line_count = last_check.get('line_count', 0)

    # Read session file
    try:
        with open(session_file, 'r') as f:
            lines = f.readlines()
    except OSError:
        return None

    current_line_count = len(lines)

    # If different session or fewer lines (session reset), start fresh
    if session_id != last_session_id:
        last_line_count = 0

    # Check new lines for compaction events
    compaction_event = None
    for line in lines[last_line_count:]:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
            if msg.get('type') == 'summary':
                compaction_event = CompactionEvent(
                    session_id=session_id,
                    summary=msg.get('summary', ''),
                    leaf_uuid=msg.get('leafUuid', ''),
                    detected_at=time.time(),
                    project_path=project_path,
                    injected=False,
                )
        except json.JSONDecodeError:
            continue

    # Update state
    state['last_check'][project_path] = {
        'session_id': session_id,
        'line_count': current_line_count,
    }

    if compaction_event:
        # Add to pending events
        state['pending_events'].append(asdict(compaction_event))

    save_state(state)

    return compaction_event


def get_pending_context(project_path: str = None) -> Optional[Dict[str, Any]]:
    """
    Get pending context to inject after compaction.

    Checks for any pending compaction events for the project and returns
    context that should be injected into the next tool response.

    Args:
        project_path: Project path (defaults to cwd)

    Returns:
        Context dict if pending injection needed, None otherwise
    """
    if project_path is None:
        project_path = os.getcwd()

    state = load_state()

    # Find pending events for this project
    pending = [
        e for e in state['pending_events']
        if e['project_path'] == project_path and not e['injected']
    ]

    if not pending:
        return None

    # Get the most recent pending event
    latest = max(pending, key=lambda e: e['detected_at'])

    return {
        'type': 'compaction_recovery',
        'session_id': latest['session_id'],
        'summary': latest['summary'],
        'detected_at': latest['detected_at'],
        'age_seconds': time.time() - latest['detected_at'],
    }


def mark_context_injected(project_path: str = None) -> None:
    """
    Mark pending context as injected for a project.

    Should be called after successfully injecting context into a tool response.

    Args:
        project_path: Project path (defaults to cwd)
    """
    if project_path is None:
        project_path = os.getcwd()

    state = load_state()

    # Mark all pending events for this project as injected
    for event in state['pending_events']:
        if event['project_path'] == project_path:
            event['injected'] = True

    # Clean up old injected events (older than 1 hour)
    cutoff = time.time() - 3600
    state['pending_events'] = [
        e for e in state['pending_events']
        if e['detected_at'] > cutoff
    ]

    save_state(state)


def get_recovery_reminder(mode_info: Dict[str, Any] = None) -> str:
    """
    Generate a system reminder for context recovery after compaction.

    Args:
        mode_info: Optional mode information (fun mode, tarot mode, etc.)

    Returns:
        Formatted system reminder string
    """
    lines = [
        "<system-reminder>",
        "SESSION CONTEXT RECOVERY: A compaction just occurred. Important context:",
    ]

    if mode_info:
        mode_type = mode_info.get('type', 'none')
        if mode_type == 'fun':
            persona = mode_info.get('persona', {})
            lines.append(f"- SESSION MODE: Fun mode active")
            if persona.get('name'):
                lines.append(f"- PERSONA: {persona['name']}")
            if persona.get('context'):
                lines.append(f"- CONTEXT: {persona['context']}")
            if persona.get('undertow'):
                lines.append(f"- UNDERTOW: {persona['undertow']}")
        elif mode_type == 'tarot':
            lines.append("- SESSION MODE: Tarot mode active (roundtable dialogue)")
        else:
            lines.append("- SESSION MODE: Standard mode")

    lines.extend([
        "",
        "Please re-read CLAUDE.md if you need to refresh project-specific instructions.",
        "</system-reminder>",
    ])

    return '\n'.join(lines)


# Background watcher (optional, for continuous monitoring)
class CompactionWatcher:
    """
    Background watcher for compaction events.

    Can be run in a separate thread to continuously monitor for compaction.
    """

    def __init__(self, project_path: str = None, poll_interval: float = 2.0):
        self.project_path = project_path or os.getcwd()
        self.poll_interval = poll_interval
        self._running = False

    def start(self):
        """Start watching in a background thread."""
        import threading
        self._running = True
        thread = threading.Thread(target=self._watch_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """Stop the watcher."""
        self._running = False

    def _watch_loop(self):
        """Main watch loop."""
        while self._running:
            try:
                event = check_for_compaction(self.project_path)
                if event:
                    # Could trigger callback here
                    pass
            except Exception:
                pass

            time.sleep(self.poll_interval)
