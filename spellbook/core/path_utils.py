"""Path encoding and project directory resolution for session storage."""

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ``resolve_repo_root`` is on the Stop hook's path, whose harness timeout is a
# BUDGET: a hook that overruns it is cancelled, its output discarded, and the
# stop proceeds -- a silent bypass of the gate rather than a loud failure. The
# two figures below are what that budget is derived from in
# ``installer.components.hooks``, so they are constants rather than literals at
# the call sites. ``scripts/develop_gate_ledger._fallback_encode_cwd`` cannot
# import these (it exists for the case where this package is unimportable) but
# spends the same two calls at the same timeout, so the bound holds either way.
GIT_SUBPROCESS_TIMEOUT_SECONDS = 5
GIT_SUBPROCESS_CALLS_PER_RESOLVE = 2

if TYPE_CHECKING:
    from fastmcp import Context


@dataclass
class GitContext:
    """Git context for a project directory."""
    branch: Optional[str] = None
    worktree_name: Optional[str] = None
    is_worktree: bool = False
    repo_root: Optional[str] = None


def detect_git_context(project_path: str, timeout: float = 5.0) -> GitContext:
    """Detect git branch and worktree context for alias derivation.

    Uses subprocess calls with timeout to extract git state.
    Returns GitContext with all-None fields on any failure.

    Args:
        project_path: Absolute path to the project directory.
        timeout: Maximum seconds for each git subprocess call.

    Returns:
        GitContext with branch/worktree info. All fields may be None
        if git is unavailable or the path is not a git repo.
    """
    branch: Optional[str] = None
    worktree_name: Optional[str] = None
    is_worktree = False

    # Detect branch name
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path,
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            raw_branch = result.stdout.strip()
            if raw_branch == "HEAD":
                # Detached HEAD: use short commit hash instead
                try:
                    hash_result = subprocess.run(
                        ["git", "rev-parse", "--short", "HEAD"],
                        cwd=project_path,
                        capture_output=True, text=True, timeout=timeout,
                    )
                    if hash_result.returncode == 0:
                        branch = hash_result.stdout.strip()
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    branch = "head"
            else:
                branch = raw_branch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.debug("Git branch detection failed for %s", project_path, exc_info=True)
        return GitContext()

    # Detect worktree status
    main_worktree: Optional[str] = None
    try:
        wt_result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_path,
            capture_output=True, text=True, timeout=timeout,
        )
        if wt_result.returncode == 0 and wt_result.stdout.strip():
            # Parse porcelain output: first "worktree <path>" is main worktree
            lines = wt_result.stdout.strip().split("\n")
            for line in lines:
                if line.startswith("worktree "):
                    main_worktree = os.path.normpath(line[len("worktree "):])
                    break  # First worktree entry is always the main one

            if main_worktree:
                normalized_project = os.path.normpath(project_path)
                if normalized_project != main_worktree:
                    is_worktree = True
                    worktree_name = os.path.basename(normalized_project)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.debug("Git worktree detection failed for %s", project_path, exc_info=True)

    # Cache the repo root so callers avoid redundant subprocess calls.
    # If we already parsed the main worktree, use it; otherwise fall back
    # to resolve_repo_root() which runs its own git commands.
    repo_root: Optional[str] = None
    if main_worktree:
        repo_root = main_worktree
    else:
        try:
            repo_root = resolve_repo_root(project_path)
        except Exception:
            logger.debug("Repo root resolution failed for %s", project_path, exc_info=True)

    return GitContext(
        branch=branch,
        worktree_name=worktree_name,
        is_worktree=is_worktree,
        repo_root=repo_root,
    )


# Environment variables that move git's repository discovery off the
# filesystem walk below. Any one of them set means the on-disk layout no
# longer determines the answer, so the walk declines and git decides.
_GIT_DISCOVERY_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)


def _read_gitdir_pointer(dot_git: Path, base: Path) -> Optional[Path]:
    """Resolve the ``gitdir: <path>`` pointer in a ``.git`` FILE."""
    try:
        text = dot_git.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None
    line = text.strip()
    if not line.startswith("gitdir:"):
        return None
    target = line[len("gitdir:"):].strip()
    if not target:
        return None
    resolved = Path(target)
    if not resolved.is_absolute():
        resolved = base / resolved
    try:
        return Path(os.path.realpath(resolved))
    except OSError:
        return None


def _looks_like_git_dir(candidate: Path) -> bool:
    """A directory git would accept as a repository/worktree git dir.

    ``HEAD`` is the cheapest marker git itself requires. Checking it stops
    the walk from claiming an empty directory that merely happens to be
    named ``.git`` -- git rejects that and keeps walking upward, and a walk
    that stopped there would return a root git never would.
    """
    try:
        return (candidate / "HEAD").is_file()
    except OSError:
        return False


def _root_if_spelled_as_on_disk(directory: Path) -> Optional[str]:
    """``directory`` as a root string, or None if its spelling is unconfirmed.

    ``realpath`` resolves symlinks but leaves CASE alone, so on a
    case-insensitive volume a caller's ``/x/MYREPO`` survives the walk exactly
    as written, while git -- which chdirs and reads ``getcwd`` -- answers
    ``/x/myrepo``. Both are non-None and they disagree, and since ``encode_cwd``
    turns this string into a storage filename the disagreement is silent: the
    caller reads the resulting miss as "no state for this project".

    The spelling is CHECKED against the parent listing rather than
    reconstructed from it. Reconstructing means folding case by Python's rules
    where the filesystem's rules apply -- HFS+ also normalizes Unicode, and
    other volumes fold differently again -- so a reconstruction is a guess of
    exactly the kind this module refuses. A check can only ever cost a deferral.
    """
    root = os.path.normpath(str(directory))
    current = Path(root)
    while True:
        parent = current.parent
        if parent == current:
            return root
        try:
            if current.name not in os.listdir(parent):
                return None
        except OSError:
            return None
        current = parent


