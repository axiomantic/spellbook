"""``spellbook update`` command.

Self-update via git tags.  Finds the spellbook repository, fetches
tags, and updates to the latest release if available.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from spellbook.cli.formatting import output


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``update`` subcommand."""
    parser = subparsers.add_parser(
        "update",
        help="Check for and apply spellbook updates",
        description="Self-update spellbook via git tags.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Only check for updates, don't apply",
    )
    parser.set_defaults(func=run)


def _find_repo_dir() -> str | None:
    """Find the spellbook repo directory.

    Checks:
    1. SPELLBOOK_DIR environment variable
    2. Parent of the installed spellbook package
    """
    env_dir = os.environ.get("SPELLBOOK_DIR")
    if env_dir and Path(env_dir).is_dir():
        return env_dir

    try:
        import spellbook

        pkg_dir = Path(spellbook.__file__).parent.parent
        if (pkg_dir / ".git").exists() or (pkg_dir / ".version").exists():
            return str(pkg_dir)
    except Exception:
        pass

    return None


def _get_current_version(repo_dir: str) -> str:
    """Get the current version from .version file or git describe."""
    version_file = Path(repo_dir) / ".version"
    if version_file.exists():
        return version_file.read_text().strip()

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    try:
        from importlib.metadata import version

        return version("spellbook")
    except Exception:
        return "unknown"


def _get_latest_version(repo_dir: str) -> str:
    """Fetch tags and find the latest release tag."""
    try:
        subprocess.run(
            ["git", "fetch", "--tags", "--quiet"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"

    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-version:refname"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Return first tag (latest version)
            return result.stdout.strip().split("\n")[0]
    except FileNotFoundError:
        pass

    return "unknown"


def run(args: argparse.Namespace) -> None:
    """Execute the update command."""
    repo_dir = _find_repo_dir()

    if repo_dir is None:
        print(
            "Error: Cannot locate spellbook repository. Set SPELLBOOK_DIR.",
            file=sys.stderr,
        )
        sys.exit(1)

    current = _get_current_version(repo_dir)
    json_mode = getattr(args, "json", False)
    check_only = getattr(args, "check", False)

    if check_only:
        latest = _get_latest_version(repo_dir)
        update_available = (
            latest != "unknown"
            and current != "unknown"
            and latest != current
        )

        if json_mode:
            output(
                {
                    "current_version": current,
                    "latest_version": latest,
                    "update_available": update_available,
                    "repo_dir": repo_dir,
                },
                json_mode=True,
            )
        else:
            print(f"Current version: {current}")
            print(f"Latest version:  {latest}")
            if update_available:
                print(f"\nUpdate available! Run 'spellbook update' to update.")
            else:
                print("\nAlready up to date.")
        return

    # Perform the update
    latest = _get_latest_version(repo_dir)
    update_available = (
        latest != "unknown"
        and current != "unknown"
        and latest != current
    )

    if not update_available:
        if json_mode:
            output(
                {
                    "current_version": current,
                    "latest_version": latest,
                    "updated": False,
                    "message": "Already up to date",
                },
                json_mode=True,
            )
        else:
            print(f"Current version: {current}")
            print("Already up to date.")
        return

    print(f"Updating from {current} to {latest}...")

    # Checkout the latest tag
    result = subprocess.run(
        ["git", "checkout", latest],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if result.returncode != 0:
        print(f"Error: git checkout failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Reinstall
    print("Reinstalling...")
    reinstall = subprocess.run(
        ["uv", "pip", "install", "-e", "."],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if reinstall.returncode != 0:
        print(f"Warning: reinstall may have failed: {reinstall.stderr}", file=sys.stderr)

    if json_mode:
        output(
            {
                "current_version": current,
                "latest_version": latest,
                "updated": True,
                "message": f"Updated to {latest}",
            },
            json_mode=True,
        )
    else:
        print(f"Updated to {latest}")
