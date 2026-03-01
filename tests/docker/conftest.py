"""Shared test fixtures for Docker integration tests.

Provides fixtures for:
- Simulated spellbook git repos with update history
- Isolated HOME directories for platform config isolation
- Platform-specific environment variable configuration
- Local HTTP server for bootstrap.sh testing
- Subprocess-based installer invocation
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Callable, Generator, Iterator

import pytest

# Mark all tests in this directory as docker tests (skipped locally, run in CI)
pytestmark = pytest.mark.docker

# Root of the real spellbook project (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Files and directories essential for a functional spellbook repo clone.
# Directories are copied recursively; files are copied individually.
ESSENTIAL_DIRS = [
    "installer",
    "spellbook_mcp",
    "skills",
    "commands",
    "agents",
    "lib",
]
ESSENTIAL_FILES = [
    "install.py",
    "pyproject.toml",
    ".version",
    "AGENTS.spellbook.md",
    "bootstrap.sh",
]


@dataclass(frozen=True)
class InstallerResult:
    """Result of running install.py via subprocess."""

    returncode: int
    stdout: str
    stderr: str


@pytest.fixture(scope="session")
def spellbook_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a bare git repo simulating the spellbook remote.

    The bare repo contains two commits on the ``main`` branch:
    1. Initial commit with all essential files at the current version.
    2. A version bump commit (patch increment) so that ``check_for_updates``
       detects an available update.

    Returns:
        Path to the bare git repository.
    """
    base = tmp_path_factory.mktemp("spellbook-remote")
    bare_repo = base / "spellbook.git"
    work_dir = base / "spellbook-work"

    # Initialize bare repo
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "--bare", str(bare_repo)],
        check=True,
        capture_output=True,
    )

    # Clone bare repo to working directory
    subprocess.run(
        ["git", "clone", str(bare_repo), str(work_dir)],
        check=True,
        capture_output=True,
    )

    # Configure git identity for commits
    subprocess.run(
        ["git", "-C", str(work_dir), "config", "user.email", "test@spellbook.test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work_dir), "config", "user.name", "Spellbook Test"],
        check=True,
        capture_output=True,
    )

    # Copy essential directories
    for dir_name in ESSENTIAL_DIRS:
        src = PROJECT_ROOT / dir_name
        dst = work_dir / dir_name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # Copy essential files
    for file_name in ESSENTIAL_FILES:
        src = PROJECT_ROOT / file_name
        dst = work_dir / file_name
        if src.is_file():
            shutil.copy2(src, dst)

    # Commit 1: initial state at current version
    subprocess.run(
        ["git", "-C", str(work_dir), "add", "-A"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work_dir), "commit", "-m", "Initial commit"],
        check=True,
        capture_output=True,
    )

    # Read current version and bump it for commit 2
    version_path = work_dir / ".version"
    current_version = version_path.read_text().strip()
    parts = current_version.split(".")
    # Bump patch version
    parts[-1] = str(int(parts[-1]) + 1)
    bumped_version = ".".join(parts)
    version_path.write_text(bumped_version + "\n")

    # Commit 2: version bump (the "update" commit)
    subprocess.run(
        ["git", "-C", str(work_dir), "add", ".version"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work_dir), "commit", "-m", f"Bump version to {bumped_version}"],
        check=True,
        capture_output=True,
    )

    # Push both commits to the bare repo
    subprocess.run(
        ["git", "-C", str(work_dir), "push", "origin", "main"],
        check=True,
        capture_output=True,
    )

    return bare_repo


