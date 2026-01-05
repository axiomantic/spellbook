"""Command utilities for work packet execution."""

import os
import json
import time
import subprocess
from pathlib import Path
from typing import Any, Dict, List

def atomic_write_json(path: str, data: dict, timeout: int = 5):
    """
    Write JSON file atomically with lock file.

    Args:
        path: File path to write
        data: Dictionary to write as JSON
        timeout: Max seconds to wait for lock
    """
    lock_path = f"{path}.lock"

    start = time.time()
    while os.path.exists(lock_path):
        if time.time() - start > timeout:
            if time.time() - os.path.getmtime(lock_path) > 30:
                os.remove(lock_path)
                break
            raise TimeoutError(f"Could not acquire lock for {path}")
        time.sleep(0.1)

    with open(lock_path, 'w') as lock:
        lock.write(str(os.getpid()))

    try:
        # Use thread-safe temp file name (PID + timestamp)
        import threading
        temp_path = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        os.replace(temp_path, path)  # atomic on POSIX
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)

def read_json_safe(path: str) -> dict:
    """Read JSON file safely with retry."""
    for attempt in range(3):
        try:
            with open(path) as f:
                content = f.read()
                if not content:
                    time.sleep(0.1)
                    continue
                return json.loads(content)
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            time.sleep(0.1)
    raise ValueError(f"Could not read valid JSON from {path}")

def invoke_skill(skill_name: str, context: dict = None) -> dict:
    """
    Invoke a skill - PLACEHOLDER.

    NOTE: This function's implementation depends on how skills are
    actually invoked in the spellbook system. Update this once
    the actual mechanism is determined.

    In the spellbook system, skills are invoked via Claude Code's
    Skill tool during interactive sessions. For automated execution:
    - Option 1: Shell out to `claude-code` CLI (if it supports non-interactive skill invocation)
    - Option 2: Use spellbook MCP's use_spellbook_skill tool
    - Option 3: Directly spawn a Claude Code agent with skill invocation instructions

    Args:
        skill_name: Name of the skill to invoke (e.g., 'test-driven-development')
        context: Optional context dictionary to pass to the skill

    Returns:
        dict: Result from skill execution

    Raises:
        NotImplementedError: Always, until the actual mechanism is implemented
    """
    raise NotImplementedError(
        f"invoke_skill('{skill_name}') not yet implemented. "
        "The actual skill invocation mechanism needs to be determined. "
        "Skills are invoked via Claude Code's Skill tool in interactive sessions. "
        "For automated execution, we need to determine the correct approach."
    )

def parse_packet_file(packet_file: Path) -> dict:
    """Parse packet markdown file with YAML frontmatter."""
    import yaml
    import re

    content = packet_file.read_text()

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2]
        else:
            frontmatter = {}
            body = content
    else:
        frontmatter = {}
        body = content

    tasks = parse_tasks_from_body(body)

    return {
        "format_version": frontmatter.get("format_version", "1.0.0"),
        "feature": frontmatter.get("feature", ""),
        "track": frontmatter.get("track", 0),
        "worktree": frontmatter.get("worktree", ""),
        "branch": frontmatter.get("branch", ""),
        "tasks": tasks,
        "body": body
    }

def parse_tasks_from_body(body: str) -> List[dict]:
    """Extract tasks from work packet markdown body."""
    import re

    tasks = []
    task_pattern = r'\*\*Task\s+([\d.]+):\*\*\s*(.+?)(?=\n)'

    for match in re.finditer(task_pattern, body):
        task_id = match.group(1)
        task_desc = match.group(2).strip()

        task_start = match.end()
        next_task = re.search(r'\*\*Task\s+[\d.]+:', body[task_start:])
        next_section = re.search(r'\n##', body[task_start:])

        if next_task and next_section:
            task_end = task_start + min(next_task.start(), next_section.start())
        elif next_task:
            task_end = task_start + next_task.start()
        elif next_section:
            task_end = task_start + next_section.start()
        else:
            task_end = len(body)

        task_section = body[task_start:task_end]

        files_match = re.search(r'Files?:\s*(.+?)(?:\n|$)', task_section)
        files = [f.strip() for f in files_match.group(1).split(',')] if files_match else []

        acceptance_match = re.search(r'Acceptance:\s*(.+?)(?:\n|$)', task_section)
        acceptance = acceptance_match.group(1).strip() if acceptance_match else ""

        tasks.append({
            "id": task_id,
            "description": task_desc,
            "files": files,
            "acceptance": acceptance
        })

    return tasks
