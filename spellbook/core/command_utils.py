"""Command utilities for work packet execution."""

import os
import json
import platform
import time
import subprocess
from pathlib import Path
from typing import Any, Dict, List

# Windows-transient-error retry budget for ``os.replace``.
#
# On Windows, ``os.replace(tmp, target)`` raises ``PermissionError``
# (``WinError 5``) when ``target`` currently has an open handle held by a
# concurrent reader. POSIX rename() atomically swaps the inode without
# caring about open handles; Windows does not. A ``FileNotFoundError``
# can also fire when ``tmp`` was superseded by another writer's rename
# between our stat and our replace. 6 attempts with exponential backoff
# (2, 4, 8, 16, 32, 64 ms) cover realistic contention without blocking
# the caller meaningfully. On non-Windows, exceptions propagate unchanged.
_ATOMIC_REPLACE_MAX_ATTEMPTS: int = 6


def atomic_replace(tmp_path: str, target_path: str) -> None:
    """``os.replace`` with Windows transient-error retry.

    On non-Windows, calls ``os.replace`` directly and lets exceptions
    propagate unchanged (POSIX rename() is unaffected by concurrent
    readers). On Windows, retries ``PermissionError`` (WinError 5: target
    has an open handle) and ``FileNotFoundError`` (tmp was concurrently
    renamed-away by another writer's superseding replace) for up to
    ``_ATOMIC_REPLACE_MAX_ATTEMPTS`` attempts with 2/4/8/16/32/64ms
    backoff. Re-raises the final exception if every retry fails; all
    other exceptions propagate immediately on the first occurrence.
    """
    if platform.system() != "Windows":
        os.replace(tmp_path, target_path)
        return
    last_exc: OSError | None = None
    for attempt in range(_ATOMIC_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(tmp_path, target_path)
            return
        except (PermissionError, FileNotFoundError) as exc:
            last_exc = exc
            if attempt == _ATOMIC_REPLACE_MAX_ATTEMPTS - 1:
                break
            time.sleep(0.002 * (2**attempt))
    assert last_exc is not None
    raise last_exc


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
            try:
                if time.time() - os.path.getmtime(lock_path) > 30:
                    try:
                        os.remove(lock_path)
                    except FileNotFoundError:
                        # Another writer released the stale lock first;
                        # fall through to re-acquire.
                        pass
                    break
            except FileNotFoundError:
                # Lock disappeared between exists() and getmtime() — a
                # concurrent writer released it. Re-check the loop.
                break
            raise TimeoutError(f"Could not acquire lock for {path}")
        time.sleep(0.1)

    with open(lock_path, 'w') as lock:
        lock.write(str(os.getpid()))

    try:
        # Use thread-safe temp file name (PID + thread id + random token)
        # to guarantee uniqueness across concurrent writers, including the
        # narrow window where two threads in the same PID race past the
        # weak lock acquisition above.
        import secrets
        import threading
        temp_path = (
            f"{path}.tmp.{os.getpid()}.{threading.get_ident()}."
            f"{secrets.token_hex(4)}"
        )
        # Ensure parent directory exists BEFORE writing tmp so both
        # tmp and target land in the same dir (required for atomic rename).
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        atomic_replace(temp_path, path)
    finally:
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            # Another writer already reclaimed/removed our lock (weak
            # lock discipline); nothing to do.
            pass

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

from spellbook.sdk.unified import get_agent_client, AgentOptions

def invoke_skill(skill_name: str, context: dict = None) -> dict:
    """
    Invoke a skill via the Unified Agent SDK.

    In the spellbook system, skills are invoked via an assistant's
    Skill tool. This function programmatically triggers that by
    sending a directive to the agent.

    Args:
        skill_name: Name of the skill to invoke (e.g., 'test-driven-development')
        context: Optional context dictionary to pass to the skill

    Returns:
        dict: Result from skill execution (wrapped in a status dict)
    """
    import asyncio
    
    async def _invoke():
        options = AgentOptions()
        client = get_agent_client(options=options)
        
        ctx_str = f" with context: {json.dumps(context)}" if context else ""
        prompt = f"Invoke the skill '{skill_name}'{ctx_str}. Follow its instructions to completion."
        
        try:
            result = await client.run(prompt)
            return {"status": "success", "output": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return asyncio.run(_invoke())

def parse_packet_file(packet_file: Path) -> dict:
    """Parse packet markdown file with YAML frontmatter."""
    import yaml
    import re

    content = packet_file.read_text(encoding="utf-8")

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