def _git_free_repo_root(path: str) -> Optional[str]:
    """The repo root for ``path`` read off the filesystem, or None to defer.

    Reproduces what ``git worktree list --porcelain`` reports as its first
    entry, for the layouts whose answer is fully determined by what is on
    disk: a plain repository, a linked worktree, any subdirectory of
    either, and a path in no repository at all. Every other shape returns
    None, which sends the caller to git.

    None -- not a guess -- is the response to anything unrecognized. A wrong
    root is not a slow path, it is a different namespace: ``encode_cwd``
    turns this string into a state filename, so a root that differs from
    git's by one character silently orphans the file it should have found,
    and the caller sees an ordinary "no state here". Deferring costs a
    process spawn; guessing costs correctness, so the two are not traded
    against each other anywhere below.

    Shapes deliberately deferred, each verified against real git:

    - A **submodule**: git reports the git dir (``<super>/.git/modules/<n>``)
      rather than the submodule's working tree. Its git dir carries no
      ``commondir``, which is how the walk recognizes it.
    - A **bare repository**: git reports the bare directory itself; there is
      no ``.git`` entry for the walk to find.
    - A **worktree of a bare repository**: ``commondir`` resolves to a
      directory not named ``.git``, so the main-worktree parent derivation
      does not apply.
    - Anything under a ``GIT_*`` discovery override.

    - Any path spelled in a case the disk does not use. ``realpath`` does not
      canonicalize case, so on a case-insensitive volume the walk would answer
      with the caller's spelling where git answers with the disk's.

    Git's own answer is realpath-based (it chdirs, and ``getcwd`` returns a
    resolved path), so the walk starts from ``os.path.realpath``. Git also
    stops discovery at a filesystem boundary unless
    ``GIT_DISCOVERY_ACROSS_FILESYSTEM`` is set; the ``st_dev`` comparison
    below is that rule, not an optimization.
    """
    if any(os.environ.get(var) for var in _GIT_DISCOVERY_ENV):
        return None

    if not path:
        # ``realpath("")`` is the process cwd, but ``subprocess(cwd="")``
        # raises, so git resolves nothing and the input passes through.
        return path

    try:
        start = Path(os.path.realpath(path))
        if not start.is_dir():
            # git cannot chdir here, so both of its probes fail and the
            # caller's documented fallback is the untouched input path.
            return path
        start_dev = start.stat().st_dev
    except OSError:
        return None

    for directory in (start, *start.parents):
        try:
            if directory.stat().st_dev != start_dev:
                # Git stopped discovery here, so it found no repository.
                return path
            dot_git = directory / ".git"
            is_dir = dot_git.is_dir()
            is_file = dot_git.is_file()
            bare_here = (
                not is_dir
                and not is_file
                and _looks_like_git_dir(directory)
                and (directory / "objects").is_dir()
            )
        except OSError:
            return None

        if bare_here:
            return None

        if is_dir:
            if not _looks_like_git_dir(dot_git):
                return None
            return _root_if_spelled_as_on_disk(directory)

        if is_file:
            git_dir = _read_gitdir_pointer(dot_git, directory)
            if git_dir is None or not _looks_like_git_dir(git_dir):
                return None
            common_file = git_dir / "commondir"
            try:
                if not common_file.is_file():
                    return None  # submodule: a git dir with no common dir
                common_raw = common_file.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                return None
            if not common_raw:
                return None
            common = Path(common_raw)
            if not common.is_absolute():
                common = git_dir / common
            try:
                common = Path(os.path.realpath(common))
            except OSError:
                return None
            if common.name != ".git":
                return None  # worktree of a bare repository
            main_root = common.parent
            try:
                if not (main_root / ".git").exists():
                    return None
            except OSError:
                return None
            return _root_if_spelled_as_on_disk(main_root)

        if dot_git.exists():
            # Present but neither file nor directory. Git's acceptance rules
            # for this are not reconstructable from a stat.
            return None

    return path


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
    # The filesystem walk answers the layouts it can prove and returns None
    # for the rest. It is not a cache: nothing it reads is retained between
    # calls, so there is no stale state to invalidate. This function is on
    # the Task PostToolUse hook path, which runs as a FRESH PROCESS per
    # event -- an in-process memo would be written once and never read, so
    # removing the spawn is the only saving available here.
    fast = _git_free_repo_root(path)
    if fast is not None:
        return fast

    try:
        # git worktree list --porcelain gives the main worktree first
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=path,
            capture_output=True, text=True,
            timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            first_line = result.stdout.strip().split("\n")[0]
            if first_line.startswith("worktree "):
                return os.path.normpath(first_line[len("worktree "):])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.debug("Git worktree list failed for %s", path, exc_info=True)

    # Fallback: try --show-toplevel (works for non-worktree repos)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True, text=True,
            timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            return os.path.normpath(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.debug("Git show-toplevel failed for %s", path, exc_info=True)

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
