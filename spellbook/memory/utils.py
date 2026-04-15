"""Shared utilities for the file-based memory system.

Extracted to avoid duplication across filestore, sync_pipeline,
and search_serena modules.
"""

import hashlib
import os
import subprocess
from pathlib import Path


def derive_namespace_from_cwd(cwd: str | Path) -> str:
    """Derive a project-encoded memory namespace from a working directory.

    Runs ``git rev-parse --show-toplevel`` from ``cwd`` to resolve worktrees
    back to their project root. Falls back to the input path if git resolution
    fails. Returns an empty string when ``cwd`` is empty.

    The project-encoding strips the leading slash and replaces path
    separators with ``-`` so the namespace is safe as a filesystem
    directory name.
    """
    if not cwd:
        return ""
    cwd_str = str(cwd)
    resolved = cwd_str
    try:
        proc = subprocess.run(
            ["git", "-C", cwd_str, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            resolved = proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return resolved.replace("\\", "/").replace("/", "-").lstrip("-")


def content_hash(content: str) -> str:
    """SHA-256 of normalized content (lowercased, whitespace-collapsed)."""
    normalized = " ".join(content.lower().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def iter_memory_files(memory_dir: str):
    """Iterate over all .md files in the memory directory, skipping hidden dirs.

    Yields absolute paths to .md files. Hidden directories (starting with '.')
    such as .archive are pruned from traversal.

    Args:
        memory_dir: Root memory directory to walk.

    Yields:
        Absolute paths to .md memory files.
    """
    for dirpath, dirnames, filenames in os.walk(memory_dir):
        rel = os.path.relpath(dirpath, memory_dir)
        if rel.startswith("."):
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".md"):
                yield os.path.join(dirpath, fname)
