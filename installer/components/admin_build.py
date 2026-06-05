"""Build the admin SPA at install/update time.

The admin frontend (``spellbook/admin/frontend``) is a Vite/React app whose
compiled bundle is served by the daemon from ``spellbook/admin/static``. That
bundle used to be committed to the repository and validated by a pre-commit
hash check. It is now generated on the operator's machine during installation
by running ``npm ci --legacy-peer-deps`` followed by ``npm run build``.

Node and npm are a HARD requirement. If either binary is absent the component
fails the install with an actionable error rather than silently shipping an
absent or stale bundle.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

# Node.js install hint shared by the missing-node and missing-npm errors.
_NODE_INSTALL_HINT = (
    "Install Node.js (https://nodejs.org) and re-run the spellbook installer."
)


def get_frontend_dir(spellbook_dir: Path) -> Path:
    """Return the admin frontend source directory for ``spellbook_dir``."""
    return spellbook_dir / "spellbook" / "admin" / "frontend"


def build_admin_frontend(
    spellbook_dir: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Compile the admin SPA via ``npm ci`` + ``npm run build``.

    Args:
        spellbook_dir: Path to the spellbook installation (contains the
            ``spellbook/admin/frontend`` source tree).
        dry_run: If True, validate prerequisites but run no build commands.

    Returns: ``(success, message)``.
    """
    # Hard requirement: node and npm must both be on PATH. This check runs
    # even under ``dry_run`` so a dry-run install still surfaces the blocker.
    if shutil.which("node") is None:
        return (
            False,
            f"node is required to build the admin SPA but was not found on "
            f"PATH. {_NODE_INSTALL_HINT}",
        )
    if shutil.which("npm") is None:
        return (
            False,
            f"npm is required to build the admin SPA but was not found on "
            f"PATH. {_NODE_INSTALL_HINT}",
        )

    frontend_dir = get_frontend_dir(spellbook_dir)
    if not frontend_dir.exists():
        return (
            False,
            f"Admin frontend source not found at {frontend_dir}; cannot "
            f"build admin SPA.",
        )

    if dry_run:
        return (
            True,
            "Would build admin SPA (npm ci --legacy-peer-deps + npm run build)",
        )

    try:
        ci = subprocess.run(
            ["npm", "ci", "--legacy-peer-deps"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return (False, "npm ci timed out after 300s")
    if ci.returncode != 0:
        error = ci.stderr.strip() or ci.stdout.strip()
        return (False, f"npm ci --legacy-peer-deps failed: {error}")

    try:
        build = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return (False, "npm run build timed out after 300s")
    if build.returncode != 0:
        error = build.stderr.strip() or build.stdout.strip()
        return (False, f"npm run build failed: {error}")

    return (True, "Admin SPA built (npm ci + npm run build)")