@pytest.fixture()
def install_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory for use as an install target.

    Returns:
        Path to an empty temporary directory.
    """
    target = tmp_path / "install-target"
    target.mkdir()
    return target


@pytest.fixture()
def isolated_home(tmp_path: Path) -> Generator[Path, None, None]:
    """Create an isolated HOME directory and set the HOME env var.

    This prevents tests from reading or writing the real user's
    ``~/.claude/``, ``~/.config/``, etc. The original HOME is restored
    on teardown.

    Yields:
        Path to the isolated HOME directory.
    """
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(home_dir)
    try:
        yield home_dir
    finally:
        if original_home is not None:
            os.environ["HOME"] = original_home
        else:
            os.environ.pop("HOME", None)


@pytest.fixture()
def platform_env(
    isolated_home: Path,
) -> Callable[[str], contextmanager[None]]:
    """Factory fixture that returns a context manager for platform-specific env vars.

    For platforms whose installer respects a config-dir env var
    (``claude_code`` via ``CLAUDE_CONFIG_DIR``, ``crush`` via
    ``CRUSH_GLOBAL_CONFIG``), the env var is set to point inside the
    isolated home. For all other platforms (``opencode``, ``codex``,
    ``gemini``), the directories are created under the isolated HOME
    so that ``Path.home()``-relative resolution finds them.

    The context manager creates the directories and restores env vars
    on exit.

    Usage::

        with platform_env("claude_code"):
            # CLAUDE_CONFIG_DIR is set, directory exists
            ...
    """
    # Map of platform -> (env_var_name | None, relative_path_from_home)
    platform_dirs: dict[str, tuple[str | None, str]] = {
        "claude_code": ("CLAUDE_CONFIG_DIR", ".claude"),
        "opencode": (None, ".config/opencode"),
        "codex": (None, ".codex"),
        "gemini": (None, ".gemini"),
        "crush": ("CRUSH_GLOBAL_CONFIG", ".local/share/crush"),
    }

    @contextmanager
    def _make_env(platform: str) -> Iterator[None]:
        if platform not in platform_dirs:
            raise ValueError(
                f"Unknown platform: {platform!r}. "
                f"Supported: {sorted(platform_dirs)}"
            )

        env_var, rel_path = platform_dirs[platform]
        config_dir = isolated_home / rel_path
        config_dir.mkdir(parents=True, exist_ok=True)

        original_value: str | None = None
        had_var = False
        if env_var is not None:
            had_var = env_var in os.environ
            original_value = os.environ.get(env_var)
            os.environ[env_var] = str(config_dir)

        try:
            yield
        finally:
            if env_var is not None:
                if had_var and original_value is not None:
                    os.environ[env_var] = original_value
                elif env_var in os.environ:
                    del os.environ[env_var]

    return _make_env


class _QuietHandler(SimpleHTTPRequestHandler):
    """HTTP request handler that suppresses access log output."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture(scope="session")
def http_server(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    """Start a local HTTP server serving bootstrap.sh.

    Copies ``bootstrap.sh`` from the project root into a temporary
    directory and serves it on a random port via a daemon thread.

    Yields:
        Base URL string, e.g. ``http://localhost:12345``.
    """
    serve_dir = tmp_path_factory.mktemp("http-serve")
    src = PROJECT_ROOT / "bootstrap.sh"
    if src.is_file():
        shutil.copy2(src, serve_dir / "bootstrap.sh")

    server = HTTPServer(
        ("localhost", 0),
        lambda *args, **kwargs: _QuietHandler(*args, directory=str(serve_dir), **kwargs),
    )
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://localhost:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture()
def run_installer() -> Callable[..., InstallerResult]:
    """Provide a callable that runs ``install.py`` via subprocess.

    The callable signature is::

        run_installer(*args: str, env: dict[str, str] | None = None,
                      cwd: str | Path | None = None) -> InstallerResult

    It always invokes ``python install.py <args>`` using the project's
    ``install.py``. Extra environment variables are merged into the
    current environment (they do not replace it). stdout and stderr
    are captured as strings.

    Returns:
        A callable that returns an ``InstallerResult``.
    """
    install_script = PROJECT_ROOT / "install.py"

    def _run(
        *args: str,
        env: dict[str, str] | None = None,
        cwd: str | Path | None = None,
    ) -> InstallerResult:
        run_env = os.environ.copy()
        if env is not None:
            run_env.update(env)

        proc = subprocess.run(
            ["python3", str(install_script), *args],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd is not None else None,
            env=run_env,
            timeout=120,
        )
        return InstallerResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    return _run


@pytest.fixture()
def committed_repo(tmp_path: Path, spellbook_repo: Path) -> Path:
    """Clone the bare spellbook repo and reset to the first commit.

    This simulates a spellbook installation that is one commit behind
    the remote, so ``check_for_updates`` will detect the version-bump
    commit as an available update.

    Returns:
        Path to the working repository (checked out at the first commit).
    """
    work_dir = tmp_path / "spellbook-local"

    # Clone from the bare repo
    subprocess.run(
        ["git", "clone", str(spellbook_repo), str(work_dir)],
        check=True,
        capture_output=True,
    )

    # Configure git identity (needed for any subsequent git operations in tests)
    subprocess.run(
        ["git", "-C", str(work_dir), "config", "user.email", "test@spellbook.test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work_dir), "config", "user.name", "Spellbook Test"],
        check=True,
        capture_output=True,
    )

    # Get the first commit SHA (the one before the version bump)
    result = subprocess.run(
        ["git", "-C", str(work_dir), "rev-list", "--max-parents=0", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    first_commit_sha = result.stdout.strip()

    # Reset to the first commit so there is an update available
    subprocess.run(
        ["git", "-C", str(work_dir), "reset", "--hard", first_commit_sha],
        check=True,
        capture_output=True,
    )

    return work_dir
