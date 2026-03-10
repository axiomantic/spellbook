"""Path encoding and project directory resolution for session storage."""

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from fastmcp import Context


def resolve_repo_root(path: str) -> str:
    """Resolve a path to its git repository root, handling worktrees.

    For worktrees, resolves to the main repository root so that
    all worktrees of the same repo share a namespace.

    Falls back to the input path if:
    - Not in a git repository
    - git commands fail or timeout

    Args:
        path: Absolute filesystem path (may be in a worktree).

    Returns:
        Absolute path to the git repository root, or the input path.
    """
    try:
        # git worktree list --porcelain gives the main worktree first
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=path,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            first_line = result.stdout.strip().split("\n")[0]
            if first_line.startswith("worktree "):
                return os.path.normpath(first_line[len("worktree "):])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback: try --show-toplevel (works for non-worktree repos)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return os.path.normpath(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return path


def encode_cwd(cwd: str, resolve_git_root: bool = True) -> str:
    """Encode current working directory for session storage path.

    Args:
        cwd: Absolute path to working directory.
        resolve_git_root: If True, resolve worktrees to repo root first.
            This ensures all worktrees of the same repo share a namespace.

    Returns:
        Encoded path with slashes replaced by dashes, leading dash stripped.

    Examples:
        >>> encode_cwd('/Users/alice/Development/spellbook', resolve_git_root=False)
        'Users-alice-Development-spellbook'
    """
    if resolve_git_root:
        cwd = resolve_repo_root(cwd)
    return cwd.replace('\\', '-').replace('/', '-').lstrip('-')


def get_spellbook_config_dir() -> Path:
    """
    Get the spellbook configuration directory.

    Resolution order:
    1. SPELLBOOK_CONFIG_DIR environment variable
    2. ~/.local/spellbook (default)

    Returns:
        Path to spellbook config directory
    """
    config_dir = os.environ.get('SPELLBOOK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir)

    return Path.home() / '.local' / 'spellbook'


def get_project_dir() -> Path:
    """
    Get session storage directory for current project.

    DEPRECATED: Use get_project_dir_from_context() for MCP tools to get
    the correct client working directory instead of the server's cwd.

    Auto-detects project directory based on current working directory
    and encodes it for storage under the spellbook config directory.

    Resolution order for base directory:
    1. $SPELLBOOK_CONFIG_DIR/projects/
    2. ~/.local/spellbook/projects/ (default)

    Returns:
        Path to project's session directory
    """
    cwd = os.getcwd()
    encoded = encode_cwd(cwd)

    return get_spellbook_config_dir() / 'projects' / encoded


def get_project_dir_for_path(project_path: str) -> Path:
    """
    Get session storage directory for a specific project path.

    Args:
        project_path: Absolute path to project directory

    Returns:
        Path to project's session directory
    """
    encoded = encode_cwd(project_path)
    return get_spellbook_config_dir() / 'projects' / encoded


async def get_project_path_from_context(ctx: "Context") -> str:
    """
    Extract project path from MCP context roots.

    MCP clients (like Claude Code) expose their working directory via the
    roots capability. This function retrieves the first root URI and extracts
    the filesystem path from it.

    Falls back to os.getcwd() if:
    - Context is None
    - No roots are available
    - Root URI is not a file:// URI
    - The list_roots() call times out or is aborted

    Args:
        ctx: FastMCP Context object

    Returns:
        Absolute filesystem path to the project directory
    """
    import asyncio

    if ctx is None:
        return os.getcwd()

    try:
        # Add timeout to prevent indefinite hangs if client doesn't respond
        # Use 1 second timeout - list_roots should be fast
        roots = await asyncio.wait_for(ctx.list_roots(), timeout=1.0)
        if roots and len(roots) > 0:
            # Root URI is like file:///Users/alice/project
            uri = str(roots[0].uri)
            if uri.startswith('file://'):
                # Parse the URI and extract the path
                parsed = urlparse(uri)
                return parsed.path
    except BaseException:
        # Fall back to cwd if roots unavailable
        # Use BaseException to catch asyncio.CancelledError and AbortError
        # which are not subclasses of Exception
        pass

    return os.getcwd()


async def get_project_dir_from_context(ctx: "Context") -> Path:
    """
    Get session storage directory using MCP context roots.

    This is the preferred method for MCP tools to determine the project
    directory, as it uses the client's actual working directory rather
    than the MCP server's cwd.

    Args:
        ctx: FastMCP Context object

    Returns:
        Path to project's session directory
    """
    project_path = await get_project_path_from_context(ctx)
    return get_project_dir_for_path(project_path)
